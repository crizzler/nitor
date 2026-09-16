"""The diagnostics report, including what it must never contain."""

from __future__ import annotations

import getpass
import socket
from pathlib import Path

import pytest

from nitor import __version__
from nitor.backend.base import BackendStatus
from nitor.backend.mock import MockBackend
from nitor.backend.registry import DeviceAccess
from nitor.domain import NZXT_VENDOR_ID, Device, lookup_profile
from nitor.services.diagnostics import (
    build_report,
    describe_device,
    desktop_environment,
    distribution_name,
    read_os_release,
    session_type,
    system_summary,
    toolkit_version,
)

SECRET_SERIAL = "SERIAL-MUST-NOT-APPEAR"


def controller() -> Device:
    return Device(
        key="1e71:2010",
        description="NZXT RGB & Fan Controller",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2010,
        driver="SmartDevice2",
        address="/dev/hidraw5",
        serial=SECRET_SERIAL,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2010),
    )


def initialized_controller() -> Device:
    return MockBackend().initialize_device(controller())


def test_report_contains_what_a_maintainer_needs() -> None:
    device = initialized_controller()
    report = build_report(
        backend_status=BackendStatus(name="liquidctl", available=True, version="1.16.0"),
        devices=[device],
        access={"1e71:2010": DeviceAccess(device_key="1e71:2010", accessible=True)},
        apply_on_login=True,
        backend_mode="auto",
    )
    flat = " ".join(report.split())

    assert f"Nitor {__version__}" in report
    assert "liquidctl" in report
    assert "1.16.0" in report
    assert "1e71:2010" in report
    assert "SmartDevice2" in report
    assert "led1" in report
    assert "HUE 2 LED Strip 300 mm" in report
    assert "Apply on login: yes" in flat


def test_report_says_when_access_is_denied() -> None:
    device = initialized_controller()
    report = build_report(
        backend_status=BackendStatus(name="liquidctl", available=True),
        devices=[device],
        access={
            "1e71:2010": DeviceAccess(
                device_key="1e71:2010",
                accessible=False,
                reason="/dev/hidraw5 is not writable by this user",
            )
        },
    )
    assert "access: NO" in " ".join(report.split())
    assert "/dev/hidraw5 is not writable" in report


def test_report_explains_a_missing_backend() -> None:
    report = build_report(
        backend_status=BackendStatus(
            name="liquidctl",
            available=False,
            summary="Lighting backend not installed",
            hint="Install it with: sudo pacman -S liquidctl",
            install_command="sudo pacman -S liquidctl",
        ),
    )
    assert "Backend available: NO" in report
    assert "sudo pacman -S liquidctl" in report
    assert "none detected" in report


def test_report_never_contains_identifying_information() -> None:
    """No user names, host names, home directories or device serial numbers."""
    report = build_report(
        backend_status=BackendStatus(name="liquidctl", available=True, version="1.16.0"),
        devices=[initialized_controller()],
    )

    assert SECRET_SERIAL not in report
    assert getpass.getuser() not in report
    assert socket.gethostname() not in report
    assert str(Path.home()) not in report
    assert "/home/" not in report


def test_devices_without_channels_say_so() -> None:
    lines = "\n".join(describe_device(controller(), None))
    assert "channels:  not probed yet" in lines


def test_unsupported_devices_carry_their_note() -> None:
    unsupported = Device(
        key="1e71:2011",
        description="NZXT RGB & Fan Controller (3+6 channels)",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2011,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2011),
    )
    text = "\n".join(describe_device(unsupported, None))
    assert "supported: no" in text
    assert "liquidctl does not implement" in text


def test_os_release_parsing_handles_quotes_and_comments(tmp_path: Path) -> None:
    path = tmp_path / "os-release"
    path.write_text(
        '# a comment\nNAME="CachyOS Linux"\nID=cachyos\nPRETTY_NAME="CachyOS"\n\n',
        encoding="utf-8",
    )
    entries = read_os_release(path)
    assert entries["PRETTY_NAME"] == "CachyOS"
    assert entries["ID"] == "cachyos"


def test_os_release_parsing_survives_a_missing_file(tmp_path: Path) -> None:
    assert read_os_release(tmp_path / "nope") == {}


def test_summary_has_the_expected_shape() -> None:
    labels = [label for label, _ in system_summary()]
    assert labels == [
        "Application",
        "Application ID",
        "Distribution",
        "Kernel",
        "Desktop",
        "Session",
        "Python",
        "Toolkit",
    ]


@pytest.mark.parametrize(
    ("variable", "expected"),
    [("XDG_CURRENT_DESKTOP", "KDE"), ("DESKTOP_SESSION", "plasma")],
)
def test_desktop_detection_prefers_the_session(
    monkeypatch: pytest.MonkeyPatch, variable: str, expected: str
) -> None:
    for name in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "XDG_SESSION_DESKTOP"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(variable, expected)
    assert desktop_environment() == expected


def test_session_and_distribution_are_never_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    assert session_type() == "unknown"
    assert distribution_name()


def test_toolkit_version_reports_something_usable() -> None:
    assert toolkit_version()
