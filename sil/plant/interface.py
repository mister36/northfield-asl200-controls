"""Plant interface: anything that can sit on the other side of the controller's CAN bus."""
from __future__ import annotations

from abc import ABC, abstractmethod

import can


class PlantInterface(ABC):
    """A truck body (simulated or real) connected to the body controller by CAN.

    The harness calls tick() once per 10 ms. Implementations read controller
    frames from their bus, advance (or sample) the physical system, and
    transmit sensor / vehicle / operator frames. truth() returns ground-truth
    measurements for the trace; on a rig these come from bench instruments.
    """

    @abstractmethod
    def attach(self, bus: can.BusABC) -> None: ...

    @abstractmethod
    def tick(self, t_s: float, dt_s: float) -> list[can.Message]:
        """Consume received frames, advance by dt_s, return frames transmitted."""

    @abstractmethod
    def truth(self) -> dict: ...

    def close(self) -> None:  # pragma: no cover - optional hook
        pass
