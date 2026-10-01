"""SIL scenario matrix: every applicable variant x scenario must pass every check.

Cases come from sil.matrix.cases(); restrict with --variant / --scenario."""
from sil.matrix import run_case


def test_scenario(variant, scenario, out_dir):
    result = run_case(variant, scenario, out_dir)
    failed = [f"{c['name']}: {c['detail']}" for c in result["checks"] if not c["passed"]]
    assert not failed, f"{variant}/{scenario}: " + "; ".join(failed)
