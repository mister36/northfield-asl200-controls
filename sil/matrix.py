"""Variant x scenario matrix: run cases, save traces/plots/results, summarise."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import params
from .plots import plot_trace
from .runner import run, save_trace, trace_path
from .scenarios import SCENARIOS


def cases(variants: list[str] | None = None, scenarios: list[str] | None = None) -> list[tuple[str, str]]:
    out = []
    for v in variants or params.variants():
        for name, sc in SCENARIOS.items():
            if scenarios and name not in scenarios:
                continue
            if sc.applies_to(v):
                out.append((v, name))
    return out


def run_case(variant: str, scenario: str, out_dir: Path, plots: bool = True) -> dict:
    trace = run(variant, scenario)
    tpath = trace_path(out_dir, variant, scenario)
    save_trace(trace, tpath)
    result = {
        "variant": variant, "scenario": scenario, "passed": trace["passed"], "checks": trace["checks"],
        "cycle_time_s": trace["summary"]["cycle_time_s"], "peak_lift_deg": trace["summary"]["peak_lift_deg"],
        "dtcs": trace["dtcs"], "trace": str(tpath.relative_to(out_dir)),
    }
    if plots:
        ppath = plot_trace(trace, tpath.with_name(f"{scenario}.png"))
        result["plot"] = str(ppath.relative_to(out_dir))
    tpath.with_name(f"{scenario}.result.json").write_text(json.dumps(result, indent=1))
    return result


def collect(out_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(out_dir.glob("*/*.result.json"))]


def summary_markdown(results: list[dict], title: str = "SIL matrix") -> str:
    variants = sorted({r["variant"] for r in results})
    scen = [s for s in SCENARIOS if any(r["scenario"] == s for r in results)]
    by = {(r["variant"], r["scenario"]): r for r in results}
    n_fail = sum(not r["passed"] for r in results)
    lines = [f"### {title}: {len(results) - n_fail}/{len(results)} passed" + (f", **{n_fail} failed**" if n_fail else ""), "",
             "| variant | " + " | ".join(scen) + " |", "|---|" + "---|" * len(scen)]
    for v in variants:
        cells = []
        for s in scen:
            r = by.get((v, s))
            if r is None:
                cells.append("not run")
            elif r["passed"]:
                ct = f" {r['cycle_time_s']:.1f}s" if r["cycle_time_s"] and SCENARIOS[s].check_cycle_time else ""
                cells.append(f"✅{ct}")
            else:
                cells.append("❌")
        lines.append(f"| `{v}` | " + " | ".join(cells) + " |")
    fails = [r for r in results if not r["passed"]]
    if fails:
        lines += ["", "**Failures**", ""]
        for r in fails:
            why = "; ".join(f"{c['name']}: {c['detail']}" for c in r["checks"] if not c["passed"])
            lines.append(f"- `{r['variant']}` / `{r['scenario']}`: {why}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", action="append", choices=params.variants())
    ap.add_argument("--scenario", action="append", choices=sorted(SCENARIOS))
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--no-plots", action="store_true")
    ap.add_argument("--summary-only", action="store_true", help="only (re)write summary.md/json from existing results")
    args = ap.parse_args()
    results = []
    for v, s in ([] if args.summary_only else cases(args.variant, args.scenario)):
        r = run_case(v, s, args.out, plots=not args.no_plots)
        results.append(r)
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {v:30s} {s}")
    md = summary_markdown(collect(args.out))
    (args.out / "summary.md").write_text(md)
    (args.out / "summary.json").write_text(json.dumps(collect(args.out), indent=1))
    print()
    print(md)
    return 0 if all(r["passed"] for r in (results or collect(args.out))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
