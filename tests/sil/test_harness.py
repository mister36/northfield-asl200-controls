"""Harness self-checks: determinism, CAN-only coupling, HIL stub honesty."""
import can
import pytest

from sil import dbc
from sil.plant import HilRigPlant
from sil.runner import run


def test_runs_are_deterministic():
    a = run("asl200_diesel_autocar", "normal")
    b = run("asl200_diesel_autocar", "normal")
    assert a["signals"]["lift_deg"] == b["signals"]["lift_deg"]
    assert a["frames"] == b["frames"]


def test_every_frame_is_in_the_dbc():
    tr = run("asl200_electric_mack", "normal")
    ids = {int(f[1], 16) for f in tr["frames"]}
    for fid in ids:
        assert dbc.decode(fid, bytes(8)) is not None, hex(fid)


def test_hil_rig_is_a_stub():
    rig = HilRigPlant()
    with pytest.raises(NotImplementedError, match="connect bench/HIL rig here"):
        rig.attach(can.Bus(interface="virtual", channel="hil-stub"))
