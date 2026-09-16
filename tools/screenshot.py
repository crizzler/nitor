#!/usr/bin/env python3
"""Capture screenshots of the interface using the mock backend.

Screenshots must not require hardware, so this runs offscreen against the mock device. The lighting
shown is therefore a mock too; the images are for documentation and the AppStream metadata, not
evidence that anything works on real LEDs.

Usage::

    python3 tools/screenshot.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Must be set before Qt is imported: this tool never touches a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "screenshots"

#: Page index in Main.qml -> file name.
PAGES = {0: "lighting.png", 1: "devices.png", 2: "settings.png", 3: "about.png"}


def _settle(application: object, seconds: float = 0.4) -> None:
    """Let queued signals, layout and painting happen."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        application.processEvents()  # type: ignore[attr-defined]
        time.sleep(0.01)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--width", type=int, default=1000)
    parser.add_argument("--height", type=int, default=680)
    arguments = parser.parse_args()

    try:
        from nitor.app import apply_quick_style, create_application, load_interface
        from nitor.backend import MODE_MOCK, create_backend
        from nitor.ui.viewmodel import NitorViewModel
    except ImportError as error:  # pragma: no cover
        print(f"PySide6 is required: {error}", file=sys.stderr)
        return 2

    apply_quick_style()
    application = create_application(["nitor"])
    backend = create_backend(MODE_MOCK)
    view_model = NitorViewModel(backend)
    engine = load_interface(view_model)

    roots = engine.rootObjects()
    if not roots:
        print("The interface did not load.", file=sys.stderr)
        return 1
    window = roots[0]

    window.setWidth(arguments.width)
    window.setHeight(arguments.height)
    view_model.start()

    deadline = time.monotonic() + 10.0
    while not view_model.ready and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.02)
    if not view_model.ready:
        print("The interface never became usable.", file=sys.stderr)
        return 1

    # A recognisable colour, so the screenshots do not show a black LED preview.
    view_model.setPreset("Cyan")
    view_model.selectEffect("breathing")
    _settle(application, 0.6)

    arguments.output.mkdir(parents=True, exist_ok=True)
    written = 0
    for index, name in PAGES.items():
        window.setProperty("currentPage", index)
        _settle(application, 0.4)
        image = window.grabWindow()
        if image.isNull():
            print(f"Could not capture page {index}.", file=sys.stderr)
            return 1
        target = arguments.output / name
        if not image.save(str(target), "PNG"):
            print(f"Could not write {target}", file=sys.stderr)
            return 1
        print(target.relative_to(PROJECT_ROOT))
        written += 1

    view_model.shutdown()
    application.quit()
    print(f"{written} screenshot(s) written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
