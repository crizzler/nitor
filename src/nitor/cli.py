"""Command line entry point.

Besides starting the window, this provides the three headless paths that make the project usable in
scripts, in CI and in the systemd unit:

``--apply-saved``   reapply the saved lighting and exit (used at login)
``--diagnostics``   print the report to paste into an issue
``--self-test``     a headless smoke test that never touches real hardware
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from nitor import APP_NAME, __version__
from nitor.backend import (
    MODE_AUTO,
    MODE_MOCK,
    MODES,
    HardwareBackend,
    check_device_access,
    create_backend,
)
from nitor.backend.commands import validate_argv
from nitor.domain import Device, NitorError, SafetyViolationError
from nitor.services import (
    Settings,
    SettingsStore,
    build_report,
    configure_logging,
    verbose_requested,
)
from nitor.services.autostart import render_unit
from nitor.services.startup import apply_saved

_LOGGER = logging.getLogger(__name__)

_PROGRAM = "nitor"

_SELF_TEST_TEMPLATE = """[Unit]
Description=self test

[Service]
ExecStart=@@EXEC_START@@
@@ENVIRONMENT@@

[Install]
WantedBy=default.target
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_PROGRAM,
        description=f"{APP_NAME} — control NZXT LED lighting on Linux without NZXT CAM.",
        epilog=(
            "Nitor only ever sets LED colours. Fan and pump control are deliberately out of scope "
            "and are refused by the backend."
        ),
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="log debug information (or set NITOR_DEBUG=1)",
    )
    parser.add_argument(
        "--backend",
        choices=MODES,
        default=MODE_AUTO,
        help="which backend to use (default: auto, the real liquidctl backend)",
    )
    parser.add_argument(
        "--mock-device",
        action="store_true",
        help="use a fake controller: never touches real hardware, for interface development",
    )
    parser.add_argument(
        "--apply-saved",
        action="store_true",
        help="reapply the saved lighting and exit; this is what the login service runs",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="print a diagnostics report and exit",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run a headless smoke test with a fake controller and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --apply-saved, report what would be sent without sending it",
    )
    return parser


def resolve_backend_mode(arguments: argparse.Namespace) -> str:
    if arguments.mock_device:
        return MODE_MOCK
    return str(arguments.backend)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(list(argv) if argv is not None else None)

    configure_logging(verbose_requested(arguments.verbose))
    mode = resolve_backend_mode(arguments)

    if arguments.self_test:
        return run_self_test()
    if arguments.diagnostics:
        return print_diagnostics(mode)
    if arguments.apply_saved:
        return apply_saved_and_exit(mode, dry_run=arguments.dry_run)
    return run_gui()


def run_gui() -> int:
    """Start the desktop application."""
    if not os.environ.get("QT_QPA_PLATFORM") and not _has_display():
        print(
            "Nitor needs a graphical session. Use --diagnostics, --apply-saved or\n"
            "QT_QPA_PLATFORM=offscreen if you meant to run it headlessly.",
            file=sys.stderr,
        )
        return 1

    from nitor.app import run  # imported here so the headless paths never load Qt

    try:
        return run()
    except RuntimeError as error:
        print(f"{error}", file=sys.stderr)
        return 1


def _has_display() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def apply_saved_and_exit(mode: str, *, dry_run: bool = False) -> int:
    """Reapply the saved lighting without a user interface."""
    backend = create_backend(mode)
    store = SettingsStore()
    settings = store.load()

    if dry_run:
        outcome = apply_saved(backend, settings)
        print(f"{'would apply' if outcome.ok else 'would fail'}: {outcome.message}")
        return outcome.exit_code

    outcome = apply_saved(backend, settings)
    print(outcome.message)
    return outcome.exit_code


def print_diagnostics(mode: str) -> int:
    """Print the diagnostics report, probing the hardware as far as permissions allow."""
    backend = create_backend(mode)
    status = backend.status
    devices = _probe_devices(backend) if status.available else []
    access = check_device_access(backend, devices) if devices else {}

    print(
        build_report(
            backend_status=status,
            devices=devices,
            access=access,
            apply_on_login=SettingsStore().load().apply_on_login,
            backend_mode=mode,
        )
    )
    return 0


def _probe_devices(backend: HardwareBackend) -> list[Device]:
    """Read what can be read for the report. A device that refuses is still worth listing."""
    try:
        discovered = backend.discover_devices()
    except NitorError as error:
        _LOGGER.warning("could not list devices for the diagnostics report: %s", error)
        return []

    devices: list[Device] = []
    for device in discovered:
        if device.lighting_supported:
            try:
                device = backend.initialize_device(device)
            except NitorError as error:
                _LOGGER.debug("could not read %s for the report: %s", device.key, error)
        devices.append(device)
    return devices


def run_self_test() -> int:
    """A headless smoke test that never touches real hardware.

    Used by CI to catch a broken build: the backend, the command gate, settings persistence, the
    startup unit and the QML interface are all exercised.
    """
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append((name, bool(condition), detail))

    backend = create_backend(MODE_MOCK)

    check("backend available", backend.status.available, backend.status.summary)

    devices = backend.discover_devices()
    check("mock devices discovered", len(devices) == 2, f"{len(devices)} found")

    device = devices[0]
    initialized = backend.initialize_device(device)
    capabilities = initialized.capabilities
    check(
        "channels reported",
        len(capabilities.channels) >= 2,
        str([c.id for c in capabilities.channels]),
    )
    check(
        "effects reported", len(capabilities.effects) > 20, f"{len(capabilities.effects)} effects"
    )

    state = Settings().lighting_for("missing") or None
    check("no saved lighting by default", state is None)

    from nitor.domain import Color, LightingState

    applied = backend.apply_lighting(
        initialized,
        LightingState(
            channel=capabilities.default_channel or "led1",
            effect="fixed",
            colors=(Color(0, 170, 255),),
        ),
    )
    check("a colour was applied", "color" in applied.argv, applied.command_line)

    refused = False
    try:
        validate_argv(("set", "pump", "speed", "90"))
    except SafetyViolationError:
        refused = True
    check("cooling commands are refused", refused)

    with tempfile.TemporaryDirectory() as directory:
        store = SettingsStore(Path(directory) / "config.json")
        settings = Settings(apply_on_login=True)
        settings.set_lighting(
            device.key,
            LightingState(channel="led1", effect="fixed", colors=(Color(255, 0, 0),)),
        )
        store.save(settings)
        reloaded = store.load()
        check(
            "settings survive a round trip",
            reloaded.apply_on_login and reloaded.lighting_for(device.key) is not None,
        )

    unit = render_unit(_SELF_TEST_TEMPLATE, exec_start="/usr/bin/nitor", environment=[])
    check(
        "the startup unit renders",
        "ExecStart=/usr/bin/nitor" in unit and "@@" not in unit,
    )

    qml_ok, qml_detail = _check_qml_loads(backend, device)
    check("the QML interface loads", qml_ok, qml_detail)

    exit_code = 0
    for name, passed, detail in results:
        marker = "PASS" if passed else "FAIL"
        suffix = f" — {detail}" if detail else ""
        print(f"{marker}  {name}{suffix}")
        if not passed:
            exit_code = 1
    print(f"\n{len(results)} checks, {sum(1 for _, ok, _ in results if ok)} passed.")
    return exit_code


def _check_qml_loads(backend: object, device: object) -> tuple[bool, str]:
    """Load the QML interface offscreen and let it reach a usable state.

    Qt's own messages are captured, so a broken binding or a property that does not exist fails the
    smoke test instead of scrolling past in the log.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import qInstallMessageHandler

        from nitor.app import apply_quick_style, create_application, load_interface
        from nitor.ui.viewmodel import NitorViewModel
    except ImportError as error:  # pragma: no cover - PySide6 missing
        return False, f"PySide6 unavailable: {error}"

    messages: list[str] = []

    def collect(_mode: object, _context: object, message: str) -> None:
        messages.append(message)

    previous = qInstallMessageHandler(collect)
    loaded = False
    ready = False
    try:
        apply_quick_style()
        application = create_application(["nitor", "--self-test"])
        view_model = NitorViewModel(backend)  # type: ignore[arg-type]
        engine = load_interface(view_model)
        loaded = bool(engine.rootObjects())
        view_model.start()

        deadline = time.monotonic() + 5.0
        while not view_model.ready and time.monotonic() < deadline:
            application.processEvents()
            time.sleep(0.01)
        ready = view_model.ready

        view_model.shutdown()
        application.quit()
    except Exception as error:
        return False, str(error)
    finally:
        qInstallMessageHandler(previous)

    problems = [message for message in messages if _is_qml_problem(message)]
    if not loaded:
        return False, "no root object was created"
    if problems:
        return False, problems[0]
    if not ready:
        return False, "the interface loaded but never reached a usable state"
    return True, ""


def _is_qml_problem(message: str) -> bool:
    """Whether a Qt message indicates something is actually wrong."""
    lowered = message.lower()
    benign = ("qml debugging is enabled", "qt quick controls", "found no plugins")
    if any(marker in lowered for marker in benign):
        return False
    return any(
        marker in lowered
        for marker in (
            "error",
            "unable to assign",
            "is not defined",
            "cannot assign",
            "typeerror",
            "overrides a member of the base object",
        )
    )


__all__ = [
    "apply_saved_and_exit",
    "build_parser",
    "main",
    "print_diagnostics",
    "resolve_backend_mode",
    "run_self_test",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
