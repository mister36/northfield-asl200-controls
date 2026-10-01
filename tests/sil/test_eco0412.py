"""Independent datasheet and effectivity checks for both lift sensor families."""
import copy

import pytest
import yaml

from codegen import variant_loader
from codegen.variant_loader import load_variant
from sil import params
from sil.plant import SimPlant
from sil.runner import run
from sil.scenarios import Scenario

LEGACY = [v for v in params.variants() if not v.endswith("_eco0412")]


@pytest.mark.parametrize("axis,key,value,message", (
    ("lift", "v_lo_mv", 4500, "span must be positive"),
    ("lift", "v_hi_mv", 4400, "differs between controls and hardware"),
    ("reach", "mm_at_v_hi", 2100, "differs between controls and hardware"),
))
def test_rejects_inconsistent_sensor_configuration(tmp_path, monkeypatch, axis, key, value, message):
    cfg = load_variant("asl200_diesel_autocar_eco0412")
    cfg["controls"]["sensors"][axis][key] = value
    (tmp_path / "invalid.yaml").write_text(yaml.safe_dump(cfg))
    monkeypatch.setattr(variant_loader, "VARIANT_DIR", tmp_path)
    with pytest.raises(ValueError, match=message):
        load_variant("invalid")


def test_rejects_cyclic_inheritance(tmp_path, monkeypatch):
    (tmp_path / "a.yaml").write_text("inherits: b.yaml\n")
    (tmp_path / "b.yaml").write_text("inherits: a.yaml\n")
    monkeypatch.setattr(variant_loader, "VARIANT_DIR", tmp_path)
    with pytest.raises(ValueError, match="Cyclic variant inheritance"):
        load_variant("a")


@pytest.mark.parametrize("legacy", LEGACY)
def test_effectivity_parameters(legacy):
    old = load_variant(legacy)
    new = load_variant(f"{legacy}_eco0412")
    assert old["hardware"]["sensors"]["lift"]["part_number"] == "55-1180-0"
    assert new["hardware"]["sensors"]["lift"]["part_number"] == "55-1180-1"
    for cfg, lo, hi in ((old, 0, 5000), (new, 500, 4500)):
        for section in ("controls", "hardware"):
            sensor = cfg[section]["sensors"]["lift"]
            assert (sensor["v_lo_mv"], sensor["v_hi_mv"]) == (lo, hi)
            assert (sensor["deg_at_v_lo"], sensor["deg_at_v_hi"]) == (-20, 180)
        sensor = cfg["controls"]["sensors"]["lift"]
        assert (sensor["open_circuit_mv"], sensor["short_circuit_mv"]) == (250, 4750)
    old = copy.deepcopy(old)
    new = copy.deepcopy(new)
    for cfg in (old, new):
        cfg.pop("name")
        cfg.pop("description")
        for section in ("controls", "hardware"):
            cfg[section]["sensors"].pop("lift")
    assert old == new


@pytest.mark.parametrize("variant", params.variants())
def test_physical_sensor_datasheet(variant):
    cfg = copy.deepcopy(params.load(variant))
    cfg["hardware"]["sensors"]["lift"]["noise_mv"] = 0
    plant = SimPlant(cfg, Scenario("datasheet", "Independent physical transfer points"), 0)
    cal = cfg["hardware"]["sensors"]["lift"]
    points = ((-20, 500), (0, 900), (80, 2500), (150, 3900), (180, 4500)) if cal["part_number"] == "55-1180-1" else (
        (-20, 0), (0, 500), (80, 2500), (150, 4250), (180, 5000))
    for angle, mv in points:
        assert plant._to_mv(angle, cal, "deg") == mv


@pytest.mark.parametrize("variant", params.variants())
def test_home_angle_and_upper_limit(variant):
    trace = run(variant, "arm_at_limit")
    assert trace["passed"], trace["checks"]
    assert abs(trace["signals"]["ctrl_lift_deg"][5]) < 0.5
    assert trace["signals"]["lift_mv"][0] == pytest.approx(900 if variant.endswith("_eco0412") else 500, abs=15)
    assert trace["summary"]["peak_lift_deg"] > 150
