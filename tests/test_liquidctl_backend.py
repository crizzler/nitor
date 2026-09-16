"""The real backend, exercised with a recorded process runner instead of liquidctl."""

from __future__ import annotations

import subprocess

import pytest

from nitor.backend.liquidctl_cli import CommandResult, LiquidctlBackend
from nitor.backend.mock import mock_devices
from nitor.domain import (
    NZXT_VENDOR_ID,
    BackendMissingError,
    Color,
    HardwareError,
    LightingState,
    PermissionDeniedError,
    lookup_profile,
)

CONTROLLER = mock_devices()[0]


class FakeLiquidctl:
    """Stands in for the liquidctl program."""

    def __init__(self, responses: dict[tuple[str, ...], CommandResult] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, ...]] = []
        self.error: BaseException | None = None

    def __call__(self, argv: tuple[str, ...], timeout: float) -> CommandResult:
        self.calls.append(argv)
        if self.error is not None:
            raise self.error
        arguments = tuple(argv[1:])
        if arguments in self.responses:
            return self.responses[arguments]
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="")


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend liquidctl is on PATH."""
    monkeypatch.setattr(
        "nitor.backend.liquidctl_cli.shutil.which", lambda _name: "/usr/bin/liquidctl"
    )


def test_missing_backend_is_reported_with_an_install_command() -> None:
    backend = LiquidctlBackend("definitely-not-liquidctl")
    status = backend.status
    assert status.available is False
    assert status.install_command == "sudo pacman -S liquidctl"
    assert status.hint is not None
    with pytest.raises(BackendMissingError):
        backend.discover_devices()


def test_status_reports_the_installed_version(installed: None) -> None:
    runner = FakeLiquidctl(
        {("--version",): CommandResult(argv=(), returncode=0, stdout="liquidctl v1.16.0\n")}
    )
    backend = LiquidctlBackend(runner=runner)
    assert backend.status.available is True
    assert backend.status.version == "1.16.0"
    assert "1.16.0" in backend.status.summary
    # The answer is cached, so repeated interface updates do not spawn processes.
    assert backend.status.version == "1.16.0"
    assert len(runner.calls) == 1


def test_status_can_be_re_probed(installed: None) -> None:
    runner = FakeLiquidctl()
    backend = LiquidctlBackend(runner=runner)
    assert backend.status.available is True
    backend.refresh()
    assert len(runner.calls) == 2


def test_a_backend_that_cannot_report_its_version_is_still_usable(installed: None) -> None:
    runner = FakeLiquidctl({("--version",): CommandResult(argv=(), returncode=1, stderr="boom")})
    backend = LiquidctlBackend(runner=runner)
    assert backend.status.available is True
    assert backend.status.version is None
    assert backend.status.summary == "liquidctl"


def test_discovery_parses_the_json_list(installed: None) -> None:
    payload = (
        '[{"description": "NZXT RGB & Fan Controller", "vendor_id": 7793, "product_id": 8208,'
        ' "serial_number": "SN1", "bus": "hid", "address": "/dev/hidraw5", "driver": "SmartDevice2"}]'
    )
    runner = FakeLiquidctl(
        {("list", "--json"): CommandResult(argv=(), returncode=0, stdout=payload)}
    )
    devices = LiquidctlBackend(runner=runner).discover_devices()
    assert [device.usb_id for device in devices] == ["1e71:2010"]
    assert runner.calls == [("/usr/bin/liquidctl", "list", "--json")]


def test_initialisation_attaches_channels_and_firmware(installed: None) -> None:
    output = (
        "NZXT RGB & Fan Controller\n"
        "├── Firmware version                      1.5.0\n"
        "└── LED 1 accessory 1        HUE 2 LED Strip 300 mm\n"
    )
    runner = FakeLiquidctl(
        {
            ("--match", "NZXT RGB & Fan Controller", "initialize"): CommandResult(
                argv=(), returncode=0, stdout=output
            )
        }
    )
    device = LiquidctlBackend(runner=runner).initialize_device(CONTROLLER)
    assert device.firmware == "1.5.0"
    channels = {channel.id: channel for channel in device.channels}
    assert channels["led1"].accessories == ("HUE 2 LED Strip 300 mm",)
    assert channels["led2"].has_accessories is False
    assert channels["sync"].led_count == 10


def test_initialisation_output_on_stderr_is_still_parsed(installed: None) -> None:
    runner = FakeLiquidctl(
        {
            ("--match", "NZXT RGB & Fan Controller", "initialize"): CommandResult(
                argv=(), returncode=0, stdout="", stderr="└── Firmware version  9.9.9\n"
            )
        }
    )
    device = LiquidctlBackend(runner=runner).initialize_device(CONTROLLER)
    assert device.firmware == "9.9.9"


def test_applying_lighting_runs_one_command(installed: None) -> None:
    runner = FakeLiquidctl()
    backend = LiquidctlBackend(runner=runner)
    applied = backend.apply_lighting(
        CONTROLLER,
        LightingState(channel="led1", effect="fixed", colors=(Color(0, 170, 255),)),
    )
    assert runner.calls == [
        (
            "/usr/bin/liquidctl",
            "--match",
            "NZXT RGB & Fan Controller",
            "set",
            "led1",
            "color",
            "fixed",
            "00aaff",
        )
    ]
    assert applied.command_line.startswith("liquidctl --match")
    assert [color.to_hex() for color in applied.colors] == ["#00AAFF"]


def test_turning_off_uses_the_off_effect(installed: None) -> None:
    runner = FakeLiquidctl()
    applied = LiquidctlBackend(runner=runner).turn_off(CONTROLLER, "led2")
    assert applied.is_off
    assert runner.calls[-1][-3:] == ("led2", "color", "off")


def test_permission_failures_are_reported_as_such(installed: None) -> None:
    runner = FakeLiquidctl(
        {
            ("list", "--json"): CommandResult(
                argv=(), returncode=1, stderr="Access denied (insufficient permissions)"
            )
        }
    )
    with pytest.raises(PermissionDeniedError) as info:
        LiquidctlBackend(runner=runner).discover_devices()
    assert "udev" in (info.value.hint or "")


def test_timeouts_do_not_escape_as_raw_subprocess_errors(installed: None) -> None:
    runner = FakeLiquidctl()
    runner.error = subprocess.TimeoutExpired(cmd="liquidctl", timeout=15)
    with pytest.raises(HardwareError) as info:
        LiquidctlBackend(runner=runner).discover_devices()
    assert "did not respond" in info.value.message


def test_a_vanishing_executable_is_reported_as_a_missing_backend(installed: None) -> None:
    runner = FakeLiquidctl()
    runner.error = FileNotFoundError(2, "No such file or directory")
    with pytest.raises(BackendMissingError):
        LiquidctlBackend(runner=runner).discover_devices()


def test_unsupported_models_are_refused_before_any_command_runs(installed: None) -> None:
    from nitor.domain import NotSupportedError

    runner = FakeLiquidctl()
    unsupported = mock_devices()[0].__class__(
        key="1e71:2011",
        description="NZXT RGB & Fan Controller (3+6 channels)",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2011,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2011),
    )
    with pytest.raises(NotSupportedError):
        LiquidctlBackend(runner=runner).apply_lighting(
            unsupported,
            LightingState(channel="led1", effect="fixed", colors=(Color(255, 255, 255),)),
        )
    assert runner.calls == []
