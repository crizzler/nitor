"""What this project knows about each supported device model before probing it.

Keyed by USB vendor/product ID. The channel layout comes from the liquidctl drivers, which is why
it can be trusted before the device is contacted; the number of LEDs actually attached is discovered
at runtime through ``initialize``.

Device models that liquidctl supports but cannot drive lighting for are listed too, with no LED
channels, so the application can explain the situation instead of showing an empty window.
"""

from __future__ import annotations

from typing import Final

from .effects import FAMILY_HUE2, FAMILY_KRAKEN
from .models import DeviceProfile

NZXT_VENDOR_ID: Final = 0x1E71

_NOTE_NO_LIGHTING: Final = (
    "liquidctl does not implement lighting commands for this model yet, so Nitor cannot control "
    "its LEDs."
)
_NOTE_H1V2: Final = "This model has no lighting channels at all."

#: USB product ID -> what we know about the model.
KNOWN_PROFILES: Final[dict[int, DeviceProfile]] = {
    # -- HUE 2 generation fan and LED controllers -------------------------------------------------
    0x2006: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT Smart Device V2",
        led_channels=("led1", "led2"),
        has_sync=True,
    ),
    0x200D: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT Smart Device V2",
        led_channels=("led1", "led2"),
        has_sync=True,
    ),
    0x200F: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT Smart Device V2",
        led_channels=("led1", "led2"),
        has_sync=True,
    ),
    0x2001: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT HUE 2",
        led_channels=("led1", "led2", "led3", "led4"),
        has_sync=True,
    ),
    0x2002: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT HUE 2 Ambient",
        led_channels=("led1", "led2"),
        has_sync=True,
    ),
    # The development machine's fan/LED controller, and its siblings.
    0x2009: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT RGB & Fan Controller",
        led_channels=("led1", "led2"),
        has_sync=True,
    ),
    0x200E: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT RGB & Fan Controller",
        led_channels=("led1", "led2"),
        has_sync=True,
    ),
    0x2010: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT RGB & Fan Controller",
        led_channels=("led1", "led2"),
        has_sync=True,
    ),
    # 2022 "3+6 channel" revision: liquidctl 1.16.0 can control the fans but not the LEDs.
    0x2011: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT RGB & Fan Controller (3+6 channels)",
        led_channels=(),
        controllable=False,
        note=_NOTE_NO_LIGHTING,
    ),
    0x2019: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT RGB & Fan Controller (3+6 channels)",
        led_channels=(),
        controllable=False,
        note=_NOTE_NO_LIGHTING,
    ),
    0x201F: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT RGB & Fan Controller (3+6 channels)",
        led_channels=(),
        controllable=False,
        note=_NOTE_NO_LIGHTING,
    ),
    # The last revision of that family does expose six LED channels upstream.
    0x2020: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT RGB & Fan Controller (3+6 channels)",
        led_channels=("led1", "led2", "led3", "led4", "led5", "led6"),
        has_sync=True,
    ),
    0x2012: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT 2023 RGB Controller",
        led_channels=("led1", "led2", "led3"),
        has_sync=True,
    ),
    0x2021: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT 2023 RGB Controller",
        led_channels=("led1", "led2", "led3"),
        has_sync=True,
    ),
    0x2015: DeviceProfile(
        family=FAMILY_HUE2,
        description="NZXT H1 V2",
        led_channels=(),
        controllable=False,
        note=_NOTE_H1V2,
    ),
    # -- Fourth-generation Kraken liquid coolers --------------------------------------------------
    # The development machine's cooler. Z models replaced the infinity mirror with an LCD, so the
    # only controllable LEDs are those on the external HUE 2 header.
    0x3008: DeviceProfile(
        family=FAMILY_KRAKEN,
        description="NZXT Kraken Z (Z53, Z63 or Z73)",
        led_channels=("external",),
        has_sync=False,
    ),
    0x2007: DeviceProfile(
        family=FAMILY_KRAKEN,
        description="NZXT Kraken X (X53, X63 or X73)",
        led_channels=("external", "ring", "logo"),
        has_sync=True,
    ),
    0x2014: DeviceProfile(
        family=FAMILY_KRAKEN,
        description="NZXT Kraken X (X53, X63 or X73)",
        led_channels=("external", "ring", "logo"),
        has_sync=True,
    ),
    # 2023 and 2024 models expose no colour channels upstream.
    0x300C: DeviceProfile(
        family=FAMILY_KRAKEN,
        description="NZXT Kraken 2023 Elite",
        led_channels=(),
        controllable=False,
        note=_NOTE_NO_LIGHTING,
    ),
    0x300E: DeviceProfile(
        family=FAMILY_KRAKEN,
        description="NZXT Kraken 2023",
        led_channels=(),
        controllable=False,
        note=_NOTE_NO_LIGHTING,
    ),
    0x3012: DeviceProfile(
        family=FAMILY_KRAKEN,
        description="NZXT Kraken 2024 Elite RGB",
        led_channels=(),
        controllable=False,
        note=_NOTE_NO_LIGHTING,
    ),
    0x3014: DeviceProfile(
        family=FAMILY_KRAKEN,
        description="NZXT Kraken 2024 Plus",
        led_channels=(),
        controllable=False,
        note=_NOTE_NO_LIGHTING,
    ),
}


def lookup_profile(vendor_id: int, product_id: int) -> DeviceProfile | None:
    """Return what we know about a USB device, or ``None`` if it is not an NZXT model we know."""
    if vendor_id != NZXT_VENDOR_ID:
        return None
    return KNOWN_PROFILES.get(product_id)


__all__ = ["KNOWN_PROFILES", "NZXT_VENDOR_ID", "lookup_profile"]
