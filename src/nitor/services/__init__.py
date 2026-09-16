"""Application services: settings, write scheduling, diagnostics and startup restoration.

These modules hold the behaviour that sits between the user interface and the hardware, and none of
them (except the controller, which lives in the user-interface package because it is a Qt object)
import Qt.
"""

from __future__ import annotations

from .autostart import UNIT_NAME, AutostartManager, AutostartState
from .diagnostics import build_report, system_summary
from .logging import configure_logging, get_logger, verbose_requested
from .scheduling import DEFAULT_DEBOUNCE, DEFAULT_MIN_INTERVAL, PendingWrite, WriteScheduler
from .settings import Settings, SettingsStore, cache_dir, config_dir, state_dir
from .startup import ApplyOutcome, apply_saved

__all__ = [
    "DEFAULT_DEBOUNCE",
    "DEFAULT_MIN_INTERVAL",
    "UNIT_NAME",
    "ApplyOutcome",
    "AutostartManager",
    "AutostartState",
    "PendingWrite",
    "Settings",
    "SettingsStore",
    "WriteScheduler",
    "apply_saved",
    "build_report",
    "cache_dir",
    "config_dir",
    "configure_logging",
    "get_logger",
    "state_dir",
    "system_summary",
    "verbose_requested",
]
