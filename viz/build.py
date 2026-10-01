#!/usr/bin/env python3
"""Build offline HTML from SIL output: out/matrix.html plus one self-contained
animated viewer per case (out/<variant>/<scenario>.html), and optionally a
standalone viewer for any trace files (e.g. a field-log replay pair).

  python3 viz/build.py --out out
  python3 viz/build.py --traces out/replay/x.field.trace.json out/replay/x.resim.trace.json --html out/replay/x.html
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sil.scenarios import SCENARIOS  # noqa: E402

VIEWER = ROOT / "viz" / "viewer.html"
MATRIX = ROOT / "viz" / "matrix.html"
EMBED_VIEWER = '<script id="embedded-traces" type="application/json">[]</script>'
EMBED_MATRIX = '<script id="matrix-data" type="application/json">{"results": [], "scenarios": [], "variants": []}</script>'


def _json_for_script(obj) -> str:
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")


def standalone_viewer(traces: list[dict], path: Path) -> Path:
    html = VIEWER.read_text()
    assert EMBED_VIEWER in html
    html = html.replace(EMBED_VIEWER, f'<script id="embedded-traces" type="application/json">{_json_for_script(traces)}</script>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def build_matrix(out: Path, viewers: bool = True) -> Path:
    results = [json.loads(p.read_text()) for p in sorted(out.glob("*/*.result.json"))]
    for r in results:
        if viewers:
            trace = json.loads((out / r["trace"]).read_text())
            vpath = standalone_viewer([trace], out / r["variant"] / f"{r['scenario']}.html")
            r["viewer"] = str(vpath.relative_to(out))
    data = {"results": results, "variants": sorted({r["variant"] for r in results}),
            "scenarios": [s for s in SCENARIOS if any(r["scenario"] == s for r in results)],
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    html = MATRIX.read_text()
    assert EMBED_MATRIX in html
    html = html.replace(EMBED_MATRIX, f'<script id="matrix-data" type="application/json">{_json_for_script(data)}</script>')
    path = out / "matrix.html"
    path.write_text(html)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--no-viewers", action="store_true")
    ap.add_argument("--traces", type=Path, nargs="+", help="build one standalone viewer for these traces (max 2)")
    ap.add_argument("--html", type=Path, help="output path for --traces")
    args = ap.parse_args()
    if args.traces:
        dest = args.html or args.traces[0].with_suffix("").with_suffix(".html")
        print(standalone_viewer([json.loads(p.read_text()) for p in args.traces[:2]], dest))
        return 0
    print(build_matrix(args.out, viewers=not args.no_viewers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
