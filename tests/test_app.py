"""The application bootstrap, in particular how the view model reaches the interface.

The view model is passed to QML as an *initial property* rather than installed as a context
property. That distinction is the reason the QML is statically checkable: a context property is
invisible to ``qmllint`` and to the QML compiler, so every access to it becomes an "unqualified
access" warning and the tooling gives up on type checking. This test fails if that wiring is
reverted.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Must be set before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QGuiApplication

from nitor import APP_NAME
from nitor.app import load_interface
from nitor.backend.mock import MockBackend
from nitor.services.autostart import AutostartManager, CommandOutcome
from nitor.services.settings import SettingsStore
from nitor.ui.viewmodel import NitorViewModel


@pytest.fixture(scope="module")
def qt_application() -> QGuiApplication:
    application = QGuiApplication.instance()
    if application is None:
        application = QGuiApplication(["nitor-tests"])
    return application


class SilentSystemctl:
    """Answers systemctl without touching the machine's real user services."""

    def __call__(self, argv: tuple[str, ...]) -> CommandOutcome:
        return CommandOutcome(argv=argv, returncode=1, stdout="disabled\n")


@pytest.fixture
def view_model(qt_application: QGuiApplication, tmp_path: Path) -> NitorViewModel:
    model = NitorViewModel(
        MockBackend(),
        store=SettingsStore(tmp_path / "config.json"),
        autostart=AutostartManager(
            unit_directory=tmp_path / "systemd" / "user",
            exec_start="/usr/bin/nitor",
            environment=[],
            runner=SilentSystemctl(),  # type: ignore[arg-type]
        ),
    )
    yield model
    model.shutdown()


def test_the_view_model_reaches_qml_without_warnings(view_model: NitorViewModel) -> None:
    """Both halves matter: the interface must see the view model, and must load silently.

    A context property would satisfy the first half while failing the second, because every access
    to it is reported as an unqualified access by the tooling. Loading quietly is therefore asserted
    here as well.
    """
    messages: list[str] = []
    previous = qInstallMessageHandler(lambda _mode, _context, message: messages.append(message))
    engine = None
    try:
        engine = load_interface(view_model)
        roots = engine.rootObjects()
        assert roots, "the interface did not load"
        assert not messages, f"the interface emitted messages while loading: {messages}"

        root = roots[0]
        assert root.property("app") is not None, "the view model was not passed to the interface"
        # The window title is bound to the view model, so this proves the interface sees it.
        assert root.property("title") == APP_NAME
    finally:
        qInstallMessageHandler(previous)
        # Dropped while the view model is still alive, so teardown cannot be mistaken for a defect.
        engine = None
        application = QGuiApplication.instance()
        if application is not None:
            application.processEvents()


def test_every_page_declares_the_view_model_it_is_given() -> None:
    """Each page receives the view model as an explicit property rather than guessing at it."""
    pages = Path(__file__).resolve().parents[1] / "src" / "nitor" / "ui" / "pages"
    for page in sorted(pages.glob("*.qml")):
        assert "required property var app" in page.read_text(encoding="utf-8"), page.name
