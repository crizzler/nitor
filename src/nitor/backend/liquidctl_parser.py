"""Parsing liquidctl output into domain objects.

Pure functions only, so every mapping decision can be tested against captured output without a
device present. The two things worth knowing about the formats:

* ``list --json`` is structured and is what device discovery relies on.
* ``initialize`` prints a tree of ``key    value`` lines. That tree is parsed for the detected LED
  accessories, because the accessory *names* are what a person needs to see, and the JSON form
  reports them as numeric enum values.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Final

from nitor.domain import (
    Device,
    DeviceNotFoundError,
    HardwareError,
    NotSupportedError,
    PermissionDeniedError,
    channel_label,
)
from nitor.domain.models import ChannelSpec
from nitor.domain.profiles import lookup_profile

#: Multi-space or tab separated key/value pairs in liquidctl's tree output.
_TREE_SPLIT: Final = re.compile(r"\s{2,}|\t")

#: Characters liquidctl uses to draw its output tree.
_TREE_DECORATION: Final = " │├└─\t"

_VERSION_PATTERN: Final = re.compile(r"(\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.]+)?)")

_ACCESSORY_PATTERN: Final = re.compile(r"^LED (\d+) accessory (\d+)$", re.IGNORECASE)
_SINGLE_ACCESSORY_PATTERN: Final = re.compile(r"^LED accessory (\d+)$", re.IGNORECASE)
_PUMP_LED_PATTERN: Final = re.compile(r"^Pump (Ring|Logo) LEDs$", re.IGNORECASE)

_FIRMWARE_KEY: Final = "firmware version"

_PERMISSION_MARKERS: Final = (
    "access denied",
    "open failed",
    "permission denied",
    "errno 13",
    "insufficient permission",
    # Observed on a real CachyOS system with liquidctl 1.16.0 and no udev rule installed: the USB
    # string descriptors cannot be read either, so even `liquidctl list` fails with
    # "ValueError: The device has no langid (permission issue, no string descriptors supported or
    # device error)". Without these two markers that lands in the generic hardware branch and the
    # user is told to replug the controller instead of being shown the udev rule.
    "permission issue",
    "no langid",
)
_MISSING_DEVICE_MARKERS: Final = (
    "no devices",
    "no matching",
    "device not found",
    "no supported",
)
_DRIVER_MARKERS: Final = (
    "no backend available",
    "libusb",
    "hidapi",
    "kernel driver",
)


@dataclass(slots=True)
class InitializeReport:
    """What ``initialize`` told us about a device."""

    firmware: str | None = None
    accessories: dict[str, list[str]] = field(default_factory=dict)
    detected: dict[str, bool] = field(default_factory=dict)
    raw_pairs: list[tuple[str, str]] = field(default_factory=list)


def parse_device_list(payload: str) -> list[Device]:
    """Parse ``liquidctl list --json`` into devices.

    Devices without a USB vendor/product pair are skipped: they cannot be identified, so there is
    nothing useful to show. Unknown models are still returned, with no profile attached, so the
    interface can say that the model is not supported yet instead of claiming nothing is connected.
    """
    text = payload.strip()
    if not text:
        return []

    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as error:
        raise HardwareError(
            "Could not understand the device list reported by liquidctl.",
            hint="Try running 'liquidctl list --json' by hand to see what it reports.",
            detail=f"{error}: {text[:400]}",
        ) from error

    if not isinstance(data, list):
        raise HardwareError("liquidctl did not report a list of devices.", detail=text[:400])

    devices: list[Device] = []
    for entry in data:
        device = _device_from_entry(entry)
        if device is not None:
            devices.append(device)
    return devices


def _device_from_entry(entry: Any) -> Device | None:
    if not isinstance(entry, dict):
        return None
    vendor_id = _as_int(entry.get("vendor_id"))
    product_id = _as_int(entry.get("product_id"))
    if vendor_id is None or product_id is None:
        return None

    description = str(entry.get("description") or _fallback_description(vendor_id, product_id))
    serial = entry.get("serial_number")
    serial_text = str(serial) if serial not in (None, "") else None
    address = str(entry.get("address") or "")
    profile = lookup_profile(vendor_id, product_id)

    return Device(
        key=device_key(vendor_id, product_id, serial_text),
        description=description,
        vendor_id=vendor_id,
        product_id=product_id,
        driver=str(entry.get("driver") or ""),
        bus=str(entry.get("bus") or ""),
        address=address,
        serial=serial_text,
        profile=profile,
    )


def _fallback_description(vendor_id: int, product_id: int) -> str:
    return f"{vendor_id:04x}:{product_id:04x} device"


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value), 0)
    except ValueError:
        return None


def device_key(vendor_id: int, product_id: int, serial: str | None = None) -> str:
    """A stable identity for a device that survives /dev/hidrawN being renumbered."""
    base = f"{vendor_id:04x}:{product_id:04x}"
    return f"{base}:{serial}" if serial else base


def parse_tree(output: str) -> list[tuple[str, str]]:
    """Turn liquidctl's tree output into ``(key, value)`` pairs."""
    pairs: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        stripped = line.strip(_TREE_DECORATION)
        stripped = stripped.lstrip()
        if not stripped:
            continue
        parts = _TREE_SPLIT.split(stripped, maxsplit=1)
        key = parts[0].strip()
        value = parts[1].strip() if len(parts) > 1 else ""
        if key:
            pairs.append((key, value))
    return pairs


def parse_version(output: str) -> str | None:
    """Extract a version number from ``liquidctl --version`` output."""
    match = _VERSION_PATTERN.search(output)
    return match.group(1) if match else None


def parse_initialize_output(channel_ids: tuple[str, ...], output: str) -> InitializeReport:
    """Read the detected accessories out of ``initialize`` output.

    ``channel_ids`` are the LED channels of the device's profile in the order liquidctl reports
    them; that order is what lets ``LED 1 accessory 1`` and ``LED accessory 1`` be resolved to real
    channel names.
    """
    report = InitializeReport(raw_pairs=parse_tree(output))

    for key, value in report.raw_pairs:
        lowered = key.lower()

        if lowered == _FIRMWARE_KEY:
            report.firmware = value or None
            continue

        pump_match = _PUMP_LED_PATTERN.match(key)
        if pump_match:
            channel = pump_match.group(1).lower()
            report.detected[channel] = value.strip().lower() == "detected"
            report.accessories.setdefault(channel, [])
            continue

        multi_match = _ACCESSORY_PATTERN.match(key)
        if multi_match:
            channel = _channel_for_liquidctl_index(int(multi_match.group(1)), channel_ids)
            _record_accessory(report, channel, value)
            continue

        single_match = _SINGLE_ACCESSORY_PATTERN.match(key)
        if single_match:
            channel = channel_ids[0] if channel_ids else ""
            _record_accessory(report, channel, value)
            continue

    for channel in channel_ids:
        report.accessories.setdefault(channel, [])
    return report


def _channel_for_liquidctl_index(index: int, channel_ids: tuple[str, ...]) -> str:
    """Map liquidctl's 1-based LED index onto a profile channel name."""
    position = index - 1
    if 0 <= position < len(channel_ids):
        return channel_ids[position]
    return f"led{index}"


def _record_accessory(report: InitializeReport, channel: str, value: str) -> None:
    if not channel:
        return
    accessories = report.accessories.setdefault(channel, [])
    if value:
        accessories.append(value)
    report.detected[channel] = report.detected.get(channel, False) or bool(value)


def channels_from_report(
    device: Device,
    report: InitializeReport,
) -> tuple[ChannelSpec, ...]:
    """Build channel descriptions for a device from an initialisation report."""
    profile = device.profile
    if profile is None:
        return ()

    specs: list[ChannelSpec] = []
    for channel_id in profile.led_channels:
        accessories = tuple(report.accessories.get(channel_id, ()))
        detected = report.detected.get(channel_id, False)
        if accessories:
            led_count = sum(_LED_COUNTS.get(name, 0) for name in accessories)
            led_count = led_count or _FIXED_LED_COUNTS.get(channel_id)
        elif detected:
            # Channels such as a Kraken pump ring report "detected" rather than an accessory list.
            led_count = _FIXED_LED_COUNTS.get(channel_id)
        else:
            led_count = 0
        specs.append(
            ChannelSpec(
                id=channel_id,
                label=channel_label(channel_id),
                accessible=True,
                led_count=led_count,
                accessories=accessories,
            )
        )

    if profile.has_sync:
        total = sum(spec.led_count or 0 for spec in specs)
        specs.append(
            ChannelSpec(
                id="sync",
                label=channel_label("sync"),
                accessible=True,
                led_count=total or None,
                accessories=(),
            )
        )
    return tuple(specs)


#: Rough LED counts per accessory type, used only to give the interface a sense of scale. The real
#: count comes from the device; these values are from NZXT's published accessory sizes.
_LED_COUNTS: Final[dict[str, int]] = {
    "HUE 2 LED Strip 300 mm": 10,
    "HUE 2 LED Strip 200 mm": 6,
    "HUE 2 Underglow 200 mm": 6,
    "HUE 2 Cable Comb": 6,
    "AER RGB 2 120 mm": 8,
    "AER RGB 2 140 mm": 8,
}

#: Channels whose LED count is fixed by the hardware and reported as a bare "detected".
_FIXED_LED_COUNTS: Final[dict[str, int]] = {"ring": 8, "logo": 1}


def classify_failure(*, returncode: int, stdout: str, stderr: str) -> Exception:
    """Turn a failed liquidctl run into the most specific error we can justify.

    Permission problems are separated from hardware problems, because the two need completely
    different things from the user.
    """
    combined = f"{stderr}\n{stdout}".lower()

    if any(marker in combined for marker in _PERMISSION_MARKERS):
        return PermissionDeniedError(
            "The controller was found, but Linux denied access to it.",
            hint=(
                "The device needs its udev rule. Installing the liquidctl package provides it "
                "('sudo pacman -S liquidctl'). If you installed liquidctl another way, copy "
                "71-liquidctl.rules into /etc/udev/rules.d/ and reload udev."
            ),
            detail=_first_meaningful_line(stderr) or _first_meaningful_line(stdout),
        )

    if any(marker in combined for marker in _MISSING_DEVICE_MARKERS):
        return DeviceNotFoundError(
            "No matching NZXT controller was found.",
            hint="Check that the device appears in 'lsusb' and that nothing else is using it.",
            detail=_first_meaningful_line(stderr) or _first_meaningful_line(stdout),
        )

    if any(marker in combined for marker in _DRIVER_MARKERS):
        return HardwareError(
            "The lighting backend could not talk to the USB device.",
            hint=(
                "Another program may be holding the device open, or a kernel driver may have "
                "detached it. Unplugging and reconnecting the controller usually clears this."
            ),
            detail=_first_meaningful_line(stderr) or _first_meaningful_line(stdout),
        )

    detail = _first_meaningful_line(stderr) or _first_meaningful_line(stdout)
    return HardwareError(
        "The lighting backend reported an error.",
        hint="Settings -> Diagnostics can copy a report that helps track this down.",
        detail=detail,
    )


def _first_meaningful_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.lower().startswith("usage:"):
            return stripped
    return None


def ensure_supported(device: Device) -> None:
    """Raise a helpful error when we have no way to control a device."""
    if device.profile is None:
        raise NotSupportedError(
            f"Nitor does not know how to control {device.display_name} yet.",
            hint="A hardware support request with the diagnostics report would help.",
        )
    if not device.profile.controllable:
        raise NotSupportedError(
            device.profile.note or f"{device.display_name} does not support lighting control.",
        )


__all__ = [
    "InitializeReport",
    "channels_from_report",
    "classify_failure",
    "device_key",
    "ensure_supported",
    "parse_device_list",
    "parse_initialize_output",
    "parse_tree",
    "parse_version",
]
