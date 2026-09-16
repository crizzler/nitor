"""The effect catalogue: contents, limits and request validation.

The pinned id lists below are the contract between the drivers' capabilities and what the interface
offers. If upstream changes or the tables are edited, these fail loudly.
"""

from __future__ import annotations

import pytest

from nitor.domain import (
    DEFAULT_DIRECTION,
    DEFAULT_SPEED,
    FAMILY_HUE2,
    FAMILY_KRAKEN,
    Color,
    EffectError,
    effects_for_family,
    get_effect,
    validate_request,
)

HUE2_ORDER = [
    "off",
    "fixed",
    "super-fixed",
    "fading",
    "breathing",
    "pulse",
    "super-breathing",
    "marquee-3",
    "marquee-4",
    "marquee-5",
    "marquee-6",
    "covering-marquee",
    "alternating-3",
    "moving-alternating-3",
    "alternating-4",
    "moving-alternating-4",
    "alternating-5",
    "moving-alternating-5",
    "alternating-6",
    "moving-alternating-6",
    "spectrum-wave",
    "rainbow-flow",
    "super-rainbow",
    "rainbow-pulse",
    "candle",
    "starry-night",
    "wings",
]

KRAKEN_ORDER = [
    *HUE2_ORDER[:24],
    "loading",
    "tai-chi",
    "water-cooler",
    *HUE2_ORDER[24:],
]


def test_hue2_effects_match_the_driver_table() -> None:
    assert [effect.id for effect in effects_for_family(FAMILY_HUE2)] == HUE2_ORDER


def test_kraken_effects_match_the_driver_table() -> None:
    assert [effect.id for effect in effects_for_family(FAMILY_KRAKEN)] == KRAKEN_ORDER


def test_unknown_family_is_rejected() -> None:
    with pytest.raises(EffectError):
        effects_for_family("homebrew")


def test_unknown_effect_lists_what_is_available() -> None:
    with pytest.raises(EffectError) as info:
        get_effect(FAMILY_HUE2, "super-saiyan")
    assert "super-saiyan" in info.value.message
    assert info.value.hint is not None


@pytest.mark.parametrize(
    ("effect_id", "min_colors", "max_colors", "speed", "direction"),
    [
        ("off", 0, 0, False, False),
        ("fixed", 1, 1, False, False),
        ("super-fixed", 1, 40, False, False),
        ("fading", 1, 8, True, False),
        ("breathing", 1, 8, True, False),
        ("pulse", 1, 8, True, False),
        ("spectrum-wave", 0, 0, True, True),
        ("marquee-3", 1, 1, True, True),
        ("covering-marquee", 1, 8, True, True),
        ("alternating-3", 2, 2, True, False),
        ("moving-alternating-6", 2, 2, True, True),
        ("candle", 1, 1, False, False),
        ("starry-night", 1, 1, True, False),
        ("wings", 1, 1, True, False),
    ],
)
def test_colour_limits_follow_the_firmware(
    effect_id: str,
    min_colors: int,
    max_colors: int,
    speed: bool,
    direction: bool,
) -> None:
    effect = get_effect(FAMILY_HUE2, effect_id)
    assert (effect.min_colors, effect.max_colors) == (min_colors, max_colors)
    assert effect.supports_speed is speed
    assert effect.supports_direction is direction


def test_liquid_coolers_accept_a_single_colour_for_alternating() -> None:
    assert get_effect(FAMILY_KRAKEN, "alternating-3").min_colors == 1
    assert get_effect(FAMILY_HUE2, "alternating-3").min_colors == 2


def test_extra_colours_are_trimmed_to_what_the_effect_accepts() -> None:
    colors = tuple(Color(index, index, index) for index in range(12))
    validated = validate_request(FAMILY_HUE2, "fading", colors)
    assert len(validated.colors) == 8
    assert validated.colors[0] == colors[0]


def test_too_few_colours_is_an_error() -> None:
    with pytest.raises(EffectError):
        validate_request(FAMILY_HUE2, "fading", ())
    with pytest.raises(EffectError):
        validate_request(FAMILY_KRAKEN, "water-cooler", (Color(1, 1, 1),))


def test_colourless_effects_discard_colours() -> None:
    validated = validate_request(FAMILY_HUE2, "off", (Color(255, 0, 0),))
    assert validated.colors == ()


def test_speed_and_direction_are_dropped_where_the_effect_ignores_them() -> None:
    validated = validate_request(
        FAMILY_HUE2,
        "fixed",
        (Color(255, 0, 0),),
        speed="fastest",
        direction="backward",
    )
    assert validated.speed == DEFAULT_SPEED
    assert validated.direction == DEFAULT_DIRECTION


def test_speed_and_direction_are_kept_where_they_matter() -> None:
    validated = validate_request(
        FAMILY_HUE2,
        "marquee-4",
        (Color(255, 0, 0),),
        speed="faster",
        direction="backward",
    )
    assert validated.speed == "faster"
    assert validated.direction == "backward"


@pytest.mark.parametrize(("speed", "direction"), [("turbo", "forward"), ("normal", "sideways")])
def test_invalid_speed_or_direction_is_rejected(speed: str, direction: str) -> None:
    with pytest.raises(EffectError):
        validate_request(
            FAMILY_HUE2,
            "marquee-4",
            (Color(255, 0, 0),),
            speed=speed,
            direction=direction,
        )
