"""The per-user startup service that reapplies saved lighting at login.

A ``systemd --user`` oneshot unit is written to ``~/.config/systemd/user/nitor.service`` and
enabled with ``systemctl --user``. No root daemon, nothing resident: the unit applies the saved
lighting once and exits.

Note that this module starts processes (``systemctl``) as well as the hardware backend. It is the
only other place that does so, it never runs ``sudo``, and it is isolated here so the rule "produce
a command line, then run it" stays auditable.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Final

from nitor.domain import AutostartError

_LOGGER = logging.getLogger(__name__)

UNIT_NAME: Final = "nitor.service"
UNIT_TEMPLATE_NAME: Final = "nitor.service"
EXEC_PLACEHOLDER: Final = "@@EXEC_START@@"
ENVIRONMENT_PLACEHOLDER: Final = "@@ENVIRONMENT@@"
SYSTEMCTL_TIMEOUT: Final = 20.0

Runner = Callable[[Sequence[str]], "CommandOutcome"]


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """The result of a systemctl call."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout or self.stderr).strip()


@dataclass(frozen=True, slots=True)
class AutostartState:
    """Whether lighting will be reapplied at login."""

    supported: bool
    installed: bool
    enabled: bool
    detail: str = ""

    @property
    def active(self) -> bool:
        return self.installed and self.enabled


def run_systemctl(argv: Sequence[str]) -> CommandOutcome:
    """Run one systemctl command for the current user."""
    completed = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=SYSTEMCTL_TIMEOUT,
        check=False,
    )
    return CommandOutcome(
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def default_unit_directory() -> Path:
    """Where user units live, honouring ``XDG_CONFIG_HOME``."""
    base = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(base) if base else Path.home() / ".config"
    return root / "systemd" / "user"


def default_exec_start() -> str:
    """How the service should start Nitor.

    An installed ``nitor`` executable is preferred; otherwise the current interpreter is used, which
    is what happens when running from a source checkout.
    """
    installed = shutil.which("nitor")
    if installed:
        return installed
    return f"{sys.executable} -m nitor"


def default_environment() -> list[str]:
    """Extra unit lines needed to make a source checkout importable."""
    import nitor

    package_directory = Path(nitor.__file__).resolve().parent
    source_directory = package_directory.parent
    if source_directory.name != "src":
        return []
    return [f"Environment=PYTHONPATH={source_directory}"]


def load_unit_template() -> str:
    """Read the packaged unit file."""
    template = resources.files("nitor").joinpath("data", UNIT_TEMPLATE_NAME)
    try:
        return template.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError) as error:  # pragma: no cover - packaging fault
        raise AutostartError(
            "The packaged startup service definition is missing.",
            detail=str(error),
        ) from error


def render_unit(
    template: str,
    *,
    exec_start: str,
    environment: Sequence[str] = (),
) -> str:
    """Substitute the two placeholders in the unit template."""
    lines: list[str] = []
    for line in template.splitlines():
        if ENVIRONMENT_PLACEHOLDER in line:
            lines.extend(environment)
            continue
        lines.append(line.replace(EXEC_PLACEHOLDER, exec_start))
    rendered = "\n".join(lines)
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


class AutostartManager:
    """Installs, enables and disables the startup service."""

    def __init__(
        self,
        *,
        unit_directory: Path | None = None,
        exec_start: str | None = None,
        environment: Sequence[str] | None = None,
        runner: Runner | None = None,
        template: str | None = None,
    ) -> None:
        self._unit_directory = (
            unit_directory if unit_directory is not None else default_unit_directory()
        )
        self._exec_start = exec_start
        self._environment = environment
        self._runner = runner or run_systemctl
        self._template = template

    # -- paths and text -------------------------------------------------------------------

    @property
    def unit_path(self) -> Path:
        return self._unit_directory / UNIT_NAME

    def unit_text(self) -> str:
        template = self._template if self._template is not None else load_unit_template()
        exec_start = self._exec_start or default_exec_start()
        environment = (
            list(self._environment) if self._environment is not None else default_environment()
        )
        return render_unit(template, exec_start=exec_start, environment=environment)

    # -- state ----------------------------------------------------------------------------

    def supported(self) -> bool:
        """Whether this system can manage user services at all."""
        return shutil.which("systemctl") is not None

    def state(self) -> AutostartState:
        """Report whether the service is installed and enabled."""
        if not self.supported():
            return AutostartState(
                supported=False,
                installed=False,
                enabled=False,
                detail="systemd is not available on this system.",
            )

        installed = self.unit_path.is_file()
        result = self._systemctl("is-enabled", UNIT_NAME)
        enabled = result.ok and result.output.strip() in {"enabled", "enabled-runtime"}
        detail = "" if enabled else result.output
        if installed and not enabled and not detail:
            detail = "The service exists but is not enabled."

        return AutostartState(
            supported=True,
            installed=installed,
            enabled=enabled,
            detail=detail,
        )

    # -- changes --------------------------------------------------------------------------

    def enable(self) -> AutostartState:
        """Write the unit, reload systemd and enable the service."""
        if not self.supported():
            raise AutostartError(
                "This system does not use systemd, so lighting cannot be reapplied at login.",
                hint="Start Nitor at login from your desktop's own autostart settings instead.",
            )

        self._write_unit()
        self._reload()
        result = self._systemctl("enable", UNIT_NAME)
        if not result.ok:
            raise AutostartError(
                "The lighting service could not be enabled.",
                detail=result.output,
            )
        _LOGGER.info("enabled %s", UNIT_NAME)
        return self.state()

    def disable(self) -> AutostartState:
        """Disable the service and remove the unit file again."""
        if not self.supported():
            raise AutostartError("This system does not use systemd.")

        result = self._systemctl("disable", UNIT_NAME)
        if not result.ok and self.unit_path.is_file():
            raise AutostartError(
                "The lighting service could not be disabled.",
                detail=result.output,
            )
        self.unit_path.unlink(missing_ok=True)
        self._reload()
        _LOGGER.info("disabled %s", UNIT_NAME)
        return self.state()

    def _write_unit(self) -> None:
        text = self.unit_text()
        try:
            self._unit_directory.mkdir(parents=True, exist_ok=True)
            self.unit_path.write_text(text, encoding="utf-8")
        except OSError as error:
            raise AutostartError(
                "The startup service file could not be written.",
                detail=f"{self.unit_path}: {error}",
            ) from error

    def _reload(self) -> None:
        result = self._systemctl("daemon-reload")
        if not result.ok:
            raise AutostartError(
                "systemd could not reload its configuration.",
                detail=result.output,
            )

    def _systemctl(self, *arguments: str) -> CommandOutcome:
        argv = ("systemctl", "--user", *arguments)
        try:
            return self._runner(argv)
        except FileNotFoundError as error:
            raise AutostartError(
                "systemctl is not available on this system.",
                detail=str(error),
            ) from error
        except subprocess.TimeoutExpired as error:  # pragma: no cover - defensive
            raise AutostartError(
                "systemctl did not respond.",
                detail=str(error),
            ) from error


__all__ = [
    "EXEC_PLACEHOLDER",
    "UNIT_NAME",
    "AutostartManager",
    "AutostartState",
    "CommandOutcome",
    "default_unit_directory",
    "load_unit_template",
    "render_unit",
    "run_systemctl",
]
