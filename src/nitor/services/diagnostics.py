"""A copyable report that makes issues fixable without collecting personal data.

Deliberately absent: user name, host name, home directory and device serial numbers. Everything
here is about versions, hardware identity and permissions, which is what actually diagnoses a
lighting problem.
"""

from __future__ import annotations

import logging
import os
import platform
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from nitor import APP_ID, APP_NAME, __version__
from nitor.backend.base import BackendStatus
from nitor.backend.registry import DeviceAccess
from nitor.domain import Device

_LOGGER = logging.getLogger(__name__)

_OS_RELEASE: Final = Path("/etc/os-release")
_REPORT_WIDTH: Final = 18


def read_os_release(path: Path | None = None) -> dict[str, str]:
    """Parse ``/etc/os-release`` into a dictionary."""
    target = path if path is not None else _OS_RELEASE
    entries: dict[str, str] = {}
    try:
        content = target.read_text(encoding="utf-8")
    except OSError:
        return entries
    for line in content.splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        entries[key.strip()] = value.strip().strip('"').strip("'")
    return entries


def distribution_name() -> str:
    """A human name for the distribution, however it describes itself."""
    release = read_os_release()
    return release.get("PRETTY_NAME") or release.get("NAME") or platform.system() or "unknown"


def desktop_environment() -> str:
    """The desktop in use, preferring what the session actually advertises."""
    for variable in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "XDG_SESSION_DESKTOP"):
        value = os.environ.get(variable, "").strip()
        if value:
            return value
    return "unknown"


def session_type() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "").strip() or "unknown"


def toolkit_version() -> str:
    """The Qt version in use, if Qt can be imported at all."""
    try:
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion
    except Exception:
        # Diagnostics must still work when Qt cannot be imported at all.
        return "unavailable"
    return f"{pyside_version} (Qt {qVersion()})"


def system_summary() -> list[tuple[str, str]]:
    """The environment section of the report, as label/value pairs."""
    return [
        ("Application", f"{APP_NAME} {__version__}"),
        ("Application ID", APP_ID),
        ("Distribution", distribution_name()),
        ("Kernel", platform.release()),
        ("Desktop", desktop_environment()),
        ("Session", session_type()),
        ("Python", platform.python_version()),
        ("Toolkit", toolkit_version()),
    ]


def describe_device(device: Device, access: DeviceAccess | None) -> list[str]:
    """The lines describing one device."""
    if not device.is_supported:
        supported = "no (unrecognised model)"
    elif device.lighting_supported:
        supported = "yes"
    else:
        supported = "no (lighting is not implemented for this model)"

    lines = [
        f"* {device.usb_id}  {device.description}",
        f"    driver:    {device.driver or 'unknown'}",
        f"    supported: {supported}",
    ]
    if device.firmware:
        lines.append(f"    firmware:  {device.firmware}")
    if device.profile is not None and device.profile.note:
        lines.append(f"    note:      {device.profile.note}")

    if device.channels:
        lines.append("    channels:")
        for channel in device.channels:
            count = f"{channel.led_count} LEDs" if channel.led_count else "no LEDs detected"
            detail = f" ({channel.summary})" if channel.accessories else ""
            lines.append(f"      - {channel.id}: {count}{detail}")
    else:
        lines.append("    channels:  not probed yet")

    if access is not None:
        lines.append(f"    access:    {'yes' if access.accessible else 'NO'}")
        if access.reason:
            lines.append(f"    reason:    {access.reason}")
    return lines


def build_report(
    *,
    backend_status: BackendStatus,
    devices: Iterable[Device] = (),
    access: dict[str, DeviceAccess] | None = None,
    apply_on_login: bool = False,
    backend_mode: str = "auto",
    extra: Iterable[str] = (),
) -> str:
    """Assemble the diagnostics text."""
    access = access or {}
    sections: list[list[str]] = []

    sections.append([f"{APP_NAME} diagnostics", "=" * (len(APP_NAME) + 12)])
    sections.append(
        [_format_row(label, value) for label, value in system_summary()],
    )

    backend_lines = [
        _format_row("Backend", backend_status.name or "none"),
        _format_row("Backend mode", backend_mode),
        _format_row("Backend version", backend_status.version or "unknown"),
        _format_row("Backend available", "yes" if backend_status.available else "NO"),
    ]
    if backend_status.missing and backend_status.hint:
        backend_lines.append(_format_row("Backend note", backend_status.hint))
    backend_lines.append(_format_row("Apply on login", "yes" if apply_on_login else "no"))
    sections.append(backend_lines)

    device_list = list(devices)
    device_lines = [f"Devices ({len(device_list)} found)"]
    if device_list:
        for device in device_list:
            device_lines.extend(describe_device(device, access.get(device.key)))
    else:
        device_lines.append("  none detected")
    sections.append(device_lines)

    extra_lines = list(extra)
    if extra_lines:
        sections.append(["Notes", *extra_lines])

    return "\n".join("\n".join(section) for section in sections) + "\n"


def _format_row(label: str, value: str) -> str:
    return f"{label + ':':<{_REPORT_WIDTH}} {value}"


__all__ = [
    "build_report",
    "describe_device",
    "desktop_environment",
    "distribution_name",
    "read_os_release",
    "session_type",
    "system_summary",
    "toolkit_version",
]
