#!/usr/bin/env python3
"""Render the hicolor icon set from the source SVG.

Qt is already a dependency of this project, so no extra tooling is needed. The generated PNGs are
committed, because packaging must not depend on running this script.

Usage::

    python3 tools/render-icons.py [--output DIR] [--force]

Sizes cover what desktops actually ask for, including the 16px and 22px cases used by panels and
task bars, where a mark either reads or does not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SVG = PROJECT_ROOT / "src" / "nitor" / "assets" / "icon.svg"
DEFAULT_OUTPUT = PROJECT_ROOT / "src" / "nitor" / "assets" / "icons" / "hicolor"
ICON_NAME = "io.github.crizzler.Nitor"

#: The sizes freedesktop.org expects, plus 22 and 24 for panels.
SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 256, 512)


def render(source: Path, output_root: Path, sizes: tuple[int, ...], force: bool) -> list[Path]:
    try:
        from PySide6.QtCore import QSize, Qt
        from PySide6.QtGui import QGuiApplication, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except ImportError as error:  # pragma: no cover - PySide6 is a runtime dependency
        print(f"PySide6 is required to render icons: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    # A QGuiApplication is needed before creating images; offscreen keeps this usable in CI.
    application = QGuiApplication.instance() or QGuiApplication(["render-icons"])
    del application

    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise SystemExit(f"Could not read the source icon: {source}")

    written: list[Path] = []
    for size in sizes:
        directory = output_root / f"{size}x{size}" / "apps"
        target = directory / f"{ICON_NAME}.png"
        if target.exists() and not force:
            continue
        directory.mkdir(parents=True, exist_ok=True)

        image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()

        if not image.save(str(target), "PNG"):
            raise SystemExit(f"Could not write {target}")
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite icons that already exist",
    )
    arguments = parser.parse_args()

    if not SOURCE_SVG.is_file():
        raise SystemExit(f"Missing source icon: {SOURCE_SVG}")

    written = render(SOURCE_SVG, arguments.output, SIZES, arguments.force)
    for path in written:
        print(path.relative_to(PROJECT_ROOT))
    print(f"{len(written)} icon(s) written, {len(SIZES)} sizes in total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
