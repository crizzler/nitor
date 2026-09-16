"""The cooling safety boundary.

If any of these tests ever fail, the application has gained the ability to poke at a pump, a fan,
the firmware or the firmware-controlled screen. That is the one thing this project must never do,
so these are the most important tests in the suite.

Command lines are represented here as liquidctl *argument vectors* — the program name is added by
the process runner, and a vector that still carries it is refused (failing closed).
"""

from __future__ import annotations

import pytest

from nitor.backend.commands import (
    build_initialize_argv,
    build_list_argv,
    build_set_argv,
    build_status_argv,
    build_version_argv,
    validate_argv,
)
from nitor.backend.liquidctl_cli import CommandResult, LiquidctlBackend
from nitor.backend.mock import MockBackend
from nitor.domain import (
    Color,
    LightingState,
    SafetyViolationError,
    effects_for_family,
)

FORBIDDEN_ARGUMENTS: list[tuple[str, ...]] = [
    ("set", "fan1", "speed", "90"),
    ("set", "fan2", "speed", "20", "30", "30", "50"),
    ("set", "fan", "speed", "100"),
    ("set", "pump", "speed", "90"),
    ("set", "sync", "speed", "55"),
    ("--match", "kraken", "set", "pump", "speed", "20", "30", "30", "50"),
    ("set", "led1", "speed", "90"),
    ("set", "led1", "brightness", "50"),
    ("set", "lcd", "screen", "brightness", "50"),
    ("set", "lcd", "screen", "static", "/tmp/image.png"),
    ("set", "lcd", "screen", "liquid"),
    ("--match", "kraken", "initialize", "--unsafe"),
    ("initialize", "--unsafe"),
    ("--unsafe=smbus", "list"),
    ("--direct-access", "list"),
    ("set", "led1", "color", "fixed", "00aaff", "--unsafe"),
    ("set", "led1", "color", "fixed", "00aaff", "--speed", "turbo"),
    ("set", "led1", "color", "fixed", "00aaff", "--direction", "sideways"),
    ("set", "led1", "color", "fixed", "00aaff", "--brightness", "50"),
    ("set", "led1", "color", "fixed", "00aaff", "not-a-colour"),
    ("set", "led1", "color", "fixed", "00aaff", "ff"),
    ("set", "led1", "color", "fixed", "00aaff", "00aaff00aaff"),
    ("reset",),
    ("download-firmware",),
    ("set", "led1"),
    ("",),
    ("--match",),
    (),
    # Fail closed: a full command line, program name included, is not an argument vector.
    ("liquidctl", "list", "--json"),
    ("liquidctl", "set", "led1", "color", "fixed", "00aaff"),
    ("/usr/bin/liquidctl", "set", "led1", "color", "off"),
]

ALLOWED_ARGUMENTS: list[tuple[str, ...]] = [
    ("list",),
    ("list", "--json"),
    ("status",),
    ("initialize",),
    ("initialize", "all"),
    ("--version",),
    ("--match", "NZXT RGB & Fan Controller", "initialize"),
    ("--match", "NZXT Kraken Z (Z53, Z63 or Z73)", "status", "--json"),
    ("--match", "smart device", "set", "led1", "color", "fixed", "00aaff"),
    ("--match", "kraken", "set", "external", "color", "spectrum-wave"),
    ("set", "led2", "color", "fading", "ff0000", "00ff00", "--speed", "faster"),
    ("set", "led1", "color", "marquee-3", "00aaff", "--direction", "backward"),
    ("set", "led1", "color", "off"),
    ("set", "sync", "color", "fixed", "000000"),
]


@pytest.mark.parametrize("arguments", FORBIDDEN_ARGUMENTS)
def test_forbidden_commands_are_refused(arguments: tuple[str, ...]) -> None:
    with pytest.raises(SafetyViolationError):
        validate_argv(arguments)


@pytest.mark.parametrize("arguments", ALLOWED_ARGUMENTS)
def test_lighting_commands_are_permitted(arguments: tuple[str, ...]) -> None:
    validate_argv(arguments)


def test_a_device_description_containing_fan_is_not_mistaken_for_a_command() -> None:
    """The match pattern for the development machine's controller literally contains "Fan"."""
    validate_argv(("--match", "NZXT RGB & Fan Controller", "set", "led1", "color", "off"))


def test_cooling_commands_are_refused_with_a_reason() -> None:
    with pytest.raises(SafetyViolationError) as info:
        validate_argv(("set", "pump", "speed", "90"))
    assert "out of scope" in (info.value.hint or "")


def test_every_generated_command_passes_the_gate() -> None:
    """Whatever the interface asks for, the gate has the final say — and it agrees."""
    backend = MockBackend()
    devices = backend.discover_devices()
    checked = 0
    for device in devices:
        assert device.profile is not None
        for effect in effects_for_family(device.profile.family):
            colors = tuple(Color(0, 170, 255) for _ in range(max(effect.min_colors, 1)))
            state = LightingState(
                channel=device.profile.led_channels[0],
                effect=effect.id,
                colors=colors,
            )
            arguments = build_set_argv(device, state)
            validate_argv(arguments)
            assert "color" in arguments
            checked += 1
    assert checked == 27 + 30


def test_build_set_argv_sends_dimmed_colours() -> None:
    device = MockBackend().discover_devices()[0]
    state = LightingState(
        channel="led1",
        effect="fixed",
        colors=(Color(0, 170, 255),),
        brightness=50,
    )
    assert build_set_argv(device, state) == (
        "--match",
        "NZXT RGB & Fan Controller",
        "set",
        "led1",
        "color",
        "fixed",
        "005580",
    )


def test_build_set_argv_adds_speed_and_direction_only_when_they_matter() -> None:
    device = MockBackend().discover_devices()[0]
    fixed = build_set_argv(
        device,
        LightingState(
            channel="led1",
            effect="fixed",
            colors=(Color(255, 255, 255),),
            speed="fastest",
            direction="backward",
        ),
    )
    assert "--speed" not in fixed
    assert "--direction" not in fixed

    marquee = build_set_argv(
        device,
        LightingState(
            channel="led1",
            effect="marquee-4",
            colors=(Color(255, 255, 255),),
            speed="faster",
            direction="backward",
        ),
    )
    assert marquee[-4:] == ("--speed", "faster", "--direction", "backward")


def test_other_command_builders_are_read_only() -> None:
    device = MockBackend().discover_devices()[0]
    for arguments in (
        build_list_argv(),
        build_version_argv(),
        build_initialize_argv(device),
        build_status_argv(device),
    ):
        validate_argv(arguments)


def test_the_backend_never_reaches_its_runner_with_a_forbidden_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate runs before the process is started, not after."""
    monkeypatch.setattr(
        "nitor.backend.liquidctl_cli.shutil.which", lambda _name: "/usr/bin/liquidctl"
    )
    calls: list[tuple[str, ...]] = []

    def recorder(argv: tuple[str, ...], timeout: float) -> CommandResult:
        calls.append(argv)
        return CommandResult(argv=argv, returncode=0, stdout="[]", stderr="")

    backend = LiquidctlBackend(runner=recorder)
    with pytest.raises(SafetyViolationError):
        backend._run(("set", "pump", "speed", "90"))
    with pytest.raises(SafetyViolationError):
        backend._run(("set", "fan1", "speed", "100"))
    with pytest.raises(SafetyViolationError):
        backend._run(("set", "lcd", "screen", "liquid"))
    assert calls == []

    backend._run(("list", "--json"))
    assert calls == [("/usr/bin/liquidctl", "list", "--json")]
