"""Field-log regression replays: closed-loop re-simulation of real candump logs.

Each test rebuilds the field conditions and operator inputs from a log in
field_logs/ (same code path as tools/replay_log.py) and runs the current
firmware against the plant. A field bug that is fixed must not come back:
the re-simulation must raise no DTCs and complete the pick.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from replay_log import scenario_from_log  # noqa: E402
from sil.runner import run  # noqa: E402


@pytest.mark.parametrize("log,variant", [
    # ASLCTL-157: unit 4471, electric Mack, -5F morning, false arm-lift stall
    # DTCs on the first lifts of the shift.
    ("unit4471_2026-01-14_0642.log", "asl200_electric_mack"),
])
def test_field_log_replay_no_dtcs(log, variant):
    resim = run(variant, scenario_from_log(ROOT / "field_logs" / log))
    assert not resim["dtcs"], \
        f"{variant} replay of {log} raised DTCs: {[(d['spn'], d['fmi']) for d in resim['dtcs']]}"
    assert resim["summary"]["peak_lift_deg"] >= 140.0, \
        f"arm never reached the dump angle (peak {resim['summary']['peak_lift_deg']:.1f} deg)"
