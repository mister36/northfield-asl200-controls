"""Hardware-in-the-loop rig adapter (placeholder).

Same interface as SimPlant, so scenarios and checks run unchanged once a
bench is connected: a real ECU on a SocketCAN / PCAN channel, the arm I/O
node and actuator driver either real or emulated by the rig.
"""
from __future__ import annotations

import can

from .interface import PlantInterface


class HilRigPlant(PlantInterface):
    def __init__(self, channel: str = "can0", interface: str = "socketcan"):
        self.channel = channel
        self.interface = interface

    def attach(self, bus: can.BusABC) -> None:
        raise NotImplementedError("connect bench/HIL rig here")

    def tick(self, t_s: float, dt_s: float) -> list[can.Message]:
        raise NotImplementedError("connect bench/HIL rig here")

    def truth(self) -> dict:
        raise NotImplementedError("connect bench/HIL rig here")
