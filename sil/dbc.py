"""DBC access shared by the plant, replay and DTC tools."""
from __future__ import annotations

from functools import lru_cache

import cantools

from . import DBC_PATH


@lru_cache(maxsize=1)
def database() -> cantools.database.Database:
    return cantools.database.load_file(str(DBC_PATH))


def frame_id(name: str) -> int:
    return database().get_message_by_name(name).frame_id


def encode(name: str, signals: dict) -> bytes:
    msg = database().get_message_by_name(name)
    full = {s.name: 0 for s in msg.signals}
    full.update(signals)
    return msg.encode(full, strict=False, padding=True)


def decode(arbitration_id: int, data: bytes) -> tuple[str, dict] | None:
    try:
        msg = database().get_message_by_frame_id(arbitration_id)
    except KeyError:
        return None
    return msg.name, msg.decode(bytes(data), decode_choices=False)


def dm1_dtc(signals: dict) -> tuple[int, int, int] | None:
    """Return (spn, fmi, occurrence) from a decoded DM1, or None if no DTC."""
    spn = int(signals["SPN_Low16"]) | (int(signals["SPN_High3"]) << 16)
    if spn == 0:
        return None
    return spn, int(signals["FMI"]), int(signals["OccurrenceCount"])
