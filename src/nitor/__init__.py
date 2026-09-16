"""Nitor — simple, reliable control of NZXT LED lighting on Linux."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

APP_NAME = "Nitor"
APP_ID = "io.github.crizzler.Nitor"
APP_SUMMARY = "Control NZXT LED lighting on Linux without NZXT CAM"
APP_URL = "https://github.com/crizzler/nitor"
_NOMINAL_VERSION = "0.1.0"


def _detect_version() -> str:
    """Return the installed distribution version, falling back to the source version."""
    try:
        return _distribution_version("nitor")
    except PackageNotFoundError:
        # Running from a source checkout without the package installed.
        return _NOMINAL_VERSION


__version__ = _detect_version()

__all__ = ["APP_ID", "APP_NAME", "APP_SUMMARY", "APP_URL", "__version__"]
