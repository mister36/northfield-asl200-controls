import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def pytest_generate_tests(metafunc):
    if {"variant", "scenario"} <= set(metafunc.fixturenames):
        from sil.matrix import cases
        sel = cases(metafunc.config.getoption("variant"), metafunc.config.getoption("scenario"))
        metafunc.parametrize("variant,scenario", sel, ids=[f"{v}-{s}" for v, s in sel])


@pytest.fixture(scope="session")
def out_dir() -> Path:
    d = ROOT / "out"
    d.mkdir(exist_ok=True)
    return d
