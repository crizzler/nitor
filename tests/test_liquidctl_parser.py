"""Parsing liquidctl output.

The payloads below are the shapes liquidctl 1.16.0 actually emits, including the tree drawing
characters and the two different accessory-line styles.
"""

from __future__ import annotations

import pytest

from nitor.backend.liquidctl_parser import (
    channels_from_report,
    classify_failure,
    device_key,
    ensure_supported,
    parse_device_list,
    parse_initialize_output,
    parse_tree,
    parse_version,
)
from nitor.domain import (
    NZXT_VENDOR_ID,
    Device,
    DeviceNotFoundError,
    HardwareError,
    NotSupportedError,
    PermissionDeniedError,
    lookup_profile,
)

LIST_JSON = """
[
  {
    "description": "NZXT RGB & Fan Controller",
    "vendor_id": 7793,
    "product_id": 8208,
    "release_number": 256,
    "serial_number": "ABC123456",
    "bus": "hid",
    "address": "/dev/hidraw5",
    "port": null,
    "driver": "SmartDevice2"
  },
  {
    "description": "NZXT Kraken Z (Z53, Z63 or Z73)",
    "vendor_id": 7793,
    "product_id": 12296,
    "release_number": 512,
    "serial_number": null,
    "bus": "hid",
    "address": "/dev/hidraw4",
    "port": null,
    "driver": "KrakenZ3"
  }
]
"""

CONTROLLER_INITIALIZE = """NZXT RGB & Fan Controller
├── Firmware version                      1.5.0
├── LED 1 accessory 1        HUE 2 LED Strip 300 mm
├── LED 2 accessory 1          AER RGB 2 140 mm
└── LED 2 accessory 2          AER RGB 2 140 mm
"""

KRAKEN_X_INITIALIZE = """NZXT Kraken X (X53, X63 or X73)
├── Firmware version                   1.8.0
├── LED accessory 1        HUE 2 LED Strip 300 mm
├── Pump Logo LEDs                 detected
└── Pump Ring LEDs                 detected
"""


def test_device_list_is_parsed_with_profiles_attached() -> None:
    devices = parse_device_list(LIST_JSON)
    assert [device.usb_id for device in devices] == ["1e71:2010", "1e71:3008"]
    controller, kraken = devices
    assert controller.driver == "SmartDevice2"
    assert controller.address == "/dev/hidraw5"
    assert controller.serial == "ABC123456"
    assert controller.is_supported
    assert kraken.serial is None
    assert kraken.is_supported


def test_device_keys_are_stable_across_hidraw_renumbering() -> None:
    with_serial = parse_device_list(LIST_JSON)[0]
    assert with_serial.key == device_key(0x1E71, 0x2010, "ABC123456")
    assert device_key(0x1E71, 0x3008) == "1e71:3008"


def test_entries_without_usb_ids_are_skipped() -> None:
    devices = parse_device_list('[{"description": "not a USB device", "bus": "i2c"}]')
    assert devices == []


def test_empty_and_invalid_lists() -> None:
    assert parse_device_list("") == []
    assert parse_device_list("   ") == []
    with pytest.raises(HardwareError):
        parse_device_list("this is not json")
    with pytest.raises(HardwareError):
        parse_device_list('{"description": "an object, not a list"}')


def test_unknown_models_are_kept_but_marked_unsupported() -> None:
    payload = '[{"description": "NZXT Future Thing", "vendor_id": 7793, "product_id": 65280}]'
    (device,) = parse_device_list(payload)
    assert device.usb_id == "1e71:ff00"
    assert device.is_supported is False
    assert device.display_name == "NZXT Future Thing"


def test_tree_parsing_handles_box_characters() -> None:
    pairs = parse_tree(CONTROLLER_INITIALIZE)
    assert pairs[0] == ("NZXT RGB & Fan Controller", "")
    assert ("Firmware version", "1.5.0") in pairs
    assert ("LED 1 accessory 1", "HUE 2 LED Strip 300 mm") in pairs


def test_version_parsing() -> None:
    assert parse_version("liquidctl v1.16.0\n") == "1.16.0"
    assert parse_version("liquidctl, version 1.12.1") == "1.12.1"
    assert parse_version("no version here") is None


def controller() -> Device:
    return Device(
        key="1e71:2010",
        description="NZXT RGB & Fan Controller",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2010,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2010),
    )


def test_hue2_style_accessory_lines_map_onto_channels() -> None:
    report = parse_initialize_output(("led1", "led2"), CONTROLLER_INITIALIZE)
    assert report.firmware == "1.5.0"
    assert report.accessories["led1"] == ["HUE 2 LED Strip 300 mm"]
    assert report.accessories["led2"] == ["AER RGB 2 140 mm", "AER RGB 2 140 mm"]

    channels = {channel.id: channel for channel in channels_from_report(controller(), report)}
    assert channels["led1"].led_count == 10
    assert channels["led2"].led_count == 16
    assert channels["led1"].has_accessories
    assert channels["sync"].led_count == 26
    assert "HUE 2 LED Strip 300 mm" in channels["led1"].summary


def test_kraken_style_accessory_lines_map_onto_channels() -> None:
    device = Device(
        key="1e71:2007",
        description="NZXT Kraken X (X53, X63 or X73)",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2007,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2007),
    )
    report = parse_initialize_output(("external", "ring", "logo"), KRAKEN_X_INITIALIZE)
    assert report.accessories["external"] == ["HUE 2 LED Strip 300 mm"]
    assert report.detected["ring"] is True
    assert report.detected["logo"] is True

    channels = {channel.id: channel for channel in channels_from_report(device, report)}
    assert channels["external"].led_count == 10
    assert channels["ring"].led_count == 8
    assert channels["logo"].led_count == 1
    # A Kraken Z reports the pump LEDs as missing, which must not look like a broken channel.
    missing = parse_initialize_output(("external", "ring", "logo"), "└── Pump Ring LEDs   missing")
    assert missing.detected["ring"] is False


def test_channels_without_accessories_are_visible_but_empty() -> None:
    report = parse_initialize_output(
        ("led1", "led2"), "NZXT RGB & Fan Controller\n└── Firmware version  1.0.0\n"
    )
    channels = {channel.id: channel for channel in channels_from_report(controller(), report)}
    assert channels["led1"].has_accessories is False
    assert channels["led1"].led_count == 0
    assert channels["led1"].summary == "No accessories detected"


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("Access denied (insufficient permissions)", PermissionDeniedError),
        ("OSError: open failed with errno 13", PermissionDeniedError),
        ("error: no devices found", DeviceNotFoundError),
        ("No matching device found", DeviceNotFoundError),
        ("AssertionError: no backend available for device", HardwareError),
        ("something completely unexpected", HardwareError),
    ],
)
def test_failures_are_classified_by_cause(stderr: str, expected: type[Exception]) -> None:
    error = classify_failure(returncode=1, stdout="", stderr=stderr)
    assert isinstance(error, expected)


def test_the_langid_failure_is_treated_as_a_permission_problem() -> None:
    """Verbatim output from this project's own machine, before the udev rule was installed.

    It is the first thing a user meets after installing liquidctl, and it does not read like a
    permission error, so it is worth pinning down.
    """
    observed = (
        "ValueError: The device has no langid (permission issue, no string descriptors "
        "supported or device error)"
    )
    error = classify_failure(returncode=1, stdout="", stderr=observed)
    assert isinstance(error, PermissionDeniedError)
    assert error.hint is not None
    assert "udev" in error.hint


def test_permission_errors_explain_the_udev_rule() -> None:
    error = classify_failure(returncode=1, stdout="", stderr="Access denied")
    assert isinstance(error, PermissionDeniedError)
    assert error.hint is not None
    assert "udev" in error.hint


def test_cooling_and_firmware_commands_are_not_part_of_this_model() -> None:
    with pytest.raises(NotSupportedError):
        ensure_supported(Device(key="k", description="d", vendor_id=1, product_id=2))
    unsupported = Device(
        key="1e71:2011",
        description="NZXT RGB & Fan Controller (3+6 channels)",
        vendor_id=NZXT_VENDOR_ID,
        product_id=0x2011,
        profile=lookup_profile(NZXT_VENDOR_ID, 0x2011),
    )
    with pytest.raises(NotSupportedError) as info:
        ensure_supported(unsupported)
    assert "liquidctl does not implement" in info.value.message
