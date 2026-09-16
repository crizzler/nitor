"""Devices, their capabilities and the lighting state the interface edits."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final

from .color import WHITE, Color
from .effects import (
    DEFAULT_DIRECTION,
    DEFAULT_EFFECT,
    DEFAULT_SPEED,
    DIRECTIONS,
    OFF_EFFECT,
    SPEEDS,
    EffectSpec,
    ValidatedEffect,
    effects_for_family,
    validate_request,
)
from .errors import InvalidStateError, NotSupportedError

MIN_BRIGHTNESS: Final = 0
MAX_BRIGHTNESS: Final = 100


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    """One addressable LED channel of a device."""

    id: str
    label: str
    accessible: bool = True
    led_count: int | None = None
    accessories: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        """A short human description of what is connected to this channel."""
        if self.accessories:
            return ", ".join(self.accessories)
        if self.led_count is not None and self.led_count > 0:
            return f"{self.led_count} LEDs detected"
        return "No accessories detected"

    @property
    def has_accessories(self) -> bool:
        return bool(self.accessories) or bool(self.led_count)


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """What this project knows about a device model before talking to it.

    This is the static half of the capability model: it comes from the liquidctl drivers and the
    hardware notes, not from probing. The dynamic half (which accessories are actually attached)
    comes from ``initialize``.
    """

    family: str
    description: str
    led_channels: tuple[str, ...]
    has_sync: bool = False
    native_brightness: bool = False
    per_led_control: bool = True
    controllable: bool = True
    note: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """Everything the interface needs to know about what a device can do."""

    family: str
    effects: tuple[EffectSpec, ...]
    channels: tuple[ChannelSpec, ...]
    speeds: tuple[str, ...] = SPEEDS
    directions: tuple[str, ...] = DIRECTIONS
    native_brightness: bool = False
    per_led_control: bool = True

    @property
    def controllable_channels(self) -> tuple[ChannelSpec, ...]:
        return tuple(channel for channel in self.channels if channel.accessible)

    @property
    def supports_lighting(self) -> bool:
        return bool(self.controllable_channels)

    @property
    def requires_accessories(self) -> bool:
        """Whether an empty channel is a likely wiring problem rather than a normal state.

        On the RGB & Fan Controller each ``ledN`` header exists whether or not something is plugged
        in. On a Kraken the single ``external`` header only matters if a HUE 2 chain is attached.
        """
        return any(not channel.has_accessories for channel in self.controllable_channels)

    def channel(self, channel_id: str) -> ChannelSpec:
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        raise NotSupportedError(f"This device has no channel called '{channel_id}'.")

    def effect(self, effect_id: str) -> EffectSpec:
        for effect in self.effects:
            if effect.id == effect_id:
                return effect
        raise NotSupportedError(f"This device cannot render the '{effect_id}' effect.")

    @property
    def default_channel(self) -> str | None:
        accessible = self.controllable_channels
        if not accessible:
            return None
        with_accessories = [channel for channel in accessible if channel.has_accessories]
        return (with_accessories or list(accessible))[0].id


@dataclass(frozen=True, slots=True)
class Device:
    """A discovered device, as reported by the backend."""

    key: str
    description: str
    vendor_id: int
    product_id: int
    driver: str = ""
    bus: str = ""
    address: str = ""
    serial: str | None = None
    profile: DeviceProfile | None = None
    channels: tuple[ChannelSpec, ...] = ()

    @property
    def usb_id(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"

    @property
    def is_supported(self) -> bool:
        return self.profile is not None

    @property
    def display_name(self) -> str:
        """A friendly name: our own model name when known, otherwise the backend's description."""
        if self.profile is not None:
            return self.profile.description
        return self.description

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Build the capability model for this device from its profile and probed channels."""
        if self.profile is None:
            return DeviceCapabilities(
                family="unknown",
                effects=(),
                channels=(),
                native_brightness=False,
                per_led_control=False,
            )

        profile = self.profile
        probed = {channel.id: channel for channel in self.channels}
        channels: list[ChannelSpec] = []
        for channel_id in profile.led_channels:
            known = probed.get(channel_id)
            channels.append(
                known
                if known is not None
                else ChannelSpec(id=channel_id, label=channel_label(channel_id))
            )
        if profile.has_sync:
            channels.append(
                probed.get("sync") or ChannelSpec(id="sync", label="Sync (all channels)")
            )

        return DeviceCapabilities(
            family=profile.family,
            effects=effects_for_family(profile.family) if profile.controllable else (),
            channels=tuple(channels),
            native_brightness=profile.native_brightness,
            per_led_control=profile.per_led_control,
        )

    def with_channels(self, channels: tuple[ChannelSpec, ...]) -> Device:
        """Return a copy of this device with the probed channel details attached."""
        return replace(self, channels=channels)


def channel_label(channel_id: str) -> str:
    """Turn a liquidctl channel name into something a person reads comfortably."""
    match = channel_id
    if match == "sync":
        return "Sync (all channels)"
    if match == "external":
        return "External (HUE 2 chain)"
    if match == "ring":
        return "Pump ring"
    if match == "logo":
        return "Pump logo"
    if len(match) == 4 and match.startswith("led") and match[3].isdigit():
        return f"LED channel {match[3]}"
    return match.capitalize()


@dataclass(frozen=True, slots=True)
class LightingState:
    """The lighting the user has asked for. Immutable; use :meth:`with_*` to change it."""

    channel: str = ""
    effect: str = DEFAULT_EFFECT
    colors: tuple[Color, ...] = (WHITE,)
    brightness: int = MAX_BRIGHTNESS
    speed: str = DEFAULT_SPEED
    direction: str = DEFAULT_DIRECTION

    def __post_init__(self) -> None:
        if isinstance(self.brightness, bool) or not isinstance(self.brightness, int):
            raise InvalidStateError("Brightness must be a whole number.")
        if not MIN_BRIGHTNESS <= self.brightness <= MAX_BRIGHTNESS:
            raise InvalidStateError(
                f"Brightness must be between {MIN_BRIGHTNESS} and {MAX_BRIGHTNESS}."
            )
        if not isinstance(self.colors, tuple):
            object.__setattr__(self, "colors", tuple(self.colors))

    # -- immutable updates ----------------------------------------------------------------

    def with_channel(self, channel: str) -> LightingState:
        return replace(self, channel=channel)

    def with_effect(self, effect: str) -> LightingState:
        return replace(self, effect=effect)

    def with_colors(self, colors: tuple[Color, ...] | list[Color]) -> LightingState:
        return replace(self, colors=tuple(colors))

    def with_color(self, index: int, color: Color) -> LightingState:
        """Replace the colour at ``index``, growing the list if the effect allows more."""
        colors = list(self.colors)
        if index < 0:
            raise InvalidStateError("Colour slot indexes start at zero.")
        while len(colors) <= index:
            colors.append(colors[-1] if colors else WHITE)
        colors[index] = color
        return replace(self, colors=tuple(colors))

    def with_brightness(self, brightness: int) -> LightingState:
        return replace(self, brightness=brightness)

    def with_speed(self, speed: str) -> LightingState:
        return replace(self, speed=speed)

    def with_direction(self, direction: str) -> LightingState:
        return replace(self, direction=direction)

    # -- derived values -------------------------------------------------------------------

    @property
    def primary_color(self) -> Color:
        """The colour to show in the picker and the preview."""
        if self.colors:
            return self.colors[0]
        return WHITE

    @property
    def is_off(self) -> bool:
        return self.effect == OFF_EFFECT

    def effective_colors(self) -> tuple[Color, ...]:
        """The colours as they will be sent, with application-level brightness applied."""
        if self.brightness >= MAX_BRIGHTNESS:
            return self.colors
        return tuple(color.dimmed(self.brightness) for color in self.colors)

    def preview_colors(self) -> tuple[Color, ...]:
        """Colours for the on-screen preview, never fully black so the picker stays usable."""
        colors = self.effective_colors()
        if not colors:
            return ()
        return tuple(color if color.to_rgb_tuple() != (0, 0, 0) else Color(24, 24, 24) for color in colors)

    def normalized(self, capabilities: DeviceCapabilities) -> LightingState:
        """Return a state that is valid for ``capabilities``.

        Called whenever the device or channel changes, and after loading persisted settings that
        may have been written for different hardware.
        """
        if not capabilities.supports_lighting:
            return self

        channel = self.channel
        if channel not in {spec.id for spec in capabilities.channels}:
            channel = capabilities.default_channel or channel

        effect_id = self.effect
        if effect_id not in {spec.id for spec in capabilities.effects}:
            effect_id = DEFAULT_EFFECT

        try:
            validated: ValidatedEffect = validate_request(
                capabilities.family,
                effect_id,
                self.colors,
                self.speed,
                self.direction,
            )
        except Exception:  # noqa: BLE001 - fall back to the safest valid state
            validated = validate_request(capabilities.family, DEFAULT_EFFECT, (self.primary_color,))

        return replace(
            self,
            channel=channel,
            effect=validated.effect.id,
            colors=validated.colors,
            speed=validated.speed,
            direction=validated.direction,
        )

    # -- persistence ----------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return {
            "channel": self.channel,
            "effect": self.effect,
            "colors": [color.to_hex() for color in self.colors],
            "brightness": self.brightness,
            "speed": self.speed,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LightingState:
        """Rebuild a state from persisted data, tolerating anything malformed."""
        colors: list[Color] = []
        raw_colors = data.get("colors")
        if isinstance(raw_colors, list):
            for entry in raw_colors:
                try:
                    colors.append(Color.from_hex(str(entry)))
                except Exception:  # noqa: BLE001, S112 - a bad colour must not break start-up
                    continue

        brightness = data.get("brightness", MAX_BRIGHTNESS)
        if not isinstance(brightness, int) or isinstance(brightness, bool):
            brightness = MAX_BRIGHTNESS
        brightness = max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, brightness))

        channel = data.get("channel")
        effect = data.get("effect")
        speed = data.get("speed")
        direction = data.get("direction")

        return cls(
            channel=channel if isinstance(channel, str) else "",
            effect=effect if isinstance(effect, str) else DEFAULT_EFFECT,
            colors=tuple(colors) or (WHITE,),
            brightness=brightness,
            speed=speed if isinstance(speed, str) else DEFAULT_SPEED,
            direction=direction if isinstance(direction, str) else DEFAULT_DIRECTION,
        )


@dataclass(slots=True)
class DeviceDiscovery:
    """The outcome of a discovery pass, including why nothing was found."""

    devices: list[Device] = field(default_factory=list)
    backend_name: str = ""
    backend_available: bool = True
    error: object | None = None

    @property
    def supported_devices(self) -> list[Device]:
        return [device for device in self.devices if device.is_supported]
