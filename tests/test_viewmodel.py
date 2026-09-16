"""The view model and the debounce path, without a display or any hardware.

These are integration tests: they exercise the real Qt objects, the real worker thread and the real
scheduler against the mock backend, which is what makes "the interface never blocks and never
hammers the controller" a tested claim rather than a hope.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

# Must be set before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QGuiApplication

from nitor.backend.mock import MockBackend
from nitor.domain import Device
from nitor.services.autostart import AutostartManager, CommandOutcome
from nitor.services.settings import SettingsStore
from nitor.ui.viewmodel import NitorViewModel

DEBOUNCE = 0.02


@pytest.fixture(scope="module")
def qt_application() -> QGuiApplication:
    application = QGuiApplication.instance()
    if application is None:
        application = QGuiApplication(["nitor-tests"])
    return application


class CountingBackend(MockBackend):
    """Counts how often the interface asks the hardware to do something."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.discoveries = 0
        self.initialisations = 0

    def discover_devices(self) -> list[Device]:
        self.discoveries += 1
        return super().discover_devices()

    def initialize_device(self, device: Device) -> Device:
        self.initialisations += 1
        return super().initialize_device(device)


class FakeSystemctl:
    def __call__(self, argv: tuple[str, ...]) -> CommandOutcome:
        verb = argv[2] if len(argv) > 2 else ""
        if verb == "is-enabled":
            return CommandOutcome(argv=argv, returncode=1, stdout="disabled\n")
        return CommandOutcome(argv=argv, returncode=0)


@pytest.fixture
def view_model(
    qt_application: QGuiApplication,
    tmp_path: Path,
) -> NitorViewModel:
    backend = CountingBackend()
    model = NitorViewModel(
        backend,
        store=SettingsStore(tmp_path / "config.json"),
        autostart=AutostartManager(
            unit_directory=tmp_path / "systemd" / "user",
            exec_start="/usr/bin/nitor",
            environment=[],
            runner=FakeSystemctl(),  # type: ignore[arg-type]
        ),
        debounce=DEBOUNCE,
        min_interval=0.0,
    )
    yield model
    model.shutdown()


def pump(until: Callable[[], bool], application: QGuiApplication, seconds: float = 5.0) -> bool:
    """Run the event loop until a condition holds, or time out."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        application.processEvents()
        if until():
            return True
        time.sleep(0.005)
    return until()


def quiesce(application: QGuiApplication, seconds: float = 0.4) -> None:
    """Let debounced work run and finish."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.005)


def test_the_view_model_reaches_a_usable_state(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    assert view_model.hasDevices
    assert view_model.backendAvailable
    assert [channel["id"] for channel in view_model.channels] == ["led1", "led2", "sync"]
    assert len(view_model.effects) == 27
    assert view_model.effectId == "fixed"
    assert view_model.colorHex == "#FFFFFF"
    assert view_model.brightness == 100
    assert view_model.mockMode is True
    assert "Mock" in view_model.backendSummary


def test_starting_twice_discovers_once(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    """The window calls start() when it is shown; a second call must not duplicate discovery."""
    view_model.start()
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)
    backend = view_model._backend
    assert backend.discoveries == 1
    assert backend.initialisations == 1


def test_a_burst_of_changes_produces_a_single_write(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    """Dragging through colours must not become one USB write per step."""
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    backend = view_model._backend
    for name in ("Red", "Green", "Blue", "Cyan", "Purple", "Orange", "White", "Red"):
        view_model.setPreset(name)
    quiesce(qt_application, 0.8)

    assert len(backend.applied) == 1
    assert backend.applied[0].colors[0].to_hex() == "#FF2020"  # the last preset wins
    assert view_model.colorHex == "#FF2020"


def test_brightness_is_applied_to_the_command(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    view_model.setPreset("Cyan")
    quiesce(qt_application)
    view_model.setBrightness(50)
    quiesce(qt_application, 0.5)

    backend = view_model._backend
    assert backend.last_applied is not None
    assert backend.last_applied.argv[-1] == "005580"
    assert view_model.effectiveColor == "#005580"
    assert view_model.previewColor == "#005580"


def test_re_initialising_the_same_device_keeps_the_chosen_colour(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    """A repeated discovery must not throw away what the user has chosen."""
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    view_model.setPreset("Purple")
    quiesce(qt_application)
    assert view_model.colorHex == "#A040FF"

    view_model.refresh()
    assert pump(lambda: view_model.ready, qt_application)
    quiesce(qt_application)

    assert view_model.colorHex == "#A040FF"


def test_turning_off_switches_to_the_off_effect(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    view_model.turnOff()
    quiesce(qt_application)

    backend = view_model._backend
    assert backend.last_applied is not None
    assert backend.last_applied.is_off
    assert view_model.effectId == "off"
    assert view_model.effectsUseColors is False
    assert view_model.brightnessAvailable is False


def test_switching_channel_is_sent_as_one_write(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    view_model.selectChannel("led2")
    quiesce(qt_application)

    backend = view_model._backend
    assert backend.last_applied is not None
    assert backend.last_applied.channel == "led2"
    assert view_model.channelId == "led2"


def test_effects_the_device_cannot_render_are_refused(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    # water-cooler exists on Kraken coolers, not on the RGB & Fan Controller.
    view_model.selectEffect("water-cooler")
    assert view_model.effectId == "fixed"

    # A channel that does not exist is ignored too.
    view_model.selectChannel("ring")
    assert view_model.channelId == "led1"


def test_an_invalid_colour_is_explained_rather_than_applied(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    view_model.setPreset("Cyan")
    quiesce(qt_application)
    view_model.setColorHex("not-a-colour")
    quiesce(qt_application, 0.3)

    assert view_model.colorHex == "#00AAFF"
    assert view_model.statusKind == "error"
    assert "not a valid colour" in view_model.statusMessage

    backend = view_model._backend
    assert len(backend.applied) == 1  # the invalid value never reached the hardware


def test_a_failure_is_reported_in_words(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    from nitor.domain import HardwareError

    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    backend = view_model._backend
    backend.queue_failure(HardwareError("The controller did not respond in time."))
    view_model.setPreset("Green")
    quiesce(qt_application, 0.6)

    assert view_model.statusKind == "error"
    assert view_model.statusMessage == "The controller did not respond in time."

    # ...and the interface keeps working, so the user can try again.
    view_model.setPreset("Blue")
    quiesce(qt_application, 0.6)
    assert view_model.statusKind == "ok"


def test_diagnostics_report_is_generated(
    view_model: NitorViewModel, qt_application: QGuiApplication
) -> None:
    view_model.start()
    assert pump(lambda: view_model.ready, qt_application)

    _ = qt_application
    report = view_model.diagnosticsReport()
    assert "Nitor diagnostics" in report
    assert "1e71:2010" in report
    assert "led1" in report
    assert view_model.diagnosticsText == report


def test_window_size_is_persisted(view_model: NitorViewModel) -> None:
    view_model.saveWindowState(1180, 760)
    assert view_model.windowWidth == 1180
    assert view_model.windowHeight == 760

    stored = view_model._store.load()
    assert (stored.window_width, stored.window_height) == (1180, 760)
