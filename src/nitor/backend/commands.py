"""Building and vetting the exact command lines handed to liquidctl.

This module is the cooling safety boundary. Everything the application ever executes is built here,
and every built command line must pass :func:`validate_argv` before it is run. The validator accepts
four shapes and nothing else:

* ``list``
* ``initialize`` (optionally ``initialize all``)
* ``status``
* ``set <channel> color <effect> [<colour> ...] [--speed <value>] [--direction <value>]``

Anything else raises :class:`SafetyViolationError`. That is what stops ``set fan1 speed 90``,
``set pump speed 90``, ``set sync speed 55`` and ``initialize --unsafe`` from ever reaching a pump,
a fan or the firmware, no matter what happens higher up the stack.

The module is deliberately pure: it imports no subprocess machinery and can be tested exhaustively.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from nitor.domain import (
    Device,
    LightingState,
    NotSupportedError,
    SafetyViolationError,
    validate_request,
)
from nitor.domain.effects import DIRECTIONS, SPEEDS

#: Global options that take a value. Their values are opaque text and are never inspected as
#: commands, which is what allows a device description such as "RGB & Fan Controller" to be passed
#: as a match pattern without tripping the cooling check.
GLOBAL_FLAGS_WITH_VALUE: Final[frozenset[str]] = frozenset(
    {"--match", "--pick", "--bus", "--address", "--serial"}
)

#: Global options that take no value. ``--version`` is allowed because it is read-only and is how
#: backend availability is probed.
GLOBAL_FLAGS: Final[frozenset[str]] = frozenset({"--json", "--verbose", "--version"})

#: Options the lighting command may carry.
ALLOWED_SET_FLAGS: Final[dict[str, frozenset[str]]] = {
    "--speed": frozenset(SPEEDS),
    "--direction": frozenset(DIRECTIONS),
}

#: Read-only commands.
READ_COMMANDS: Final[frozenset[str]] = frozenset({"list", "initialize", "status"})

SET_COMMAND: Final = "set"
COLOR_SUBCOMMAND: Final = "color"


def build_version_argv() -> tuple[str, ...]:
    return ("--version",)


def build_list_argv() -> tuple[str, ...]:
    return ("list", "--json")


def build_initialize_argv(device: Device) -> tuple[str, ...]:
    return ("--match", device.description, "initialize")


def build_status_argv(device: Device) -> tuple[str, ...]:
    return ("--match", device.description, "status", "--json")


def build_set_argv(
    device: Device,
    state: LightingState,
) -> tuple[str, ...]:
    """Build the ``set … color …`` command line for a device and a lighting state.

    The state is validated against the device's own effect limits first, so the command can never
    ask the firmware for something it would silently ignore.
    """
    if device.profile is None:
        raise NotSupportedError(
            f"{device.display_name} is not a lighting device Nitor knows how to control."
        )
    if not device.profile.controllable:
        raise NotSupportedError(
            device.profile.note or f"{device.display_name} does not support lighting control."
        )

    # Brightness is applied here as software dimming, so the colours that reach the hardware are the
    # dimmed ones and the command line is an exact record of what the LEDs will show.
    colors_to_send = state.effective_colors()

    validated = validate_request(
        device.profile.family,
        state.effect,
        colors_to_send,
        state.speed,
        state.direction,
    )

    if not state.channel:
        raise NotSupportedError("No LED channel was selected.")

    argv: list[str] = [
        "--match",
        device.description,
        SET_COMMAND,
        state.channel,
        COLOR_SUBCOMMAND,
        validated.effect.id,
    ]
    argv.extend(color.to_liquidctl() for color in validated.colors)
    if validated.effect.supports_speed:
        argv.extend(["--speed", validated.speed])
    if validated.effect.supports_direction:
        argv.extend(["--direction", validated.direction])
    return tuple(argv)


def validate_argv(argv: Sequence[str]) -> None:
    """Raise :class:`SafetyViolationError` unless ``argv`` is a permitted lighting command.

    ``argv`` is a liquidctl *argument vector*: the program name is added by the process runner
    afterwards. A command line that still carries the program name is refused, because its first
    token cannot be a command — failing closed is the only acceptable direction here.
    """
    tokens = list(argv)
    if not tokens:
        raise SafetyViolationError("Refusing to run an empty command.")

    remainder = _strip_global_flags(tokens)
    if not remainder:
        if "--version" in tokens:
            return
        raise SafetyViolationError(f"'{' '.join(tokens)}' contains no command.")

    command = remainder[0]
    if command in READ_COMMANDS:
        _validate_read_command(command, remainder[1:], tokens)
        return

    if command != SET_COMMAND:
        raise SafetyViolationError(
            f"Refusing to run the '{command}' command.",
            hint="Nitor only ever runs list, initialize, status and LED colour commands.",
        )

    _validate_set_command(remainder[1:], tokens)


def _strip_global_flags(tokens: list[str]) -> list[str]:
    """Drop leading global options, returning the command and its arguments."""
    index = 0
    while index < len(tokens) and tokens[index].startswith("--"):
        flag = tokens[index]
        if flag in GLOBAL_FLAGS_WITH_VALUE:
            if index + 1 >= len(tokens):
                raise SafetyViolationError(f"'{flag}' was given without a value.")
            index += 2
        elif flag in GLOBAL_FLAGS:
            index += 1
        else:
            raise SafetyViolationError(
                f"Refusing to run a command with the '{flag}' option.",
                hint="Nitor does not use unsafe or direct-access mode.",
            )
    return tokens[index:]


def _validate_read_command(command: str, arguments: list[str], tokens: list[str]) -> None:
    """Read-only commands may carry value-less global flags, and ``all`` for initialize.

    Anything else — ``--unsafe`` above all — is refused, which is why the allowed set is built from
    the global flag list rather than from a deny list.
    """
    allowed = set(GLOBAL_FLAGS)
    if command == "initialize":
        allowed.add("all")
    unexpected = [argument for argument in arguments if argument not in allowed]
    if unexpected:
        raise SafetyViolationError(
            f"Refusing to run '{command} {' '.join(unexpected)}'.",
            hint="Nitor initialises devices only, never with unsafe or firmware options.",
        )


def _validate_set_command(arguments: list[str], tokens: list[str]) -> None:
    """Require ``<channel> color <effect> …``, the only shape lighting commands take."""
    if len(arguments) < 3:
        raise SafetyViolationError(
            f"Refusing to run an incomplete command: '{' '.join(tokens)}'.",
            hint="LED commands must set a colour, for example 'set led1 color fixed 00aaff'.",
        )

    channel, subcommand, effect = arguments[0], arguments[1], arguments[2]
    if subcommand != COLOR_SUBCOMMAND:
        raise SafetyViolationError(
            f"Refusing to run 'set {channel} {subcommand} …'.",
            hint=(
                "Nitor changes LED colours only. Fan and pump control are deliberately out of "
                "scope, so speed, firmware and screen commands are refused."
            ),
        )
    if not channel or not effect:
        raise SafetyViolationError("Refusing to run an incomplete LED command.")

    _validate_set_arguments(arguments[3:], tokens)


def _validate_set_arguments(arguments: list[str], tokens: list[str]) -> None:
    """Check the colours and options that follow the effect name."""
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token.startswith("--"):
            allowed_values = ALLOWED_SET_FLAGS.get(token)
            if allowed_values is None:
                raise SafetyViolationError(
                    f"Refusing to run a colour command with the '{token}' option.",
                )
            if index + 1 >= len(arguments):
                raise SafetyViolationError(f"'{token}' was given without a value.")
            value = arguments[index + 1]
            if value not in allowed_values:
                raise SafetyViolationError(
                    f"'{value}' is not a valid value for '{token}'.",
                    hint=f"Valid values: {', '.join(sorted(allowed_values))}.",
                )
            index += 2
            continue

        if not _is_color_token(token):
            raise SafetyViolationError(
                f"Refusing to run a colour command containing '{token}'.",
                hint=f"Offending command: {' '.join(tokens)}",
            )
        index += 1


def _is_color_token(token: str) -> bool:
    """Whether a token is a plain ``rrggbb`` colour, the only form Nitor generates."""
    if len(token) != 6:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in token)


__all__ = [
    "ALLOWED_SET_FLAGS",
    "GLOBAL_FLAGS",
    "GLOBAL_FLAGS_WITH_VALUE",
    "READ_COMMANDS",
    "build_initialize_argv",
    "build_list_argv",
    "build_set_argv",
    "build_status_argv",
    "build_version_argv",
    "validate_argv",
]
