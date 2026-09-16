"""Error types.

Every error raised for the user's benefit carries a :attr:`NitorError.message` that is safe and
sensible to display, an optional actionable :attr:`NitorError.hint`, and an optional
:attr:`NitorError.detail` holding raw backend text. Details never reach the user interface directly;
they go to the log and to the diagnostics report.
"""

from __future__ import annotations


class NitorError(Exception):
    """Base class for all errors raised deliberately by this application."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.detail = detail

    def __str__(self) -> str:
        return self.message


class BackendMissingError(NitorError):
    """The lighting backend (liquidctl) is not installed."""


class PermissionDeniedError(NitorError):
    """The device exists but this user is not allowed to access it."""


class DeviceNotFoundError(NitorError):
    """No supported device was found, or the selected one went away."""


class NotSupportedError(NitorError):
    """The hardware or backend does not support the requested operation."""


class HardwareError(NitorError):
    """The backend failed for a reason we could not classify more precisely."""


class SafetyViolationError(NitorError):
    """A command outside the lighting-only safety boundary was attempted.

    This never happens because of user input; it means a programming error, and it exists so that
    the cooling boundary fails loudly instead of quietly poking at a pump.
    """


class InvalidStateError(NitorError, ValueError):
    """A lighting state was constructed with impossible values."""


class InvalidColorError(NitorError, ValueError):
    """A colour string could not be parsed, or an RGB component was out of range."""


class EffectError(NitorError, ValueError):
    """An effect, colour count, speed or direction is not valid for the device."""
