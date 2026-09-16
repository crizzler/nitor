"""The headless startup path used by ``nitor --apply-saved`` and the systemd unit."""

from __future__ import annotations

from dataclasses import replace

from nitor.backend.liquidctl_cli import LiquidctlBackend
from nitor.backend.mock import MockBackend, mock_devices
from nitor.backend.registry import MODE_MOCK, create_backend
from nitor.domain import Color, Device, LightingState, NZXT_VENDOR_ID, lookup_profile
from nitor.services.settings import Settings
from nitor.services.startup import EXIT_BACKEND_MISSING, EXIT_FAILED, EXIT_OK, apply_saved

#: The mock controller's real device key, serial number included.
CONTROLLER_KEY = mock_devices()[0].key


def controller() -> Device:
    return Device(
        key="1e71:2010",
        description="NZXT RGB & Fan Controller",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2010,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2010),
    )


def settings_with(state: LightingState, key: str = CONTROLLER_KEY) -> Settings:
    settings = Settings(selected_device=key)
    settings.set_lighting(key, state)
    return settings


def test_saved_lighting_is_applied() -> None:
    backend = MockBackend()
    settings = settings_with(
        LightingState(channel="led2", effect="fixed", colors=(Color(0, 170, 255),))
    )

    outcome = apply_saved(backend, settings)

    assert outcome.exit_code == EXIT_OK
    assert outcome.ok is True
    assert len(outcome.applied) == 1
    assert outcome.applied[0].channel == "led2"
    assert backend.last_applied is not None
    assert backend.last_applied.argv[-4:] == ("led2", "color", "fixed", "00aaff")


def test_no_controller_connected_is_not_a_failure() -> None:
    """A controller that is simply unplugged must not make the login service report a failure."""
    backend = MockBackend(devices=[])
    outcome = apply_saved(backend, settings_with(LightingState(channel="led1")))
    assert outcome.exit_code == EXIT_OK
    assert "No supported NZXT controller" in outcome.message


def test_nothing_saved_is_not_a_failure() -> None:
    outcome = apply_saved(MockBackend(), Settings())
    assert outcome.exit_code == EXIT_OK
    assert "No saved lighting" in outcome.message


def test_a_missing_backend_is_reported_separately() -> None:
    backend = LiquidctlBackend("definitely-not-liquidctl")
    outcome = apply_saved(backend, settings_with(LightingState(channel="led1")))
    assert outcome.exit_code == EXIT_BACKEND_MISSING
    assert outcome.applied == ()


def test_permission_problems_are_failures() -> None:
    backend = MockBackend(permission_denied=True)
    outcome = apply_saved(backend, settings_with(LightingState(channel="led1")))
    assert outcome.exit_code == EXIT_FAILED
    assert "denied access" in outcome.message


def test_a_state_saved_for_another_key_is_still_used_when_there_is_one_device() -> None:
    renamed = replace(controller(), key="1e71:2010:NEW-SERIAL")
    backend = MockBackend(devices=[renamed])
    settings = settings_with(LightingState(channel="led1"), key="1e71:2010:OLD-SERIAL")

    outcome = apply_saved(backend, settings)

    assert outcome.exit_code == EXIT_OK
    assert len(outcome.applied) == 1


def test_an_impossible_saved_state_is_normalised_rather_than_failing() -> None:
    """Settings written for different hardware must not break the login service."""
    backend = MockBackend()
    kraken_state = LightingState(
        channel="external", effect="water-cooler", colors=(Color(255, 0, 0), Color(0, 0, 255))
    )
    settings = settings_with(kraken_state)

    outcome = apply_saved(backend, settings)

    assert outcome.exit_code == EXIT_OK
    assert backend.last_applied is not None
    # water-cooler is not a fan-controller effect, so it must not be sent as-is.
    assert backend.last_applied.effect != "water-cooler"


def test_devices_without_lighting_are_skipped() -> None:
    unsupported = Device(
        key="1e71:2011",
        description="NZXT RGB & Fan Controller (3+6 channels)",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2011,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2011),
    )
    outcome = apply_saved(
        MockBackend(devices=[unsupported]), settings_with(LightingState(channel="led1"))
    )
    assert outcome.exit_code == EXIT_OK
    assert "No supported NZXT controller" in outcome.message


def test_the_mock_backend_can_be_built_through_the_registry() -> None:
    backend = create_backend(MODE_MOCK)
    assert backend.is_mock is True
    assert apply_saved(backend, Settings()).exit_code == EXIT_OK
