"""Structured, restrained logging.

Normal users should never see noise on the terminal: the default level is warnings and errors only.
``--verbose`` (or ``NITOR_DEBUG``) turns on debug logging for bug reports.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import IO

LOGGER_NAME = "nitor"
_DEBUG_ENVIRONMENT_VARIABLE = "NITOR_DEBUG"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def configure_logging(verbose: bool = False, stream: IO[str] | None = None) -> logging.Logger:
    """Configure the application logger and return it.

    The application uses one handler on stderr, matching what a desktop user expects: nothing when
    all is well, a short line when something needs attention.
    """
    logger = logging.getLogger(LOGGER_NAME)
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    # Replacing rather than adding keeps repeated calls (tests, restarts) from stacking handlers.
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    set_verbosity(verbose)
    return logger


def set_verbosity(verbose: bool) -> None:
    """Turn debug logging on or off."""
    logging.getLogger(LOGGER_NAME).setLevel(logging.DEBUG if verbose else logging.WARNING)


def verbose_requested(explicit: bool = False) -> bool:
    """Whether debug logging was asked for on the command line or in the environment."""
    if explicit:
        return True
    return os.environ.get(_DEBUG_ENVIRONMENT_VARIABLE, "").strip().lower() in {"1", "true", "yes"}


def get_logger(name: str) -> logging.Logger:
    """Return a child logger so that log lines show which part of the program spoke."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


__all__ = ["LOGGER_NAME", "configure_logging", "get_logger", "set_verbosity", "verbose_requested"]
