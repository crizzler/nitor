"""The Qt-facing application state.

QML holds no logic, and the rest of the application knows nothing about Qt. This module is the seam
between them: it exposes devices, capabilities and the lighting state as plain properties, and it
owns the worker thread so that no user-interface call ever waits for USB.

Two rules are enforced here rather than trusted to the interface:

* the hardware is only ever touched from the worker thread
* the lighting state keeps the colour slots, effect limits and channel that the selected device
  actually supports
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Property, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from nitor import APP_NAME, __version__
from nitor.backend.base import AppliedLighting, BackendStatus, HardwareBackend
from nitor.backend.registry import MODE_AUTO, DeviceAccess, check_device_access, create_backend
from nitor.domain import (
    DEFAULT_DIRECTION,
    DEFAULT_EFFECT,
    DEFAULT_SPEED,
    DIRECTIONS,
    PRESETS,
    SPEEDS,
    WHITE,
    Color,
    Device,
    DeviceCapabilities,
    InvalidColorError,
    LightingState,
    NitorError,
    NotSupportedError,
    PermissionDeniedError,
)
from nitor.services import Settings, SettingsStore, WriteScheduler, build_report
from nitor.services.autostart import AutostartError, AutostartManager, AutostartState
from nitor.services.scheduling import DEFAULT_DEBOUNCE, DEFAULT_MIN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STATUS_IDLE = "idle"
STATUS_BUSY = "applying"
STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"

#: How many colour slots the interface offers for effects that accept many (the ``super-*`` modes
#: accept up to 40, one per LED). Per-LED editing is deliberately out of scope for now; the command
#: sent to the hardware is still valid because the value is only ever trimmed, never over-filled.
MAX_EDITABLE_SLOTS = 8

#: Fallback base font size, used only when the view model is built without a running application.
DEFAULT_FONT_POINT_SIZE = 10

#: How long shutdown waits for an in-flight hardware call. Must exceed the backend's own subprocess
#: timeout, otherwise closing the window during a slow call destroys a running QThread and aborts.
WORKER_STOP_TIMEOUT = 20.0


class _BackendWorker(QObject):
    """Runs every hardware operation, on its own thread."""

    discovered = Signal(object, object)
    initialized = Signal(object)
    applied = Signal(object)
    failed = Signal(str, object)
    autostartChanged = Signal(object)
    autostartFailed = Signal(object)

    def __init__(
        self,
        backend: HardwareBackend,
        autostart: AutostartManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend
        self._autostart = autostart

    @Slot()
    def discover(self) -> None:
        status = self._backend.status
        if not status.available:
            self.discovered.emit([], status)
            return
        try:
            devices = self._backend.discover_devices()
        except NitorError as error:
            # Only report the failure. Also emitting an empty device list would look like a
            # successful search that found nothing, and the "no controller found" handling would
            # then overwrite the real reason: a permission problem would be reported as missing
            # hardware, with the udev advice replaced by "check lsusb".
            self.failed.emit("discover", error)
            return
        self.discovered.emit(devices, status)

    @Slot()
    def refresh(self) -> None:
        """Re-probe the backend, then look for devices again."""
        refresh = getattr(self._backend, "refresh", None)
        if callable(refresh):
            refresh()
        self.discover()

    @Slot(object)
    def initialize(self, device: Device) -> None:
        try:
            self.initialized.emit(self._backend.initialize_device(device))
        except NitorError as error:
            self.failed.emit("initialize", error)

    @Slot(object, object)
    def apply(self, write: object, device: Device) -> None:
        state = write.state  # type: ignore[attr-defined]
        try:
            applied: AppliedLighting = self._backend.apply_lighting(device, state)
        except NitorError as error:
            self.failed.emit("apply", error)
            return
        self.applied.emit(applied)

    @Slot()
    def query_autostart(self) -> None:
        try:
            self.autostartChanged.emit(self._autostart.state())
        except AutostartError as error:
            self.autostartFailed.emit(error)

    @Slot(bool)
    def set_autostart(self, enabled: bool) -> None:
        try:
            state = self._autostart.enable() if enabled else self._autostart.disable()
        except AutostartError as error:
            self.autostartFailed.emit(error)
            return
        self.autostartChanged.emit(state)


class NitorViewModel(QObject):
    """Everything QML binds to.

    One ``changed`` signal notifies every property. With this many bindings and this little data,
    coarse notifications are simpler to reason about than two dozen individual signals, and the
    cost is negligible.
    """

    changed = Signal()

    _discoverRequested = Signal()
    _refreshRequested = Signal()
    _initializeRequested = Signal(object)
    _applyRequested = Signal(object, object)
    _autostartQueryRequested = Signal()
    _autostartSetRequested = Signal(bool)

    def __init__(
        self,
        backend: HardwareBackend | None = None,
        *,
        backend_mode: str = MODE_AUTO,
        store: SettingsStore | None = None,
        autostart: AutostartManager | None = None,
        debounce: float = DEFAULT_DEBOUNCE,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend_mode = backend_mode
        self._backend = backend if backend is not None else create_backend(backend_mode)
        self._store = store if store is not None else SettingsStore()
        self._settings: Settings = self._store.load()
        self._autostart = autostart if autostart is not None else AutostartManager()
        self._scheduler = WriteScheduler(debounce=debounce, min_interval=min_interval)

        self._status = self._initial_status()
        self._devices: list[Device] = []
        self._access: dict[str, DeviceAccess] = {}
        self._current: Device | None = None
        self._capabilities: DeviceCapabilities | None = None
        self._state = LightingState(channel="", effect=DEFAULT_EFFECT, colors=(WHITE,))
        self._active_slot = 0
        self._notices: list[str] = []
        self._status_message = "Looking for a compatible NZXT controller…"
        self._status_kind = STATUS_BUSY
        self._status_hint = ""
        self._busy = True
        self._ready = False
        self._access_denied = False
        self._permission_hint = ""
        self._diagnostics = ""
        self._autostart_state = AutostartState(supported=True, installed=False, enabled=False)
        self._in_flight_revision: int | None = None
        self._started = False
        self._pending_device_key: str | None = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush)

        self._thread = QThread(self)
        self._thread.setObjectName("nitor-hardware")
        self._worker = _BackendWorker(self._backend, self._autostart)
        self._worker.moveToThread(self._thread)
        self._connect_worker()
        self._thread.start()

    def _initial_status(self) -> BackendStatus:
        name = getattr(self._backend, "name", "backend")
        if self._backend.is_mock:
            return self._backend.status
        return BackendStatus(
            name=name,
            available=True,
            summary="Checking the lighting backend…",
        )

    def _connect_worker(self) -> None:
        self._discoverRequested.connect(self._worker.discover)
        self._refreshRequested.connect(self._worker.refresh)
        self._initializeRequested.connect(self._worker.initialize)
        self._applyRequested.connect(self._worker.apply)
        self._autostartQueryRequested.connect(self._worker.query_autostart)
        self._autostartSetRequested.connect(self._worker.set_autostart)

        self._worker.discovered.connect(self._on_discovered)
        self._worker.initialized.connect(self._on_initialized)
        self._worker.applied.connect(self._on_applied)
        self._worker.failed.connect(self._on_failed)
        self._worker.autostartChanged.connect(self._on_autostart_changed)
        self._worker.autostartFailed.connect(self._on_autostart_failed)

    # -- lifecycle ------------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Begin discovery once the interface is visible. Safe to call more than once."""
        if self._started:
            return
        self._started = True
        self._discoverRequested.emit()

    @Slot()
    def shutdown(self) -> None:
        """Stop the worker thread. Called when the window closes.

        The wait deliberately outlasts a single backend call. Destroying a QThread while it is still
        running aborts the whole process ("QThread: Destroyed while thread is still running"), and
        the case that matters is closing the window while a hardware call is in flight: a liquidctl
        invocation may legitimately take longer than a few seconds, so a short wait would turn
        "close the window" into a crash on exit. Every backend call has its own subprocess timeout,
        so this is bounded in practice.
        """
        self._timer.stop()
        self._scheduler.cancel()
        self._thread.quit()
        if not self._thread.wait(WORKER_STOP_TIMEOUT):
            _LOGGER.warning(
                "the hardware worker was still running after %gs; waiting anyway",
                WORKER_STOP_TIMEOUT,
            )
            self._thread.wait()

    # -- worker results ------------------------------------------------------------------

    @Slot(object, object)
    def _on_discovered(self, devices: list[Device], status: BackendStatus) -> None:
        self._devices = list(devices)
        self._status = status
        self._access = check_device_access(self._backend, self._devices)
        self._busy = False
        self._refresh_diagnostics()

        if not status.available:
            self._current = None
            self._capabilities = None
            self._ready = False
            self._access_denied = False
            self._set_status(status.summary, STATUS_ERROR, status.hint or "")
            self.changed.emit()
            return

        usable = [device for device in self._devices if device.lighting_supported]
        if not usable:
            self._current = None
            self._capabilities = None
            self._ready = False
            self._access_denied = False
            self._set_status(self._no_device_message(), STATUS_WARNING)
            self.changed.emit()
            return

        remembered = self._settings.selected_device
        chosen = next((device for device in usable if device.key == remembered), usable[0])
        self._access_denied = not self._access.get(
            chosen.key, DeviceAccess(chosen.key, True)
        ).accessible
        if self._access_denied:
            entry = self._access.get(chosen.key)
            self._permission_hint = entry.reason if entry else ""
        self._set_status(f"Reading {chosen.display_name}…", STATUS_BUSY)
        self.changed.emit()
        self._pending_device_key = chosen.key
        self._initializeRequested.emit(chosen)

    def _no_device_message(self) -> str:
        if self._devices:
            return "A device was found, but its lighting is not supported yet."
        return "No compatible NZXT lighting controller was found."

    @Slot(object)
    def _on_initialized(self, device: Device) -> None:
        if self._pending_device_key is not None and device.key != self._pending_device_key:
            # A result for a device the user has already moved away from.
            _LOGGER.debug("ignoring a late initialisation of %s", device.key)
            return

        same_device = self._current is not None and self._current.key == device.key
        self._current = device
        self._capabilities = device.capabilities
        capabilities = self._capabilities

        if not capabilities.supports_lighting:
            self._ready = False
            note = device.profile.note if device.profile and device.profile.note else ""
            self._set_status(
                f"{device.display_name} has no controllable LED channels.", STATUS_WARNING, note
            )
            self._refresh_diagnostics()
            self.changed.emit()
            return

        if same_device:
            # Re-initialising the device it is already controlling must not throw away what the
            # user has chosen; only the capabilities could have changed.
            self._state = self._state.normalized(capabilities)
        else:
            saved = self._settings.lighting_for(device.key)
            base = saved or LightingState(
                channel=capabilities.default_channel or "",
                effect=DEFAULT_EFFECT,
                colors=(WHITE,),
            )
            self._state = base.normalized(capabilities)
        self._active_slot = 0
        self._notices = self._build_notices(device)
        self._ready = True
        self._busy = False
        self._settings.selected_device = device.key
        self._remember()
        self._refresh_diagnostics()

        if self._access_denied:
            self._set_status(
                "The controller was found, but Linux denied access to it.",
                STATUS_ERROR,
                self._permission_hint
                or "Installing the liquidctl package provides the udev rule this needs.",
            )
        elif self._notices:
            self._set_status(self._notices[0], STATUS_WARNING)
        else:
            self._set_status(f"Controlling {device.display_name}.", STATUS_OK)
        self.changed.emit()

    def _build_notices(self, device: Device) -> list[str]:
        notices: list[str] = []
        capabilities = device.capabilities
        for channel in capabilities.controllable_channels:
            if channel.id != "sync" and not channel.has_accessories:
                notices.append(f"No accessories detected on {channel.label}.")
        if device.profile is not None and device.profile.led_channels == ("external",):
            notices.append(
                "Only the external HUE 2 channel carries LEDs on this cooler; its pump face is a "
                "display, which Nitor does not control."
            )
        return notices

    @Slot(object)
    def _on_applied(self, applied: AppliedLighting) -> None:
        if self._in_flight_revision is not None:
            self._scheduler.complete(self._in_flight_revision)
            self._in_flight_revision = None

        channel = self._capabilities.channel(applied.channel) if self._capabilities else None
        label = channel.label if channel else applied.channel
        colors = ", ".join(color.to_hex() for color in applied.colors)
        if applied.is_off:
            message = f"{label} switched off."
        elif colors:
            message = f"{label} · {applied.effect} · {colors}"
        else:
            message = f"{label} · {applied.effect}"
        self._set_status(message, STATUS_OK)

        if self._scheduler.has_pending:
            self._schedule_flush()
        else:
            self._remember()
        self.changed.emit()

    @Slot(str, object)
    def _on_failed(self, operation: str, error: NitorError) -> None:
        if operation == "apply" and self._in_flight_revision is not None:
            self._scheduler.apply_failed(self._in_flight_revision)
            self._in_flight_revision = None
        self._busy = False

        if isinstance(error, PermissionDeniedError):
            self._access_denied = True
            self._permission_hint = error.hint or ""
        if isinstance(error, NotSupportedError):
            self._ready = False

        _LOGGER.warning("%s failed: %s", operation, error)
        self._set_status(error.message, STATUS_ERROR, error.hint or "")
        self._refresh_diagnostics()
        self.changed.emit()

    @Slot(object)
    def _on_autostart_changed(self, state: AutostartState) -> None:
        self._autostart_state = state
        self._settings.apply_on_login = state.active
        self._remember()
        # Never talk over a failure. The autostart check runs at startup, just after discovery, so
        # without this a permission problem or a missing backend would be replaced by a note about
        # login behaviour before the user had a chance to read it.
        if self._status_kind == STATUS_ERROR:
            self.changed.emit()
            return
        if state.active:
            self._set_status("Lighting will be reapplied when you log in.", STATUS_OK)
        elif state.detail:
            self._set_status(state.detail, STATUS_WARNING)
        self.changed.emit()

    @Slot(object)
    def _on_autostart_failed(self, error: AutostartError) -> None:
        self._autostart_state = AutostartState(
            supported=self._autostart.supported(),
            installed=False,
            enabled=False,
            detail=error.message,
        )
        self._set_status(error.message, STATUS_ERROR, error.hint or "")
        self.changed.emit()

    # -- requested changes ----------------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        """Look for devices again, re-probing the backend first."""
        self._busy = True
        self._set_status("Looking for a compatible NZXT controller…", STATUS_BUSY)
        self.changed.emit()
        self._refreshRequested.emit()

    @Slot(str)
    def selectDevice(self, key: str) -> None:
        device = next((candidate for candidate in self._devices if candidate.key == key), None)
        if device is None or device.key == (self._current.key if self._current else None):
            return
        self._scheduler.cancel()
        self._busy = True
        self._ready = False
        self._settings.selected_device = key
        self._set_status(f"Reading {device.display_name}…", STATUS_BUSY)
        self.changed.emit()
        self._pending_device_key = key
        self._initializeRequested.emit(device)

    @Slot(str)
    def selectChannel(self, channel_id: str) -> None:
        if self._capabilities is None:
            return
        try:
            self._capabilities.channel(channel_id)
        except NotSupportedError:
            return
        self._update_state(self._state.with_channel(channel_id))

    @Slot(str)
    def selectEffect(self, effect_id: str) -> None:
        if self._capabilities is None:
            return
        try:
            self._capabilities.effect(effect_id)
        except NotSupportedError:
            return
        state = self._state.with_effect(effect_id).normalized(self._capabilities)
        self._active_slot = min(self._active_slot, max(0, len(state.colors) - 1))
        self._update_state(state)

    @Slot(int)
    def selectColorSlot(self, index: int) -> None:
        if 0 <= index < self._color_slot_count():
            self._active_slot = index
            self.changed.emit()

    @Slot(str)
    def setColorHex(self, text: str) -> None:
        try:
            color = Color.from_hex(text)
        except InvalidColorError as error:
            self._set_status(error.message, STATUS_ERROR, error.hint or "")
            self.changed.emit()
            return
        self._update_state(self._state.with_color(self._active_slot, color))

    @Slot(int, int, int)
    def setColorComponents(self, red: int, green: int, blue: int) -> None:
        """Used by the colour wheel, which works in components rather than hex."""
        try:
            color = Color(int(red), int(green), int(blue))
        except InvalidColorError:
            return
        self._update_state(self._state.with_color(self._active_slot, color))

    @Slot(str)
    def setPreset(self, name: str) -> None:
        preset = dict(PRESETS).get(name)
        if preset is None:
            return
        self._update_state(self._state.with_color(self._active_slot, preset))

    @Slot(int)
    def setBrightness(self, percent: int) -> None:
        self._update_state(self._state.with_brightness(max(0, min(100, int(percent)))))

    @Slot(str)
    def setSpeed(self, speed: str) -> None:
        if speed in SPEEDS:
            self._update_state(self._state.with_speed(speed))

    @Slot(str)
    def setDirection(self, direction: str) -> None:
        if direction in DIRECTIONS:
            self._update_state(self._state.with_direction(direction))

    @Slot()
    def turnOff(self) -> None:
        if self._capabilities is None:
            return
        self._update_state(self._state.with_effect("off").normalized(self._capabilities))

    @Slot()
    def applyNow(self) -> None:
        """Send the current state immediately, skipping the debounce."""
        self._timer.stop()
        device = self._current
        if device is None:
            return
        self._scheduler.submit(device.key, self._state, force=True)
        self._flush()

    @Slot()
    def resetToDefaults(self) -> None:
        if self._capabilities is None:
            return
        self._update_state(
            LightingState(
                channel=self._capabilities.default_channel or "",
                effect=DEFAULT_EFFECT,
                colors=(WHITE,),
            ).normalized(self._capabilities)
        )

    @Slot()
    def queryAutostart(self) -> None:
        self._autostartQueryRequested.emit()

    @Slot(bool)
    def setApplyOnLogin(self, enabled: bool) -> None:
        self._settings.apply_on_login = enabled
        self._autostartSetRequested.emit(bool(enabled))

    @Slot(int, int)
    def saveWindowState(self, width: int, height: int) -> None:
        if width > 0 and height > 0:
            self._settings.window_width = width
            self._settings.window_height = height
            self._remember()

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self._set_status("Copied to the clipboard.", STATUS_OK)
            self.changed.emit()

    @Slot(result=str)
    def diagnosticsReport(self) -> str:
        self._refresh_diagnostics()
        return self._diagnostics

    # -- internals ------------------------------------------------------------------------

    def _update_state(self, state: LightingState, *, force: bool = False) -> None:
        self._state = state
        self.changed.emit()

        device = self._current
        if device is None or not self._ready:
            return
        if self._scheduler.submit(device.key, state, force=force) is None:
            return
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        delay = self._scheduler.next_delay()
        if delay is None:
            return
        self._timer.start(max(10, int(delay * 1000)))

    @Slot()
    def _flush(self) -> None:
        write = self._scheduler.take()
        if write is None:
            self._schedule_flush()
            return
        device = self._current
        if device is None:
            self._scheduler.cancel()
            return
        self._in_flight_revision = write.revision
        self._set_status("Applying…", STATUS_BUSY)
        self.changed.emit()
        self._applyRequested.emit(write, device)

    def _remember(self) -> None:
        if self._current is not None:
            self._settings.set_lighting(self._current.key, self._state)
        self._store.save(self._settings)

    def _set_status(self, message: str, kind: str, hint: str = "") -> None:
        self._status_message = message
        self._status_kind = kind
        self._status_hint = hint

    def _devices_for_report(self) -> list[Device]:
        """Discovered devices, with the probed details of the one currently in use.

        Only the selected device is initialised, so it is the only one whose channels and firmware
        are known; the report says "not probed yet" for the rest rather than implying it checked.
        """
        current = self._current
        devices = list(self._devices)
        if current is None:
            return devices
        for index, device in enumerate(devices):
            if device.key == current.key:
                devices[index] = current
                return devices
        devices.append(current)
        return devices

    def _refresh_diagnostics(self) -> None:
        notes: list[str] = []
        if self._current is not None and self._current.firmware:
            notes.append(f"Firmware {self._current.firmware}")
        notes.extend(self._notices)
        self._diagnostics = build_report(
            backend_status=self._status,
            devices=self._devices_for_report(),
            access=self._access,
            apply_on_login=self._settings.apply_on_login,
            backend_mode=self._backend_mode,
            extra=notes,
        )

    def _current_effect(self):
        """The selected effect, or ``None`` when nothing is selected."""
        if self._capabilities is None:
            return None
        try:
            return self._capabilities.effect(self._state.effect)
        except NotSupportedError:
            return None

    def _color_slot_count(self) -> int:
        effect = self._current_effect()
        if effect is None or not effect.uses_colors:
            return 0
        return max(effect.min_colors, min(effect.max_colors, MAX_EDITABLE_SLOTS))

    # -- properties exposed to QML ---------------------------------------------------------

    @Property(str, notify=changed)
    def appName(self) -> str:
        return APP_NAME

    @Property(str, notify=changed)
    def version(self) -> str:
        return __version__

    @Property(int, constant=True)
    def baseFontPointSize(self) -> int:
        """The system's base font size, so the interface scales typography from one number.

        QML could read ``Qt.application.font`` directly, which is the documented way to follow the
        system font, but ``qmllint``'s type metadata does not describe that property and reports
        every use as a missing property. Exposing it here keeps the lint output meaningful.
        """
        application = QGuiApplication.instance()
        if application is None:  # pragma: no cover - only reachable without a GUI
            return DEFAULT_FONT_POINT_SIZE
        point_size = application.font().pointSize()
        return point_size if point_size > 0 else DEFAULT_FONT_POINT_SIZE

    @Property(bool, notify=changed)
    def mockMode(self) -> bool:
        return self._backend.is_mock

    @Property(bool, notify=changed)
    def backendAvailable(self) -> bool:
        return self._status.available

    @Property(str, notify=changed)
    def backendSummary(self) -> str:
        return self._status.summary

    @Property(str, notify=changed)
    def backendName(self) -> str:
        return self._status.name

    @Property(str, notify=changed)
    def backendVersion(self) -> str:
        return self._status.version or ""

    @Property(str, notify=changed)
    def backendHint(self) -> str:
        return self._status.hint or ""

    @Property(str, notify=changed)
    def installCommand(self) -> str:
        return self._status.install_command or ""

    @Property(bool, notify=changed)
    def accessDenied(self) -> bool:
        return self._access_denied

    @Property(str, notify=changed)
    def permissionHint(self) -> str:
        return self._permission_hint

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=changed)
    def ready(self) -> bool:
        return self._ready

    @Property(bool, notify=changed)
    def hasDevices(self) -> bool:
        return bool(self._devices)

    @Property(str, notify=changed)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=changed)
    def statusKind(self) -> str:
        return self._status_kind

    @Property(str, notify=changed)
    def statusHint(self) -> str:
        return self._status_hint

    @Property("QVariantList", notify=changed)
    def devices(self) -> list[dict[str, Any]]:
        return [
            {
                "key": device.key,
                "name": device.display_name,
                "usbId": device.usb_id,
                "driver": device.driver,
                "lightingSupported": device.lighting_supported,
                "note": device.profile.note if device.profile and device.profile.note else "",
                "current": self._current is not None and device.key == self._current.key,
            }
            for device in self._devices
        ]

    @Property(str, notify=changed)
    def currentDeviceKey(self) -> str:
        return self._current.key if self._current else ""

    @Property(str, notify=changed)
    def currentDeviceName(self) -> str:
        return self._current.display_name if self._current else ""

    @Property(str, notify=changed)
    def currentDeviceUsbId(self) -> str:
        return self._current.usb_id if self._current else ""

    @Property(str, notify=changed)
    def currentDeviceDriver(self) -> str:
        return self._current.driver if self._current else ""

    @Property(str, notify=changed)
    def currentDeviceFirmware(self) -> str:
        return (self._current.firmware or "") if self._current else ""

    @Property(str, notify=changed)
    def currentDeviceAddress(self) -> str:
        return self._current.address if self._current else ""

    @Property("QVariantList", notify=changed)
    def channels(self) -> list[dict[str, Any]]:
        if self._capabilities is None:
            return []
        return [
            {
                "id": channel.id,
                "label": channel.label,
                "summary": channel.summary,
                "ledCount": channel.led_count or 0,
                "hasAccessories": channel.has_accessories,
            }
            for channel in self._capabilities.channels
        ]

    @Property(str, notify=changed)
    def channelId(self) -> str:
        return self._state.channel

    @Property(str, notify=changed)
    def channelLabel(self) -> str:
        if self._capabilities is None or not self._state.channel:
            return ""
        try:
            return self._capabilities.channel(self._state.channel).label
        except NotSupportedError:
            return self._state.channel

    @Property("QVariantList", notify=changed)
    def effects(self) -> list[dict[str, Any]]:
        if self._capabilities is None:
            return []
        return [
            {
                "id": effect.id,
                "label": effect.label,
                "group": effect.group,
                "minColors": effect.min_colors,
                "maxColors": effect.max_colors,
                "usesColors": effect.uses_colors,
                "supportsSpeed": effect.supports_speed,
                "supportsDirection": effect.supports_direction,
            }
            for effect in self._capabilities.effects
        ]

    @Property(str, notify=changed)
    def effectId(self) -> str:
        return self._state.effect

    @Property(str, notify=changed)
    def effectLabel(self) -> str:
        if self._capabilities is None:
            return ""
        try:
            return self._capabilities.effect(self._state.effect).label
        except NotSupportedError:
            return self._state.effect

    @Property(bool, notify=changed)
    def effectsUseColors(self) -> bool:
        return self._color_slot_count() > 0

    @Property(bool, notify=changed)
    def speedAvailable(self) -> bool:
        if self._capabilities is None:
            return False
        try:
            return self._capabilities.effect(self._state.effect).supports_speed
        except NotSupportedError:
            return False

    @Property(bool, notify=changed)
    def directionAvailable(self) -> bool:
        if self._capabilities is None:
            return False
        try:
            return self._capabilities.effect(self._state.effect).supports_direction
        except NotSupportedError:
            return False

    @Property(bool, notify=changed)
    def brightnessAvailable(self) -> bool:
        """Brightness dims the colour Nitor sends, so it only means anything for coloured effects."""
        return self._color_slot_count() > 0

    @Property(str, notify=changed)
    def colorHex(self) -> str:
        colors = list(self._state.colors)
        if not colors:
            return ""
        index = min(self._active_slot, len(colors) - 1)
        return colors[index].to_hex()

    @Property(str, notify=changed)
    def colorRgb(self) -> str:
        colors = list(self._state.colors)
        if not colors:
            return "rgb(20, 20, 20)"
        index = min(self._active_slot, len(colors) - 1)
        color = colors[index]
        return f"rgb({color.r}, {color.g}, {color.b})"

    @Property(float, notify=changed)
    def colorHue(self) -> float:
        colors = list(self._state.colors)
        if not colors:
            return 0.0
        index = min(self._active_slot, len(colors) - 1)
        return colors[index].to_hsv()[0]

    @Property(float, notify=changed)
    def colorSaturation(self) -> float:
        colors = list(self._state.colors)
        if not colors:
            return 0.0
        index = min(self._active_slot, len(colors) - 1)
        return colors[index].to_hsv()[1]

    @Property(float, notify=changed)
    def colorValue(self) -> float:
        colors = list(self._state.colors)
        if not colors:
            return 0.0
        index = min(self._active_slot, len(colors) - 1)
        return colors[index].to_hsv()[2]

    @Property("QVariantList", notify=changed)
    def colorSlots(self) -> list[dict[str, Any]]:
        """One entry per colour the selected effect accepts, for the slot selector."""
        if self._capabilities is None:
            return []
        try:
            effect = self._capabilities.effect(self._state.effect)
        except NotSupportedError:
            return []
        if not effect.uses_colors:
            return []
        count = self._color_slot_count()
        colors = list(self._state.colors)
        return [
            {
                "index": index,
                "hex": (colors[index].to_hex() if index < len(colors) else colors[-1].to_hex()),
                "active": index == self._active_slot,
            }
            for index in range(count)
        ]

    @Property(int, notify=changed)
    def activeSlot(self) -> int:
        return self._active_slot

    @Property(int, notify=changed)
    def brightness(self) -> int:
        return self._state.brightness

    @Property(str, notify=changed)
    def speed(self) -> str:
        return self._state.speed if self._state.speed in SPEEDS else DEFAULT_SPEED

    @Property("QVariantList", notify=changed)
    def speeds(self) -> list[str]:
        return list(SPEEDS)

    @Property(str, notify=changed)
    def direction(self) -> str:
        return self._state.direction if self._state.direction in DIRECTIONS else DEFAULT_DIRECTION

    @Property("QVariantList", notify=changed)
    def directions(self) -> list[str]:
        return list(DIRECTIONS)

    @Property("QVariantList", notify=changed)
    def presets(self) -> list[dict[str, str]]:
        return [{"name": name, "hex": color.to_hex()} for name, color in PRESETS]

    @Property("QVariantList", notify=changed)
    def notices(self) -> list[str]:
        return list(self._notices)

    @Property(str, notify=changed)
    def previewColor(self) -> str:
        colors = self._state.preview_colors()
        return colors[0].to_hex() if colors else "#141414"

    @Property(str, notify=changed)
    def effectiveColor(self) -> str:
        """The colour that will actually be sent, after brightness."""
        colors = self._state.effective_colors()
        return colors[0].to_hex() if colors else "#000000"

    @Property(bool, notify=changed)
    def applyOnLogin(self) -> bool:
        return self._autostart_state.active

    @Property(bool, notify=changed)
    def autostartSupported(self) -> bool:
        return self._autostart_state.supported

    @Property(str, notify=changed)
    def autostartDetail(self) -> str:
        return self._autostart_state.detail

    @Property(int, notify=changed)
    def windowWidth(self) -> int:
        return self._settings.window_width

    @Property(int, notify=changed)
    def windowHeight(self) -> int:
        return self._settings.window_height

    @Property(str, notify=changed)
    def configPath(self) -> str:
        return str(self._store.path)

    @Property(str, notify=changed)
    def diagnosticsText(self) -> str:
        return self._diagnostics
