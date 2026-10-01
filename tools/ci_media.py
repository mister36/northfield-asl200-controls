#!/usr/bin/env python3
"""Collect plots and render GIFs for failing SIL cases (used by CI for the PR comment)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "viz"))

from render_gif import render  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--media", type=Path, default=Path("out/media"))
    ap.add_argument("--max", type=int, default=4)
    args = ap.parse_args()
    args.media.mkdir(parents=True, exist_ok=True)
    fails = [json.loads(p.read_text()) for p in sorted(args.out.glob("*/*.result.json"))]
    fails = [r for r in fails if not r["passed"]][: args.max]
    index = []
    for r in fails:
        stem = f"{r['variant']}__{r['scenario']}"
        entry = {"variant": r["variant"], "scenario": r["scenario"],
                 "reason": "; ".join(c["detail"] for c in r["checks"] if not c["passed"])}
        if r.get("plot"):
            shutil.copy(args.out / r["plot"], args.media / f"{stem}.png")
            entry["png"] = f"{stem}.png"
        trace = json.loads((args.out / r["trace"]).read_text())
        render([trace], args.media / f"{stem}.gif", fps=10, speed=2.0)
        entry["gif"] = f"{stem}.gif"
        index.append(entry)
        print(f"media: {stem}")
    (args.media / "index.json").write_text(json.dumps(index, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
