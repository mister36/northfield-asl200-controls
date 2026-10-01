"""Pass/fail checks applied to every SIL run."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .scenarios import Scenario

SOFT_LIMIT_TOL_DEG = 0.5
SOFT_LIMIT_TOL_MM = 10.0
INTERLOCK_LATENCY_S = 0.15   # CCVS period (100 ms) + one controller step + bus
MOTION_EPS_PCT = 0.5


@dataclass
class Check:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _first(seq, pred):
    for i, x in enumerate(seq):
        if pred(x):
            return i
    return None


def run_checks(trace: dict, scenario: Scenario) -> list[Check]:
    sig = trace["signals"]
    p = trace["meta"]["params"]["controls"]
    t = sig["t"]
    n = len(t)
    checks: list[Check] = []

    # 1. Vehicle-speed / tailgate interlocks never violated.
    limit_mph = p["interlocks"]["vehicle_speed_limit_mph"]
    worst = None
    inhibit_since = None
    for i in range(n):
        inhibited = sig["speed_mph"][i] > limit_mph or (p["interlocks"]["tailgate_inhibit"] and sig["tailgate_open"][i])
        if inhibited:
            inhibit_since = t[i] if inhibit_since is None else inhibit_since
            moving = abs(sig["lift_cmd_pct"][i]) > MOTION_EPS_PCT or abs(sig["reach_cmd_pct"][i]) > MOTION_EPS_PCT
            if moving and t[i] - inhibit_since > INTERLOCK_LATENCY_S and worst is None:
                worst = (t[i], sig["speed_mph"][i])
        else:
            inhibit_since = None
    checks.append(Check("interlocks", worst is None,
                        "arm never commanded while inhibited" if worst is None else
                        f"arm commanded at t={worst[0]:.2f}s with vehicle at {worst[1]:.1f} mph (limit {limit_mph} mph)"))

    # 2. Soft limits never exceeded (ground truth position).
    lim = p["limits"]
    lmax, lmin = max(sig["lift_deg"]), min(sig["lift_deg"])
    rmax = max(sig["reach_mm"])
    over = []
    if lmax > lim["lift_soft_max_deg"] + SOFT_LIMIT_TOL_DEG:
        i = sig["lift_deg"].index(lmax)
        over.append(f"lift reached {lmax:.2f} deg at t={t[i]:.2f}s (soft max {lim['lift_soft_max_deg']})")
    if lmin < lim["lift_soft_min_deg"] - SOFT_LIMIT_TOL_DEG:
        over.append(f"lift reached {lmin:.2f} deg (soft min {lim['lift_soft_min_deg']})")
    if rmax > lim["reach_soft_max_mm"] + SOFT_LIMIT_TOL_MM:
        over.append(f"reach {rmax:.0f} mm (soft max {lim['reach_soft_max_mm']})")
    checks.append(Check("soft_limits", not over,
                        f"peak lift {lmax:.2f} deg, peak reach {rmax:.0f} mm" if not over else "; ".join(over)))

    # 3. DTCs: exactly the expected set.
    seen = {(d["spn"], d["fmi"]) for d in trace["dtcs"]}
    unexpected = seen - set(scenario.expect_dtcs)
    missing = set(scenario.expect_dtcs) - seen
    detail = []
    for spn, fmi in sorted(unexpected):
        first = next(d for d in trace["dtcs"] if (d["spn"], d["fmi"]) == (spn, fmi))
        detail.append(f"unexpected DTC SPN {spn} FMI {fmi} at t={first['t']:.2f}s")
    for spn, fmi in sorted(missing):
        detail.append(f"expected DTC SPN {spn} FMI {fmi} not raised")
    checks.append(Check("dtcs", not unexpected and not missing,
                        "; ".join(detail) if detail else
                        ("no DTCs" if not seen else "expected DTCs: " + ", ".join(f"{s}/{f}" for s, f in sorted(seen)))))

    # 4. Cycle completes, within budget where required.
    budget = p["requirements"]["cycle_time_budget_s"]
    ct = trace["summary"].get("cycle_time_s")
    if scenario.expect_cycle_complete:
        if ct is None:
            checks.append(Check("cycle_complete", False, f"cycle did not complete (final state {trace['summary']['final_state']})"))
        elif scenario.check_cycle_time:
            checks.append(Check("cycle_time", ct <= budget, f"{ct:.2f}s (budget {budget:.1f}s)"))
        else:
            checks.append(Check("cycle_complete", True, f"{ct:.2f}s (budget not applied)"))
    else:
        checks.append(Check("cycle_complete", ct is None, "cycle correctly not completed" if ct is None else
                            f"cycle completed in {ct:.2f}s but should have been aborted"))

    # 5. Scenario-specific.
    if scenario.expect_no_lift:
        checks.append(Check("no_lift_without_grip", lmax < 5.0, f"peak lift {lmax:.2f} deg"))
    if scenario.expect_dtcs:
        i_fault = _first(sig["state"], lambda s: s == 8)
        if i_fault is None:
            checks.append(Check("fault_stop", False, "controller never entered FAULT_STOP"))
        else:
            tail = range(i_fault + 1, n)
            moving = any(abs(sig["lift_cmd_pct"][i]) > MOTION_EPS_PCT for i in tail)
            checks.append(Check("fault_stop", not moving, f"FAULT_STOP at t={t[i_fault]:.2f}s, outputs "
                                + ("still active" if moving else "zeroed")))
    return checks
