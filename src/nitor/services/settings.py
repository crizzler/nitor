"""Persistent settings in the standard XDG locations.

Configuration lives in ``$XDG_CONFIG_HOME/nitor/config.json`` (so ``~/.config/nitor/config.json`` by
default). Writes are atomic, so a crash or a full disk cannot leave a half-written file behind, and
a corrupt file is moved aside rather than being silently deleted.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from nitor.domain import LightingState

_LOGGER = logging.getLogger(__name__)

APP_DIRECTORY: Final = "nitor"
CONFIG_FILE: Final = "config.json"
SCHEMA_VERSION: Final = 1

DEFAULT_WINDOW_WIDTH: Final = 1000
DEFAULT_WINDOW_HEIGHT: Final = 680
MIN_WINDOW_WIDTH: Final = 640
MIN_WINDOW_HEIGHT: Final = 480
MAX_WINDOW_SIZE: Final = 8000


def _xdg_directory(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable, "").strip()
    base = Path(value) if value else Path.home() / fallback
    return base / APP_DIRECTORY


def config_dir() -> Path:
    """Where settings are stored."""
    return _xdg_directory("XDG_CONFIG_HOME", ".config")


def state_dir() -> Path:
    """Where small pieces of state (such as the last known device list) may be stored."""
    return _xdg_directory("XDG_STATE_HOME", ".local/state")


def cache_dir() -> Path:
    """Where disposable data may be stored."""
    return _xdg_directory("XDG_CACHE_HOME", ".cache")


def _clamp_size(value: Any, minimum: int, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(minimum, min(MAX_WINDOW_SIZE, value))


@dataclass(slots=True)
class Settings:
    """Everything Nitor remembers between runs."""

    schema_version: int = SCHEMA_VERSION
    apply_on_login: bool = False
    selected_device: str | None = None
    window_width: int = DEFAULT_WINDOW_WIDTH
    window_height: int = DEFAULT_WINDOW_HEIGHT
    verbose_logging: bool = False
    lighting: dict[str, LightingState] = field(default_factory=dict)

    def lighting_for(self, device_key: str) -> LightingState | None:
        return self.lighting.get(device_key)

    def set_lighting(self, device_key: str, state: LightingState) -> None:
        self.lighting[device_key] = state

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "apply_on_login": self.apply_on_login,
            "selected_device": self.selected_device,
            "verbose_logging": self.verbose_logging,
            "window": {"width": self.window_width, "height": self.window_height},
            "lighting": {
                device_key: state.to_dict() for device_key, state in sorted(self.lighting.items())
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        """Rebuild settings from stored data, ignoring anything malformed."""
        window = data.get("window")
        window = window if isinstance(window, dict) else {}

        lighting: dict[str, LightingState] = {}
        raw_lighting = data.get("lighting")
        if isinstance(raw_lighting, dict):
            for device_key, raw_state in raw_lighting.items():
                if isinstance(raw_state, dict):
                    lighting[str(device_key)] = LightingState.from_dict(raw_state)

        selected = data.get("selected_device")

        return cls(
            schema_version=SCHEMA_VERSION,
            apply_on_login=bool(data.get("apply_on_login", False)),
            selected_device=str(selected) if isinstance(selected, str) else None,
            window_width=_clamp_size(window.get("width"), MIN_WINDOW_WIDTH, DEFAULT_WINDOW_WIDTH),
            window_height=_clamp_size(
                window.get("height"), MIN_WINDOW_HEIGHT, DEFAULT_WINDOW_HEIGHT
            ),
            verbose_logging=bool(data.get("verbose_logging", False)),
            lighting=lighting,
        )


def _migrate_v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Version 0 was the pre-release layout, which stored a single ``color`` string.

    It is kept as a worked example of how to add a migration: copy the data, change it, and hand it
    back with the new schema version.
    """
    migrated = dict(data)
    legacy_color = migrated.pop("color", None)
    migrated.pop("effect", None)
    if isinstance(legacy_color, str):
        migrated.setdefault("lighting", {})
    migrated["schema_version"] = 1
    return migrated


#: Applied in order until the stored version matches :data:`SCHEMA_VERSION`.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    0: _migrate_v0_to_v1,
}


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Bring stored data up to the current schema version."""
    working = dict(data)
    version = working.get("schema_version")
    version = version if isinstance(version, int) and not isinstance(version, bool) else 0

    while version < SCHEMA_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            _LOGGER.warning("no migration from schema version %s; using defaults", version)
            return {"schema_version": SCHEMA_VERSION}
        working = migration(working)
        new_version = working.get("schema_version")
        if not isinstance(new_version, int) or new_version <= version:
            _LOGGER.warning("migration from schema version %s made no progress", version)
            return {"schema_version": SCHEMA_VERSION}
        version = new_version

    return working


class SettingsStore:
    """Loads and saves :class:`Settings`."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else config_dir() / CONFIG_FILE

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Settings:
        """Read settings, falling back to defaults for any reason at all.

        This runs at start-up, so it must never raise: a broken configuration file is moved aside
        and the application continues with defaults.
        """
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Settings()
        except OSError as error:
            _LOGGER.warning("could not read %s: %s", self._path, error)
            return Settings()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            self._quarantine(f"invalid JSON: {error}")
            return Settings()

        if not isinstance(data, dict):
            self._quarantine("the file does not contain a JSON object")
            return Settings()

        stored_version = data.get("schema_version", 0)
        if isinstance(stored_version, int) and stored_version > SCHEMA_VERSION:
            _LOGGER.warning(
                "%s was written by a newer version of Nitor (schema %s); using defaults and "
                "leaving the file alone",
                self._path,
                stored_version,
            )
            return Settings()

        return Settings.from_dict(migrate(data))

    def save(self, settings: Settings) -> None:
        """Write settings atomically."""
        payload = json.dumps(settings.to_dict(), indent=2, sort_keys=False) + "\n"
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, self._path)
        except OSError as error:
            _LOGGER.warning("could not save settings to %s: %s", self._path, error)
            temporary.unlink(missing_ok=True)

    def exists(self) -> bool:
        return self._path.is_file()

    def _quarantine(self, reason: str) -> None:
        backup = self._path.with_name(self._path.name + ".corrupt")
        try:
            os.replace(self._path, backup)
            _LOGGER.warning("moved the unusable settings file aside (%s): %s", reason, backup)
        except OSError as error:  # pragma: no cover - only reachable with an unwritable directory
            _LOGGER.warning("could not move the unusable settings file aside: %s", error)


__all__ = [
    "APP_DIRECTORY",
    "CONFIG_FILE",
    "DEFAULT_WINDOW_HEIGHT",
    "DEFAULT_WINDOW_WIDTH",
    "MIGRATIONS",
    "SCHEMA_VERSION",
    "Settings",
    "SettingsStore",
    "cache_dir",
    "config_dir",
    "migrate",
    "state_dir",
]
