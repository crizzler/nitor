"""Packaging: everything the application reads at runtime has to reach the wheel.

The interface, the icons and the unit template are data rather than Python, so setuptools only
includes them because ``package-data`` says so. Forgetting a line there is invisible from a source
checkout — the QML loads straight from the tree and everything appears to work — but produces an
installed application that cannot open a window at all. That is exactly what happened once, so it is
checked here rather than trusted.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "nitor"


def package_data_patterns() -> list[str]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        configuration = tomllib.load(handle)
    patterns = configuration["tool"]["setuptools"]["package-data"]["nitor"]
    assert isinstance(patterns, list) and patterns
    return patterns


def covered_files() -> set[Path]:
    """Resolve the package-data patterns the way setuptools does."""
    covered: set[Path] = set()
    for pattern in package_data_patterns():
        for match in PACKAGE_ROOT.glob(pattern):
            if match.is_file():
                covered.add(match.resolve())
    return covered


def test_every_qml_file_is_packaged() -> None:
    """A wheel without QML installs an application that cannot start."""
    interface_files = sorted((PACKAGE_ROOT / "ui").rglob("*.qml"))
    assert interface_files, "no QML found; has the interface moved?"

    covered = covered_files()
    missing = [path for path in interface_files if path.resolve() not in covered]
    assert not missing, f"not covered by package-data: {[path.name for path in missing]}"


def test_the_icon_set_is_packaged() -> None:
    """The desktop entry and the window icon are looked up by name."""
    icons = sorted((PACKAGE_ROOT / "assets" / "icons").rglob("*.png"))
    assert icons

    covered = covered_files()
    missing = [path for path in icons if path.resolve() not in covered]
    assert not missing, f"icon sizes missing from the wheel: {[path.name for path in missing]}"

    scalable = PACKAGE_ROOT / "assets" / "icon.svg"
    assert scalable.resolve() in covered, "the scalable icon is not packaged"


def test_the_desktop_files_are_packaged() -> None:
    """The desktop entry, AppStream metadata and unit template are read from the package."""
    for name in (
        "io.github.crizzler.Nitor.desktop",
        "io.github.crizzler.Nitor.metainfo.xml",
        "nitor.service",
    ):
        path = PACKAGE_ROOT / "data" / name
        assert path.is_file(), f"{name} is missing from the source tree"
        assert path.resolve() in covered_files(), f"{name} is not packaged"


def test_the_interface_is_loaded_from_inside_the_package() -> None:
    """app.py resolves Main.qml relative to the package, so that file has to travel with it."""
    pytest.importorskip("PySide6")

    from nitor.app import MAIN_QML

    assert MAIN_QML.is_file(), f"{MAIN_QML} does not exist"
    assert PACKAGE_ROOT.resolve() in MAIN_QML.resolve().parents, (
        f"{MAIN_QML} is outside the package; an installed copy would not find it"
    )
