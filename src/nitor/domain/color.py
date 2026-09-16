"""RGB colour value object and the parsing rules the user interface relies on."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from typing import Final

from .errors import InvalidColorError

_HEX_PATTERN: Final = re.compile(r"^(?:#|0x)?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

MIN_COMPONENT: Final = 0
MAX_COMPONENT: Final = 255
MAX_HUE: Final = 360.0
MAX_PERCENT: Final = 100.0


@dataclass(frozen=True, slots=True)
class Color:
    """An RGB colour with components in the range 0-255."""

    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        for label, value in (("red", self.r), ("green", self.g), ("blue", self.b)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidColorError(f"The {label} component must be a whole number.")
            if not MIN_COMPONENT <= value <= MAX_COMPONENT:
                raise InvalidColorError(
                    f"The {label} component must be between {MIN_COMPONENT} and {MAX_COMPONENT}."
                )

    # -- construction ---------------------------------------------------------------------

    @classmethod
    def from_hex(cls, text: str) -> Color:
        """Parse ``#RRGGBB``, ``RRGGBB``, ``#RGB``, ``RGB`` or ``0xRRGGBB``.

        Surrounding whitespace is ignored. Anything else raises :class:`InvalidColorError`.
        """
        if not isinstance(text, str):
            raise InvalidColorError("A colour must be given as text.")
        candidate = text.strip()
        match = _HEX_PATTERN.match(candidate)
        if not match:
            raise InvalidColorError(
                f"'{text}' is not a valid colour.",
                hint="Use six hexadecimal digits, for example #00AAFF.",
            )
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(character * 2 for character in digits)
        return cls(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))

    @classmethod
    def from_hsv(cls, hue: float, saturation: float, value: float) -> Color:
        """Build a colour from hue (0-360), saturation (0-100) and value (0-100)."""
        hue = _clamp(float(hue), 0.0, MAX_HUE)
        saturation = _clamp(float(saturation), 0.0, MAX_PERCENT) / MAX_PERCENT
        value = _clamp(float(value), 0.0, MAX_PERCENT) / MAX_PERCENT
        red, green, blue = colorsys.hsv_to_rgb(hue / MAX_HUE, saturation, value)
        return cls(
            round(red * MAX_COMPONENT), round(green * MAX_COMPONENT), round(blue * MAX_COMPONENT)
        )

    @classmethod
    def from_name(cls, name: str) -> Color:
        """Look up one of the preset colours by name (case insensitive)."""
        key = name.strip().lower()
        for preset_name, preset in PRESETS:
            if preset_name.lower() == key:
                return preset
        raise InvalidColorError(
            f"'{name}' is not a known colour name.",
            hint="Known colours: " + ", ".join(preset[0] for preset in PRESETS) + ".",
        )

    # -- conversion -----------------------------------------------------------------------

    def to_hex(self) -> str:
        """Return the canonical ``#RRGGBB`` representation used throughout the interface."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def to_hsv(self) -> tuple[float, float, float]:
        """Return hue (0-360), saturation (0-100) and value (0-100)."""
        hue, saturation, value = colorsys.rgb_to_hsv(
            self.r / MAX_COMPONENT, self.g / MAX_COMPONENT, self.b / MAX_COMPONENT
        )
        return (hue * MAX_HUE, saturation * MAX_PERCENT, value * MAX_PERCENT)

    def to_liquidctl(self) -> str:
        """Return the ``rrggbb`` form liquidctl accepts on the command line."""
        return f"{self.r:02x}{self.g:02x}{self.b:02x}"

    def to_rgb_tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    # -- appearance -----------------------------------------------------------------------

    def relative_luminance(self) -> float:
        """Perceived brightness in the range 0.0-1.0 (sRGB weights, normalised)."""
        return (0.2126 * self.r + 0.7152 * self.g + 0.0722 * self.b) / MAX_COMPONENT

    def prefers_dark_text(self) -> bool:
        """Whether black text reads better than white text on top of this colour."""
        return self.relative_luminance() > 0.6

    def dimmed(self, percent: float) -> Color:
        """Scale the colour towards black by ``percent`` (0-100).

        Used for the application-level brightness control: the HUE 2 protocol and the Kraken
        drivers expose no brightness command, so dimming happens here instead of being pretended.
        """
        factor = _clamp(float(percent), 0.0, MAX_PERCENT) / MAX_PERCENT
        return Color(round(self.r * factor), round(self.g * factor), round(self.b * factor))

    # -- helpers --------------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Color({self.to_hex()})"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


WHITE: Final = Color(255, 255, 255)

#: The deliberately small preset palette offered in the user interface.
PRESETS: Final[tuple[tuple[str, Color], ...]] = (
    ("White", Color(255, 255, 255)),
    ("Red", Color(255, 32, 32)),
    ("Green", Color(32, 255, 96)),
    ("Blue", Color(32, 96, 255)),
    ("Cyan", Color(0, 170, 255)),
    ("Purple", Color(160, 64, 255)),
    ("Orange", Color(255, 112, 24)),
)


def parse_color(value: str | Color | tuple[int, int, int]) -> Color:
    """Coerce a hex string, a preset name or an RGB tuple into a :class:`Color`."""
    if isinstance(value, Color):
        return value
    if isinstance(value, str):
        text = value.strip()
        if _HEX_PATTERN.match(text):
            return Color.from_hex(text)
        return Color.from_name(text)
    if isinstance(value, tuple) and len(value) == 3:
        return Color(*value)
    raise InvalidColorError(f"Cannot interpret {value!r} as a colour.")
