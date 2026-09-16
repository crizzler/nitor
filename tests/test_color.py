"""Colour parsing, conversion and dimming."""

from __future__ import annotations

import pytest

from nitor.domain import PRESETS, Color, InvalidColorError, parse_color


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#00AAFF", (0, 170, 255)),
        ("00aaff", (0, 170, 255)),
        ("0x00AAFF", (0, 170, 255)),
        ("  #00AAFF  ", (0, 170, 255)),
        ("#FFF", (255, 255, 255)),
        ("abc", (170, 187, 204)),
        ("#000000", (0, 0, 0)),
    ],
)
def test_from_hex_accepts_the_forms_users_type(text: str, expected: tuple[int, int, int]) -> None:
    assert Color.from_hex(text).to_rgb_tuple() == expected


@pytest.mark.parametrize(
    "text", ["", "#12345", "gggggg", "#1234567", "not a colour", "12345", "#-123"]
)
def test_from_hex_rejects_nonsense(text: str) -> None:
    with pytest.raises(InvalidColorError):
        Color.from_hex(text)


def test_invalid_colour_error_explains_itself() -> None:
    with pytest.raises(InvalidColorError) as info:
        Color.from_hex("nope")
    assert "not a valid colour" in info.value.message
    assert info.value.hint is not None


@pytest.mark.parametrize("component", [-1, 256, 1.5, "10", True])
def test_components_are_validated(component: object) -> None:
    with pytest.raises(InvalidColorError):
        Color(component, 0, 0)  # type: ignore[arg-type]


def test_hex_output_is_canonical() -> None:
    assert Color(0, 170, 255).to_hex() == "#00AAFF"
    assert Color(0, 170, 255).to_liquidctl() == "00aaff"


@pytest.mark.parametrize(
    ("hue", "saturation", "value"), [(0, 100, 100), (210, 100, 50), (359, 20, 80), (120, 0, 50)]
)
def test_hsv_round_trip_is_stable(hue: float, saturation: float, value: float) -> None:
    color = Color.from_hsv(hue, saturation, value)
    back_hue, back_saturation, back_value = color.to_hsv()
    if saturation == 0:
        assert back_saturation == pytest.approx(0, abs=1)
        assert back_value == pytest.approx(value, abs=1)
    else:
        assert back_hue == pytest.approx(hue % 360, abs=2)
        assert back_saturation == pytest.approx(saturation, abs=2)


def test_hsv_is_clamped_rather_than_rejected() -> None:
    assert Color.from_hsv(-40, 500, 500) == Color.from_hsv(0, 100, 100)


def test_white_is_the_brightest_and_black_the_darkest() -> None:
    assert Color(255, 255, 255).relative_luminance() == pytest.approx(1.0)
    assert Color(0, 0, 0).relative_luminance() == pytest.approx(0.0)


def test_dark_text_is_preferred_on_light_colours_only() -> None:
    assert Color(255, 255, 255).prefers_dark_text()
    assert Color(0, 170, 255).prefers_dark_text() is False


@pytest.mark.parametrize("percent", [0, 25, 50, 100])
def test_dimming_scales_components(percent: int) -> None:
    color = Color(200, 100, 50).dimmed(percent)
    assert color.to_rgb_tuple() == (
        round(200 * percent / 100),
        round(100 * percent / 100),
        round(50 * percent / 100),
    )


def test_dimming_cannot_leave_the_valid_range() -> None:
    assert Color(255, 255, 255).dimmed(-50).to_rgb_tuple() == (0, 0, 0)
    assert Color(255, 255, 255).dimmed(500).to_rgb_tuple() == (255, 255, 255)


def test_presets_are_the_documented_set() -> None:
    assert [name for name, _ in PRESETS] == [
        "White",
        "Red",
        "Green",
        "Blue",
        "Cyan",
        "Purple",
        "Orange",
    ]
    assert len({color.to_hex() for _, color in PRESETS}) == len(PRESETS)


def test_colours_can_be_named() -> None:
    assert Color.from_name("cyan") == dict(PRESETS)["Cyan"]
    with pytest.raises(InvalidColorError):
        Color.from_name("chartreuse")


def test_parse_color_accepts_all_convenient_forms() -> None:
    assert parse_color("#00AAFF") == Color(0, 170, 255)
    assert parse_color("Blue") == dict(PRESETS)["Blue"]
    assert parse_color((1, 2, 3)) == Color(1, 2, 3)
    assert parse_color(Color(1, 2, 3)) == Color(1, 2, 3)
    with pytest.raises(InvalidColorError):
        parse_color(12)  # type: ignore[arg-type]
