"""Device capability mapping and lighting-state normalisation."""

from __future__ import annotations

import pytest

from nitor.domain import (
    NZXT_VENDOR_ID,
    Color,
    Device,
    InvalidStateError,
    LightingState,
    lookup_profile,
)


def make_device(product_id: int, *, serial: str | None = "SN1") -> Device:
    profile = lookup_profile(NZXT_VENDOR_ID, product_id)
    return Device(
        key=f"1e71:{product_id:04x}",
        description=profile.description if profile else "Unknown",
        vendor_id=NZXT_VENDOR_ID,
        product_id=product_id,
        profile=profile,
        serial=serial,
    )


def test_rgb_and_fan_controller_channels() -> None:
    capabilities = make_device(0x2010).capabilities
    assert [channel.id for channel in capabilities.channels] == ["led1", "led2", "sync"]
    assert capabilities.family == "hue2"
    assert capabilities.supports_lighting
    assert capabilities.native_brightness is False


def test_kraken_z_has_only_the_external_channel() -> None:
    capabilities = make_device(0x3008).capabilities
    assert [channel.id for channel in capabilities.channels] == ["external"]
    assert "ring" not in {channel.id for channel in capabilities.channels}
    assert "logo" not in {channel.id for channel in capabilities.channels}
    assert capabilities.family == "kraken"


def test_kraken_x_models_do_have_ring_and_logo() -> None:
    channels = [channel.id for channel in make_device(0x2007).capabilities.channels]
    assert channels == ["external", "ring", "logo", "sync"]


def test_models_without_lighting_support_expose_no_channels_and_say_why() -> None:
    device = make_device(0x2011)
    assert device.profile is not None
    assert device.profile.controllable is False
    assert device.profile.note is not None
    capabilities = device.capabilities
    assert capabilities.channels == ()
    assert capabilities.effects == ()
    assert capabilities.supports_lighting is False


def test_unknown_model_is_reported_as_unsupported() -> None:
    device = Device(
        key="1e71:9999",
        description="NZXT mystery device",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x9999,
    )
    assert device.profile is None
    assert device.is_supported is False
    assert device.capabilities.supports_lighting is False


def test_default_channel_prefers_one_with_accessories() -> None:
    device = make_device(0x2010)
    with_accessories = device.with_channels(
        (
            *device.capabilities.channels[:1],
            *device.capabilities.channels[1:],
        )
    )
    assert with_accessories.capabilities.default_channel == "led1"


def test_usb_id_and_display_name() -> None:
    device = make_device(0x2010)
    assert device.usb_id == "1e71:2010"
    assert device.display_name == "NZXT RGB & Fan Controller"


def test_brightness_is_range_checked() -> None:
    assert LightingState(brightness=0).brightness == 0
    assert LightingState(brightness=100).brightness == 100
    with pytest.raises(InvalidStateError):
        LightingState(brightness=101)
    with pytest.raises(InvalidStateError):
        LightingState(brightness=-1)
    with pytest.raises(InvalidStateError):
        LightingState(brightness="bright")  # type: ignore[arg-type]


def test_effective_colours_apply_brightness() -> None:
    state = LightingState(effect="fixed", colors=(Color(0, 170, 255),), brightness=50)
    assert [color.to_hex() for color in state.effective_colors()] == ["#005580"]


def test_effective_colours_are_unchanged_at_full_brightness() -> None:
    state = LightingState(effect="fixed", colors=(Color(0, 170, 255),), brightness=100)
    assert state.effective_colors() == state.colors


def test_preview_never_goes_fully_black() -> None:
    state = LightingState(effect="fixed", colors=(Color(255, 255, 255),), brightness=0)
    assert all(color.to_rgb_tuple() != (0, 0, 0) for color in state.preview_colors())


def test_normalising_repairs_a_state_from_other_hardware() -> None:
    capabilities = make_device(0x3008).capabilities  # Kraken: external only, kraken family
    state = LightingState(
        channel="led2",
        effect="alternating-3",
        colors=(Color(255, 0, 0),),  # kraken allows one colour here, hue2 does not
        brightness=100,
    )
    normalized = state.normalized(capabilities)
    assert normalized.channel == "external"
    assert normalized.effect == "alternating-3"


def test_normalising_replaces_an_effect_the_device_cannot_render() -> None:
    capabilities = make_device(0x2010).capabilities
    state = LightingState(channel="led1", effect="water-cooler", colors=(Color(1, 1, 1),))
    normalized = state.normalized(capabilities)
    assert normalized.effect == "fixed"


def test_lighting_state_round_trips_through_persistence() -> None:
    state = LightingState(
        channel="led2",
        effect="fading",
        colors=(Color(0, 170, 255), Color(255, 0, 0)),
        brightness=80,
        speed="faster",
        direction="backward",
    )
    assert LightingState.from_dict(state.to_dict()) == state


def test_lighting_state_survives_corrupt_persisted_data() -> None:
    state = LightingState.from_dict(
        {
            "channel": 5,
            "effect": None,
            "colors": ["#00AAFF", "not-a-colour", 12],
            "brightness": "loud",
            "speed": 7,
            "direction": [],
        }
    )
    assert state.channel == ""
    assert state.effect == "fixed"
    assert [color.to_hex() for color in state.colors] == ["#00AAFF"]
    assert state.brightness == 100
    assert state.speed == "normal"
    assert state.direction == "forward"


def test_colour_slots_can_be_filled_incrementally() -> None:
    state = LightingState(effect="fading", colors=(Color(255, 0, 0),))
    extended = state.with_color(2, Color(0, 255, 0))
    assert [color.to_hex() for color in extended.colors] == ["#FF0000", "#FF0000", "#00FF00"]
    with pytest.raises(InvalidStateError):
        state.with_color(-1, Color(0, 0, 0))
