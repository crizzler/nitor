"""The effect catalogue, transcribed from the liquidctl drivers.

Two families exist because the hardware differs. Both tables were read from upstream
``liquidctl.driver.smart_device.SmartDevice2._COLOR_MODES`` (HUE 2 generation: Smart Device V2,
HUE 2, RGB & Fan Controller) and ``liquidctl.driver.kraken3._COLOR_MODES`` (fourth-generation
Kraken X3/Z3 and later), together with the matching device guides.

Only effects listed for the selected device are ever offered in the user interface, and the number
of colour slots follows the selected effect's own limits, so no control can silently do nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .color import Color
from .errors import EffectError

SPEEDS: Final[tuple[str, ...]] = ("slowest", "slower", "normal", "faster", "fastest")
DEFAULT_SPEED: Final = "normal"

DIRECTIONS: Final[tuple[str, ...]] = ("forward", "backward")
DEFAULT_DIRECTION: Final = "forward"

OFF_EFFECT: Final = "off"
DEFAULT_EFFECT: Final = "fixed"

#: Device families, named after the liquidctl driver generation that supports them.
FAMILY_HUE2: Final = "hue2"
FAMILY_KRAKEN: Final = "kraken"

# User-interface groupings. They only affect presentation.
GROUP_BASIC: Final = "Basic"
GROUP_PER_LED: Final = "Per LED"
GROUP_FADE: Final = "Fading"
GROUP_MARQUEE: Final = "Marquee"
GROUP_ALTERNATE: Final = "Alternating"
GROUP_RAINBOW: Final = "Rainbow"
GROUP_PLAYFUL: Final = "Playful"


@dataclass(frozen=True, slots=True)
class EffectSpec:
    """One effect a device can render, with the limits its firmware enforces."""

    id: str
    label: str
    group: str
    min_colors: int = 0
    max_colors: int = 0
    supports_speed: bool = False
    supports_direction: bool = False

    @property
    def uses_colors(self) -> bool:
        """Whether this effect takes a colour at all (``off`` and the rainbow modes do not)."""
        return self.max_colors > 0

    @property
    def supports_multiple_colors(self) -> bool:
        return self.max_colors > 1


def _marquee_effects() -> tuple[EffectSpec, ...]:
    return tuple(
        EffectSpec(
            id=f"marquee-{length}",
            label=f"Marquee ({length} LEDs)",
            group=GROUP_MARQUEE,
            min_colors=1,
            max_colors=1,
            supports_speed=True,
            supports_direction=True,
        )
        for length in (3, 4, 5, 6)
    )


def _alternating_effects(*, min_colors: int) -> tuple[EffectSpec, ...]:
    effects: list[EffectSpec] = []
    for length in (3, 4, 5, 6):
        effects.append(
            EffectSpec(
                id=f"alternating-{length}",
                label=f"Alternating ({length} LEDs)",
                group=GROUP_ALTERNATE,
                min_colors=min_colors,
                max_colors=2,
                supports_speed=True,
            )
        )
        effects.append(
            EffectSpec(
                id=f"moving-alternating-{length}",
                label=f"Moving alternating ({length} LEDs)",
                group=GROUP_ALTERNATE,
                min_colors=min_colors,
                max_colors=2,
                supports_speed=True,
                supports_direction=True,
            )
        )
    return tuple(effects)


#: Effects shared by the HUE 2 generation and the fourth-generation Kraken coolers.
_COMMON_EFFECTS: Final[tuple[EffectSpec, ...]] = (
    EffectSpec(id=OFF_EFFECT, label="Off", group=GROUP_BASIC),
    EffectSpec(id="fixed", label="Fixed", group=GROUP_BASIC, min_colors=1, max_colors=1),
    EffectSpec(
        id="fading",
        label="Fading",
        group=GROUP_FADE,
        min_colors=1,
        max_colors=8,
        supports_speed=True,
    ),
    EffectSpec(
        id="breathing",
        label="Breathing",
        group=GROUP_FADE,
        min_colors=1,
        max_colors=8,
        supports_speed=True,
    ),
    EffectSpec(
        id="pulse",
        label="Pulse",
        group=GROUP_FADE,
        min_colors=1,
        max_colors=8,
        supports_speed=True,
    ),
    *_marquee_effects(),
    EffectSpec(
        id="covering-marquee",
        label="Covering marquee",
        group=GROUP_MARQUEE,
        min_colors=1,
        max_colors=8,
        supports_speed=True,
        supports_direction=True,
    ),
    EffectSpec(
        id="spectrum-wave",
        label="Spectrum wave",
        group=GROUP_RAINBOW,
        supports_speed=True,
        supports_direction=True,
    ),
    EffectSpec(
        id="rainbow-flow",
        label="Rainbow flow",
        group=GROUP_RAINBOW,
        supports_speed=True,
        supports_direction=True,
    ),
    EffectSpec(
        id="super-rainbow",
        label="Super rainbow",
        group=GROUP_RAINBOW,
        supports_speed=True,
        supports_direction=True,
    ),
    EffectSpec(
        id="rainbow-pulse",
        label="Rainbow pulse",
        group=GROUP_RAINBOW,
        supports_speed=True,
        supports_direction=True,
    ),
    EffectSpec(id="candle", label="Candle", group=GROUP_PLAYFUL, min_colors=1, max_colors=1),
    EffectSpec(
        id="starry-night",
        label="Starry night",
        group=GROUP_PLAYFUL,
        min_colors=1,
        max_colors=1,
        supports_speed=True,
    ),
    EffectSpec(
        id="wings",
        label="Wings",
        group=GROUP_PLAYFUL,
        min_colors=1,
        max_colors=1,
        supports_speed=True,
    ),
)

_SUPER_FIXED: Final = EffectSpec(
    id="super-fixed",
    label="Super fixed (per LED)",
    group=GROUP_PER_LED,
    min_colors=1,
    max_colors=40,
)
_SUPER_BREATHING: Final = EffectSpec(
    id="super-breathing",
    label="Super breathing (per LED)",
    group=GROUP_PER_LED,
    min_colors=1,
    max_colors=40,
    supports_speed=True,
)

# Layout of ``_COMMON_EFFECTS``, used by the family tables below:
#   0 off, 1 fixed, 2 fading, 3 breathing, 4 pulse, 5-8 marquee-3..6, 9 covering-marquee,
#   10 spectrum-wave, 11 rainbow-flow, 12 super-rainbow, 13 rainbow-pulse, 14 candle,
#   15 starry-night, 16 wings.
# ``tests/test_effects.py`` pins the resulting effect order for both families.

#: HUE 2 generation: Smart Device V2, HUE 2, HUE 2 Ambient and the RGB & Fan Controller.
HUE2_EFFECTS: Final[tuple[EffectSpec, ...]] = (
    *_COMMON_EFFECTS[0:2],  # off, fixed
    _SUPER_FIXED,
    *_COMMON_EFFECTS[2:5],  # fading, breathing, pulse
    _SUPER_BREATHING,
    *_COMMON_EFFECTS[5:10],  # the marquees and covering marquee
    *_alternating_effects(min_colors=2),
    *_COMMON_EFFECTS[10:14],  # spectrum wave and the rainbow modes
    *_COMMON_EFFECTS[14:17],  # candle, starry night, wings
)

#: Fourth-generation Kraken: X3/Z3 and later. Note that ``alternating`` accepts a single colour
#: here, and that the liquid cooler firmware knows three effects the fan controllers do not.
KRAKEN_EFFECTS: Final[tuple[EffectSpec, ...]] = (
    *_COMMON_EFFECTS[0:2],  # off, fixed
    _SUPER_FIXED,
    *_COMMON_EFFECTS[2:5],  # fading, breathing, pulse
    _SUPER_BREATHING,
    *_COMMON_EFFECTS[5:10],  # the marquees and covering marquee
    *_alternating_effects(min_colors=1),
    *_COMMON_EFFECTS[10:14],  # spectrum wave and the rainbow modes
    EffectSpec(
        id="loading",
        label="Loading",
        group=GROUP_PLAYFUL,
        min_colors=1,
        max_colors=1,
        supports_speed=True,
    ),
    EffectSpec(
        id="tai-chi",
        label="Tai chi",
        group=GROUP_PLAYFUL,
        min_colors=1,
        max_colors=2,
        supports_speed=True,
    ),
    EffectSpec(
        id="water-cooler",
        label="Water cooler",
        group=GROUP_PLAYFUL,
        min_colors=2,
        max_colors=2,
        supports_speed=True,
    ),
    *_COMMON_EFFECTS[14:17],  # candle, starry night, wings
)

EFFECTS_BY_FAMILY: Final[dict[str, tuple[EffectSpec, ...]]] = {
    FAMILY_HUE2: HUE2_EFFECTS,
    FAMILY_KRAKEN: KRAKEN_EFFECTS,
}


def effects_for_family(family: str) -> tuple[EffectSpec, ...]:
    """All effects available to a device family, in presentation order."""
    try:
        return EFFECTS_BY_FAMILY[family]
    except KeyError:
        raise EffectError(f"Unknown device family '{family}'.") from None


def get_effect(family: str, effect_id: str) -> EffectSpec:
    """Look up one effect, raising :class:`EffectError` if the device cannot render it."""
    for effect in effects_for_family(family):
        if effect.id == effect_id:
            return effect
    available = ", ".join(effect.id for effect in effects_for_family(family))
    raise EffectError(
        f"'{effect_id}' is not an effect this device supports.",
        hint=f"Supported effects: {available}.",
    )


@dataclass(frozen=True, slots=True)
class ValidatedEffect:
    """An effect request that has been checked against the hardware's limits."""

    effect: EffectSpec
    colors: tuple[Color, ...]
    speed: str
    direction: str


def validate_request(
    family: str,
    effect_id: str,
    colors: tuple[Color, ...] | list[Color] = (),
    speed: str = DEFAULT_SPEED,
    direction: str = DEFAULT_DIRECTION,
) -> ValidatedEffect:
    """Check an effect request against the limits of ``family`` and normalise it.

    Colour lists are trimmed to what the firmware accepts, speed and direction are dropped for
    effects that ignore them, and anything genuinely contradictory raises :class:`EffectError`.
    """
    effect = get_effect(family, effect_id)
    supplied = tuple(colors)

    if effect.max_colors == 0:
        resolved_colors: tuple[Color, ...] = ()
    elif len(supplied) > effect.max_colors:
        resolved_colors = supplied[: effect.max_colors]
    elif len(supplied) < effect.min_colors:
        raise EffectError(
            f"The {effect.label} effect needs at least {effect.min_colors} "
            f"{'colour' if effect.min_colors == 1 else 'colours'}.",
        )
    else:
        resolved_colors = supplied

    if effect.supports_speed:
        if speed not in SPEEDS:
            raise EffectError(
                f"'{speed}' is not a valid animation speed.",
                hint=f"Valid speeds: {', '.join(SPEEDS)}.",
            )
        resolved_speed = speed
    else:
        resolved_speed = DEFAULT_SPEED

    if effect.supports_direction:
        if direction not in DIRECTIONS:
            raise EffectError(
                f"'{direction}' is not a valid direction.",
                hint=f"Valid directions: {', '.join(DIRECTIONS)}.",
            )
        resolved_direction = direction
    else:
        resolved_direction = DEFAULT_DIRECTION

    return ValidatedEffect(
        effect=effect,
        colors=resolved_colors,
        speed=resolved_speed,
        direction=resolved_direction,
    )
