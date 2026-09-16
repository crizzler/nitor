"""Starting the graphical application.

The theme is the desktop's own: Qt Quick Controls is pointed at the Plasma style when it is
available, so light/dark appearance and accent colours come from KDE rather than from a hardcoded
palette here.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from nitor import APP_ID, APP_NAME, __version__
from nitor.ui.viewmodel import NitorViewModel

_LOGGER = logging.getLogger(__name__)

PACKAGE_DIRECTORY = Path(__file__).resolve().parent
UI_DIRECTORY = PACKAGE_DIRECTORY / "ui"
ASSET_DIRECTORY = PACKAGE_DIRECTORY / "assets"
MAIN_QML = UI_DIRECTORY / "Main.qml"

#: Plasma's Qt Quick Controls style, which gives Nitor the desktop's light/dark appearance and
#: accent colours without hardcoding a palette. It is provided by the ``qqc2-desktop-style`` package.
PLASMA_STYLE = "org.kde.desktop"
_PLASMA_STYLE_MODULE = ("org", "kde", "desktop")
_FALLBACK_IMPORT_PATHS = (Path("/usr/lib/qt6/qml"), Path("/usr/lib64/qt6/qml"))


def qml_import_paths() -> list[Path]:
    """Where Qt looks for QML modules, plus the usual system locations."""
    paths: list[Path] = []
    try:
        from PySide6.QtCore import QLibraryInfo

        paths.append(Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath)))
    except Exception as error:
        _LOGGER.debug("could not ask Qt for its QML import path: %s", error)
    paths.extend(_FALLBACK_IMPORT_PATHS)
    return paths


def preferred_quick_style() -> str | None:
    """The Plasma style to use, or ``None`` to leave Qt's default alone.

    PySide6 does not expose Qt's style enumeration, so the style is looked for on disk. If the
    desktop already asked for a style, that choice is respected: on KDE it will already be Plasma.
    """
    if os.environ.get("QT_QUICK_CONTROLS_STYLE", "").strip():
        return None
    for import_path in qml_import_paths():
        module = import_path.joinpath(*_PLASMA_STYLE_MODULE)
        if (module / "qmldir").is_file():
            return PLASMA_STYLE
    _LOGGER.debug("no Plasma Qt Quick Controls style found; using Qt's default")
    return None


def apply_quick_style() -> None:
    """Point Qt Quick Controls at the Plasma style when it is available."""
    style = preferred_quick_style()
    if style is None:
        return
    try:
        from PySide6.QtQuickControls2 import QQuickStyle

        QQuickStyle.setStyle(style)
        _LOGGER.debug("using the %s Qt Quick Controls style", style)
    except Exception as error:
        _LOGGER.debug("could not select the %s style: %s", style, error)


def create_application(argv: list[str]) -> QGuiApplication:
    """Build the QGuiApplication with the identity KDE needs to group windows correctly."""
    QGuiApplication.setDesktopFileName(APP_ID)
    application = QGuiApplication(argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationDisplayName(APP_NAME)
    application.setApplicationVersion(__version__)
    application.setOrganizationDomain("github.com")
    application.setOrganizationName("crizzler")

    icon_path = ASSET_DIRECTORY / "icon.svg"
    if icon_path.is_file():
        application.setWindowIcon(QIcon(str(icon_path)))
    return application


def load_interface(view_model: NitorViewModel) -> QQmlApplicationEngine:
    """Load the QML interface, raising a clear error if it cannot be built."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("app", view_model)
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
    if not engine.rootObjects():
        raise RuntimeError(
            "The user interface could not be loaded. The QML errors above explain why."
        )
    return engine


def run(argv: list[str] | None = None) -> int:
    """Run the application until the window is closed."""
    apply_quick_style()
    application = create_application(list(sys.argv if argv is None else argv))

    view_model = NitorViewModel()
    engine = load_interface(view_model)  # noqa: F841 - the engine must outlive this call
    application.aboutToQuit.connect(view_model.shutdown)

    return application.exec()


__all__ = [
    "ASSET_DIRECTORY",
    "MAIN_QML",
    "PLASMA_STYLE",
    "apply_quick_style",
    "create_application",
    "load_interface",
    "preferred_quick_style",
    "qml_import_paths",
    "run",
]
