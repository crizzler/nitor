"""The hardware backend contract.

The user interface never talks to USB directly: it asks a :class:`HardwareBackend` to discover
devices, initialise one, and apply a lighting state. Two implementations exist — the real one drives
liquidctl, and a mock one exists so the interface can be developed and tested without hardware.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from nitor.domain import OFF_EFFECT, Device, LightingState
from nitor.domain.color import Color


@dataclass(frozen=True, slots=True)
class BackendStatus:
    """Whether the backend can be used, and what to tell the user if it cannot."""

    name: str
    available: bool
    version: str | None = None
    summary: str = ""
    hint: str | None = None
    install_command: str | None = None

    @property
    def missing(self) -> bool:
        return not self.available


@dataclass(frozen=True, slots=True)
class AppliedLighting:
    """Proof of what was sent to the hardware, for the log, diagnostics and the tests."""

    device_key: str
    channel: str
    effect: str
    colors: tuple[Color, ...] = ()
    speed: str = ""
    direction: str = ""
    argv: tuple[str, ...] = ()

    @property
    def is_off(self) -> bool:
        return self.effect == OFF_EFFECT

    @property
    def command_line(self) -> str:
        """The command line as a person would type it, for the log and diagnostics."""
        return "liquidctl " + " ".join(self.argv) if self.argv else ""


class HardwareBackend(ABC):
    """What the rest of the application is allowed to ask of the hardware."""

    #: Short name shown in the interface and in diagnostics.
    name: ClassVar[str] = "backend"

    #: True for the development backend, which never touches a real device.
    is_mock: ClassVar[bool] = False

    @property
    @abstractmethod
    def status(self) -> BackendStatus:
        """Current availability of the backend, suitable for showing to a user."""

    @abstractmethod
    def discover_devices(self) -> list[Device]:
        """List connected supported devices. Must not require write access."""

    @abstractmethod
    def initialize_device(self, device: Device) -> Device:
        """Ask the device to detect its accessories; return it with channel details attached."""

    @abstractmethod
    def apply_lighting(self, device: Device, state: LightingState) -> AppliedLighting:
        """Apply channel, effect, colours, speed and direction in one hardware operation."""

    def turn_off(self, device: Device, channel: str) -> AppliedLighting:
        """Switch a channel's LEDs off."""
        return self.apply_lighting(
            device,
            LightingState(channel=channel, effect=OFF_EFFECT, colors=()),
        )


__all__ = ["AppliedLighting", "BackendStatus", "HardwareBackend"]
