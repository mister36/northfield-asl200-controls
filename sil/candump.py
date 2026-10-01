"""Read/write candump -l format: "(1705236120.123456) can0 18FEF100#FFFF1E00FFFFFFFF"."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LINE = re.compile(r"^\((\d+\.\d+)\)\s+(\S+)\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]*)\s*$")


@dataclass(frozen=True)
class LoggedFrame:
    t: float
    channel: str
    can_id: int
    data: bytes


def read(path: Path) -> list[LoggedFrame]:
    frames = []
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        m = LINE.match(line)
        if not m:
            raise ValueError(f"{path}:{n}: not a candump line: {line!r}")
        frames.append(LoggedFrame(float(m.group(1)), m.group(2), int(m.group(3), 16), bytes.fromhex(m.group(4))))
    return frames


def format_line(t: float, can_id: int, data: bytes, channel: str = "can0") -> str:
    return f"({t:.6f}) {channel} {can_id:08X}#{data.hex().upper()}"
