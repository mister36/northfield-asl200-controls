#!/usr/bin/env python3
"""Decode ASL-200 DTCs.

  tools/decode_dtc.py 520210 7          # one SPN/FMI
  tools/decode_dtc.py --log field.log   # every DM1 in a candump log
  tools/decode_dtc.py --list            # the whole table
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sil import candump, dbc  # noqa: E402

TABLE = ROOT / "can" / "faults.yaml"


def load_table() -> dict:
    return yaml.safe_load(TABLE.read_text())


def describe(spn: int, fmi: int, table: dict | None = None) -> str:
    table = table or load_table()
    fmi_text = table["fmi"].get(fmi, f"FMI {fmi}")
    entry = table["spn"].get(spn)
    if entry is None:
        return f"SPN {spn} FMI {fmi}: unknown SPN ({fmi_text})"
    detail = entry["fmi"].get(fmi)
    if detail is None:
        return f"SPN {spn} FMI {fmi}: {entry['name']} - {fmi_text}"
    return f"SPN {spn} FMI {fmi}: {entry['name']} - {detail['text']}\n    action: {detail['action']}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spn", nargs="?", type=int)
    ap.add_argument("fmi", nargs="?", type=int)
    ap.add_argument("--log", type=Path, help="candump log to scan for DM1 frames")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    table = load_table()
    if args.list:
        for spn, e in table["spn"].items():
            for fmi in e["fmi"]:
                print(describe(spn, fmi, table))
        return 0
    if args.log:
        dm1 = dbc.frame_id("DM1")
        last = None
        for f in candump.read(args.log):
            if f.can_id != dm1:
                continue
            d = dbc.dm1_dtc(dbc.decode(f.can_id, f.data)[1])
            if d != last and d is not None:
                ts = datetime.fromtimestamp(f.t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"{ts} UTC  OC={d[2]}  " + describe(d[0], d[1], table))
            last = d
        return 0
    if args.spn is None or args.fmi is None:
        ap.error("give SPN and FMI, --log or --list")
    print(describe(args.spn, args.fmi, table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
