"""The real backend: liquidctl, executed as a subprocess.

liquidctl is used as a separate process rather than an imported library because it is licensed
GPL-3.0-or-later while this project is MIT: running a program is aggregation, importing it is not.

Every command line goes through :func:`nitor.backend.commands.validate_argv` before execution, so
this module — the only place in the application that starts a process for hardware access — cannot
reach a fan, a pump or the firmware.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar

from nitor.domain import (
    BackendMissingError,
    Device,
    HardwareError,
    LightingState,
    NitorError,
)
from nitor.domain.effects import DEFAULT_DIRECTION, DEFAULT_SPEED

from .base import AppliedLighting, BackendStatus, HardwareBackend
from .commands import (
    build_initialize_argv,
    build_list_argv,
    build_set_argv,
    build_version_argv,
    validate_argv,
)
from .liquidctl_parser import (
    channels_from_report,
    classify_failure,
    ensure_supported,
    parse_device_list,
    parse_initialize_output,
    parse_tree,
    parse_version,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
INSTALL_COMMAND = "sudo pacman -S liquidctl"

CommandRunner = Callable[[Sequence[str], float], "CommandResult"]


@dataclass(frozen=True, slots=True)
class CommandResult:
    """The outcome of one liquidctl invocation."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def command_line(self) -> str:
        return " ".join(self.argv)


def run_process(argv: Sequence[str], timeout: float) -> CommandResult:
    """Run a command and capture its output. The only process runner in the application."""
    environment = {
        **os.environ,
        # Keep messages parseable: liquidctl localises some output otherwise.
        "LANG": "C",
        "LC_ALL": "C",
    }
    completed = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment,
        check=False,
    )
    return CommandResult(
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


class LiquidctlBackend(HardwareBackend):
    """Drives supported NZXT devices through the liquidctl command line interface."""

    name: ClassVar[str] = "liquidctl"
    is_mock: ClassVar[bool] = False

    def __init__(
        self,
        executable: str = "liquidctl",
        *,
        timeout: float = DEFAULT_TIMEOUT,
        runner: CommandRunner | None = None,
    ) -> None:
        self._executable = executable
        self._timeout = timeout
        self._runner = runner or run_process
        self._cached_status: BackendStatus | None = None

    # -- availability ---------------------------------------------------------------------

    @property
    def executable_path(self) -> str | None:
        """Absolute path of the liquidctl program, or ``None`` when it is not installed."""
        return shutil.which(self._executable)

    @property
    def status(self) -> BackendStatus:
        if self._cached_status is None:
            self._cached_status = self._detect_status()
        return self._cached_status

    def refresh(self) -> BackendStatus:
        """Re-probe availability. Used by the "Check again" button."""
        self._cached_status = None
        return self.status

    def _detect_status(self) -> BackendStatus:
        path = self.executable_path
        if path is None:
            return BackendStatus(
                name=self.name,
                available=False,
                summary="Lighting backend not installed",
                hint=(
                    "Nitor uses liquidctl to communicate safely with supported NZXT controllers. "
                    "It is not installed, so the LEDs cannot be reached."
                ),
                install_command=INSTALL_COMMAND,
            )

        version: str | None = None
        try:
            result = self._run(build_version_argv())
            version = parse_version(result.stdout) or parse_version(result.stderr)
        except NitorError as error:
            _LOGGER.warning("could not read the liquidctl version: %s", error)

        available_text = f"liquidctl {version}" if version else "liquidctl"
        return BackendStatus(
            name=self.name,
            available=True,
            version=version,
            summary=available_text,
        )

    # -- operations -----------------------------------------------------------------------

    def discover_devices(self) -> list[Device]:
        """List supported devices. This only reads USB descriptors, so it needs no permissions."""
        result = self._run(build_list_argv())
        return parse_device_list(result.stdout)

    def initialize_device(self, device: Device) -> Device:
        """Ask the controller to detect its accessories and report its firmware version."""
        ensure_supported(device)
        result = self._run(build_initialize_argv(device))

        payload = result.stdout if parse_tree(result.stdout) else result.stderr
        profile = device.profile
        channel_ids = profile.led_channels if profile else ()
        report = parse_initialize_output(tuple(channel_ids), payload)

        _LOGGER.info(
            "initialised %s (firmware %s, accessories %s)",
            device.display_name,
            report.firmware or "unknown",
            {name: list(items) for name, items in report.accessories.items()},
        )
        return device.with_channels(channels_from_report(device, report), firmware=report.firmware)

    def apply_lighting(self, device: Device, state: LightingState) -> AppliedLighting:
        """Apply channel, effect, colours, speed and direction in a single call."""
        ensure_supported(device)
        arguments = build_set_argv(device, state)
        self._run(arguments)

        _LOGGER.info(
            "applied %s on %s (%s)",
            state.effect,
            state.channel,
            ", ".join(color.to_hex() for color in state.effective_colors()) or "no colour",
        )
        return AppliedLighting(
            device_key=device.key,
            channel=state.channel,
            effect=state.effect,
            colors=state.effective_colors(),
            speed=state.speed or DEFAULT_SPEED,
            direction=state.direction or DEFAULT_DIRECTION,
            argv=arguments,
        )

    # -- internals ------------------------------------------------------------------------

    def _require_executable(self) -> str:
        path = self.executable_path
        if path is None:
            raise BackendMissingError(
                "The lighting backend (liquidctl) is not installed.",
                hint=f"Install it with: {INSTALL_COMMAND}",
            )
        return path

    def _run(self, arguments: Sequence[str]) -> CommandResult:
        """Validate one argument vector, then execute it with the liquidctl program."""
        validate_argv(arguments)
        argv = (self._require_executable(), *arguments)
        _LOGGER.debug("executing: %s", " ".join(argv))
        try:
            result = self._runner(argv, self._timeout)
        except FileNotFoundError as error:
            raise BackendMissingError(
                "The lighting backend (liquidctl) is not installed.",
                hint=f"Install it with: {INSTALL_COMMAND}",
                detail=str(error),
            ) from error
        except subprocess.TimeoutExpired as error:
            raise HardwareError(
                "The controller did not respond in time.",
                hint="Unplugging and reconnecting it usually clears this.",
                detail=f"timed out after {self._timeout:g}s",
            ) from error
        except OSError as error:
            raise HardwareError(
                "The lighting backend could not be started.",
                detail=str(error),
            ) from error

        if not result.ok:
            raise classify_failure(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result


__all__ = ["CommandResult", "LiquidctlBackend", "run_process"]
