"""Field-log regressions: closed-loop re-simulation of logs pulled from units in service.

Each case replays a log's conditions (ambient, battery temperature, road speed) and operator
console inputs through the plant and the current firmware for the variant the unit runs."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from replay_log import scenario_from_log  # noqa: E402
from sil.runner import run  # noqa: E402

FIELD_CASES = [
    # ASLCTL-157: unit 4471, -5F, pack -18C; lift stall DTC on the first lifts of the shift.
    ("asl200_electric_mack", "unit4471_2026-01-14_0642.log"),
]


@pytest.mark.parametrize("variant,log", FIELD_CASES, ids=[f"{v}-{Path(l).stem}" for v, l in FIELD_CASES])
def test_field_log_resim_has_no_dtcs(request, variant, log):
    selected = request.config.getoption("variant")
    if selected and variant not in selected:
        pytest.skip(f"variant {variant} not selected")
    trace = run(variant, scenario_from_log(ROOT / "field_logs" / log))
    raised = [f"SPN {d['spn']} FMI {d['fmi']} at t={d['t']:.2f}s" for d in trace["dtcs"]]
    assert not raised, f"{variant} re-sim of {log} raised: " + "; ".join(raised)
    assert 8 not in trace["signals"]["state"], "controller entered FAULT_STOP"
    assert trace["summary"]["peak_lift_deg"] > 140.0, "arm never reached the dump angle"
