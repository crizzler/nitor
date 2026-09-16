"""The startup service: rendering the unit, and enabling/disabling it with a fake systemctl."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from nitor.domain import AutostartError
from nitor.services.autostart import (
    ENVIRONMENT_PLACEHOLDER,
    EXEC_PLACEHOLDER,
    AutostartManager,
    CommandOutcome,
    default_environment,
    default_exec_start,
    load_unit_template,
    render_unit,
)

TEMPLATE = """[Unit]
Description=test unit

[Service]
Type=oneshot
ExecStart=@@EXEC_START@@ --apply-saved
@@ENVIRONMENT@@
NoNewPrivileges=yes

[Install]
WantedBy=default.target
"""


class FakeSystemctl:
    """Records calls and answers the two queries the manager makes."""

    def __init__(self, *, enabled: bool = False, failing: set[str] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.enabled = enabled
        self.failing = failing or set()

    def __call__(self, argv: tuple[str, ...]) -> CommandOutcome:
        self.calls.append(tuple(argv))
        verb = argv[2] if len(argv) > 2 else ""
        if verb in self.failing:
            return CommandOutcome(argv=argv, returncode=1, stderr="simulated failure")
        if verb == "is-enabled":
            state = "enabled" if self.enabled else "disabled"
            return CommandOutcome(
                argv=argv, returncode=0 if self.enabled else 1, stdout=state + "\n"
            )
        if verb == "enable":
            self.enabled = True
        elif verb == "disable":
            self.enabled = False
        return CommandOutcome(argv=argv, returncode=0)

    @property
    def verbs(self) -> list[str]:
        return [call[2] for call in self.calls]


def manager(tmp_path: Path, runner: FakeSystemctl, **overrides: object) -> AutostartManager:
    arguments: dict[str, object] = {
        "unit_directory": tmp_path / "systemd" / "user",
        "exec_start": "/usr/bin/nitor",
        "environment": [],
        "runner": runner,
        "template": TEMPLATE,
    }
    arguments.update(overrides)
    return AutostartManager(**arguments)  # type: ignore[arg-type]


def test_render_unit_substitutes_the_command() -> None:
    text = render_unit(TEMPLATE, exec_start="/usr/bin/nitor", environment=[])
    assert "ExecStart=/usr/bin/nitor --apply-saved" in text
    assert EXEC_PLACEHOLDER not in text
    assert ENVIRONMENT_PLACEHOLDER not in text


def test_render_unit_omits_the_environment_line_when_there_is_nothing_to_add() -> None:
    text = render_unit(TEMPLATE, exec_start="/usr/bin/nitor", environment=[])
    assert "@@" not in text
    assert "Environment" not in text
    assert "\n\n\n" not in text


def test_render_unit_adds_environment_lines() -> None:
    text = render_unit(
        TEMPLATE,
        exec_start="python -m nitor",
        environment=["Environment=PYTHONPATH=/home/someone/project/src"],
    )
    assert "Environment=PYTHONPATH=/home/someone/project/src" in text
    assert "ExecStart=python -m nitor --apply-saved" in text


def test_the_packaged_unit_uses_the_expected_placeholders() -> None:
    template = load_unit_template()
    assert EXEC_START_MARKER in template, "the packaged unit lost its ExecStart placeholder"
    assert "Type=oneshot" in template
    assert "WantedBy=default.target" in template


EXEC_START_MARKER = "ExecStart=@@EXEC_START@@"


def test_unit_text_is_built_from_the_template(tmp_path: Path) -> None:
    instance = manager(tmp_path, FakeSystemctl())
    text = instance.unit_text()
    assert "ExecStart=/usr/bin/nitor --apply-saved" in text


def test_enabling_writes_the_unit_and_asks_systemd_to_use_it(tmp_path: Path) -> None:
    runner = FakeSystemctl()
    instance = manager(tmp_path, runner)

    state = instance.enable()

    assert instance.unit_path.is_file()
    assert "ExecStart=/usr/bin/nitor --apply-saved" in instance.unit_path.read_text()
    assert runner.verbs == ["daemon-reload", "enable", "is-enabled"]
    assert state.installed is True
    assert state.enabled is True
    assert state.active is True


def test_enabling_without_systemd_is_refused_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nitor.services.autostart.shutil.which", lambda _name: None)
    instance = manager(tmp_path, FakeSystemctl())
    assert instance.supported() is False
    with pytest.raises(AutostartError) as info:
        instance.enable()
    assert info.value.hint is not None


def test_a_failing_enable_surfaces_the_reason(tmp_path: Path) -> None:
    runner = FakeSystemctl(failing={"enable"})
    instance = manager(tmp_path, runner)
    with pytest.raises(AutostartError) as info:
        instance.enable()
    assert info.value.detail == "simulated failure"


def test_disabling_removes_the_unit_again(tmp_path: Path) -> None:
    runner = FakeSystemctl(enabled=True)
    instance = manager(tmp_path, runner)
    instance.enable()
    runner.calls.clear()

    state = instance.disable()

    assert runner.verbs == ["disable", "daemon-reload", "is-enabled"]
    assert instance.unit_path.exists() is False
    assert state.enabled is False


def test_state_reports_a_disabled_service_that_still_exists(tmp_path: Path) -> None:
    runner = FakeSystemctl()
    instance = manager(tmp_path, runner)
    instance.enable()
    runner.enabled = False

    state = instance.state()

    assert state.installed is True
    assert state.enabled is False
    assert state.detail


def test_state_reports_missing_systemd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nitor.services.autostart.shutil.which", lambda _name: None)
    state = manager(tmp_path, FakeSystemctl()).state()
    assert state.supported is False
    assert state.active is False
    assert "systemd" in state.detail


def test_the_default_command_prefers_an_installed_nitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nitor.services.autostart.shutil.which", lambda name: f"/usr/bin/{name}")
    assert default_exec_start() == "/usr/bin/nitor"


def test_the_default_command_falls_back_to_this_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nitor.services.autostart.shutil.which", lambda _name: None)
    assert default_exec_start() == f"{sys.executable} -m nitor"


def test_a_source_checkout_gets_a_pythonpath_line() -> None:
    """When running from a checkout the unit needs PYTHONPATH, otherwise it cannot import Nitor."""
    environment = default_environment()
    assert isinstance(environment, list)
    for line in environment:
        assert line.startswith("Environment=PYTHONPATH=")
        assert Path(line.split("=", 2)[2]).name == "src"
