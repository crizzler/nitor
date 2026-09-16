"""Settings persistence: defaults, round trips, migrations and damaged files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nitor.domain import Color, LightingState
from nitor.services.settings import (
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MIGRATIONS,
    SCHEMA_VERSION,
    Settings,
    SettingsStore,
    config_dir,
    migrate,
    state_dir,
)


@pytest.fixture
def store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(tmp_path / "nitor" / "config.json")


def sample_state() -> LightingState:
    return LightingState(
        channel="led2",
        effect="fading",
        colors=(Color(0, 170, 255), Color(255, 0, 0)),
        brightness=70,
        speed="faster",
        direction="backward",
    )


def test_defaults_when_nothing_was_saved(store: SettingsStore) -> None:
    settings = store.load()
    assert settings.schema_version == SCHEMA_VERSION
    assert settings.apply_on_login is False
    assert settings.selected_device is None
    assert settings.lighting == {}
    assert (settings.window_width, settings.window_height) == (
        DEFAULT_WINDOW_WIDTH,
        DEFAULT_WINDOW_HEIGHT,
    )
    assert store.exists() is False


def test_settings_round_trip(store: SettingsStore) -> None:
    settings = Settings(apply_on_login=True, selected_device="1e71:2010:SN1")
    settings.set_lighting("1e71:2010:SN1", sample_state())
    settings.window_width = 1200
    settings.window_height = 800
    store.save(settings)

    loaded = store.load()
    assert loaded.apply_on_login is True
    assert loaded.selected_device == "1e71:2010:SN1"
    assert loaded.window_width == 1200
    assert loaded.lighting_for("1e71:2010:SN1") == sample_state()


def test_saving_creates_the_directory_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "nested" / "config.json"
    store = SettingsStore(path)
    store.save(Settings())
    assert path.is_file()
    assert list(path.parent.glob("*.tmp")) == []


def test_a_corrupt_file_is_moved_aside_rather_than_deleted(store: SettingsStore) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text("{ this is not json", encoding="utf-8")

    settings = store.load()
    assert settings == Settings()
    assert store.exists() is False
    assert store.path.with_name(store.path.name + ".corrupt").is_file()


def test_a_json_file_that_is_not_an_object_is_also_moved_aside(store: SettingsStore) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text('["not", "settings"]', encoding="utf-8")
    assert store.load() == Settings()
    assert store.path.with_name(store.path.name + ".corrupt").is_file()


def test_settings_from_a_newer_version_are_left_completely_alone(store: SettingsStore) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    future = {"schema_version": SCHEMA_VERSION + 5, "apply_on_login": True, "unknown": 1}
    store.path.write_text(json.dumps(future), encoding="utf-8")

    assert store.load() == Settings()
    assert json.loads(store.path.read_text(encoding="utf-8")) == future


def test_older_settings_are_migrated(store: SettingsStore) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps(
            {
                "schema_version": 0,
                "apply_on_login": True,
                "color": "#00AAFF",
                "effect": "fixed",
            }
        ),
        encoding="utf-8",
    )

    settings = store.load()
    assert settings.schema_version == SCHEMA_VERSION
    assert settings.apply_on_login is True
    assert "color" not in settings.to_dict()
    assert "effect" not in settings.to_dict()


def test_every_older_schema_has_a_migration() -> None:
    """Adding a schema version without a migration would silently reset user settings."""
    for version in range(SCHEMA_VERSION):
        assert version in MIGRATIONS


def test_migration_of_unknown_versions_falls_back_to_defaults() -> None:
    assert migrate({"schema_version": -5}) == {"schema_version": SCHEMA_VERSION}


def test_a_newer_schema_is_passed_through_untouched() -> None:
    """Stored data from a newer release must not be rewritten or reset by an older one."""
    assert migrate({"schema_version": 99}) == {"schema_version": 99}


def test_malformed_values_are_ignored_rather_than_fatal(store: SettingsStore) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "apply_on_login": "yes please",
                "selected_device": 42,
                "window": "not a dictionary",
                "lighting": {"dev": "not a dictionary", "other": {"colors": ["#00AAFF"]}},
            }
        ),
        encoding="utf-8",
    )

    settings = store.load()
    assert settings.selected_device is None
    assert settings.apply_on_login is True  # truthy values are accepted
    assert settings.window_width == DEFAULT_WINDOW_WIDTH
    assert list(settings.lighting) == ["other"]
    assert settings.lighting["other"].colors[0].to_hex() == "#00AAFF"


def test_window_sizes_are_clamped(store: SettingsStore) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "window": {"width": 1, "height": 999999}}),
        encoding="utf-8",
    )
    settings = store.load()
    assert settings.window_width >= 640
    assert settings.window_height <= 8000


def test_lighting_can_be_looked_up_and_replaced(store: SettingsStore) -> None:
    settings = Settings()
    assert settings.lighting_for("dev") is None
    settings.set_lighting("dev", sample_state())
    assert settings.lighting_for("dev") == sample_state()
    settings.set_lighting("dev", sample_state().with_brightness(10))
    assert settings.lighting_for("dev") is not None
    assert settings.lighting_for("dev").brightness == 10  # type: ignore[union-attr]


def test_directories_follow_the_xdg_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "st"))
    assert config_dir() == tmp_path / "cfg" / "nitor"
    assert state_dir() == tmp_path / "st" / "nitor"


def test_directories_fall_back_to_the_home_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert config_dir() == tmp_path / ".config" / "nitor"
