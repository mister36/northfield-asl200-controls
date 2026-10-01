"""ctypes wrapper around the per-variant SIL shared library."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import can

from . import DEFAULT_BUILD_DIR

MAX_TX = 8


class CanFrame(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("dlc", ctypes.c_uint8), ("data", ctypes.c_uint8 * 8)]


def library_path(variant: str, build_dir: Path | None = None) -> Path:
    build = Path(build_dir or os.environ.get("ASL200_BUILD_DIR", DEFAULT_BUILD_DIR))
    path = build / "sil" / f"libasl200_sil_{variant}.so"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run: cmake -S . -B build && cmake --build build")
    return path


class ControllerECU:
    """The body controller as a node on a CAN bus.

    Each call to step() drains received frames, runs one 10 ms controller
    step in C, and transmits whatever the controller scheduled.
    """

    def __init__(self, variant: str, bus: can.BusABC, build_dir: Path | None = None):
        # Load a private copy so several variants can run in one process.
        self._lib = ctypes.CDLL(str(library_path(variant, build_dir)), mode=os.RTLD_LOCAL)
        self._lib.sil_variant_name.restype = ctypes.c_char_p
        self._lib.sil_step_ms.restype = ctypes.c_uint32
        self._lib.sil_step.restype = ctypes.c_uint8
        self._lib.sil_step.argtypes = [ctypes.POINTER(CanFrame), ctypes.c_uint32,
                                       ctypes.POINTER(CanFrame), ctypes.c_uint8]
        self.variant = self._lib.sil_variant_name().decode()
        if self.variant != variant:
            raise RuntimeError(f"library reports variant {self.variant}, expected {variant}")
        self.step_ms = int(self._lib.sil_step_ms())
        self.bus = bus
        self._rx = (CanFrame * 64)()
        self._tx = (CanFrame * MAX_TX)()
        self._lib.sil_reset()

    def step(self, t_s: float) -> list[can.Message]:
        n = 0
        while n < len(self._rx):
            msg = self.bus.recv(timeout=0)
            if msg is None:
                break
            f = self._rx[n]
            f.id = msg.arbitration_id
            f.dlc = msg.dlc
            for i in range(8):
                f.data[i] = msg.data[i] if i < len(msg.data) else 0xFF
            n += 1
        n_tx = self._lib.sil_step(self._rx, n, self._tx, MAX_TX)
        sent = []
        for i in range(n_tx):
            f = self._tx[i]
            msg = can.Message(arbitration_id=f.id, is_extended_id=True, data=bytes(f.data[: f.dlc]),
                              timestamp=t_s)
            self.bus.send(msg)
            sent.append(msg)
        return sent
