"""Variant loader: `lift_sensor` selects the sensor calibration (ECO-0412).

Bodies >= ASL2-26-04100 ship with P/N 55-1180-1 (0.5-4.5 V); earlier bodies
keep 55-1180-0 (0-5 V). The loader resolves the selection into
`controls.sensors.lift` (compiled into params_t) and `hardware.sensors.lift`
(the SIL plant's sensor model, including part_number).
"""
import pytest

from codegen.variant_loader import load_variant, resolve_lift_sensor

POST_BREAK_VARIANTS = ("asl200_diesel_autocar", "asl200_cng_peterbilt",
                       "asl200_electric_mack", "asl200_diesel_mack_longreach")


@pytest.mark.parametrize("variant", POST_BREAK_VARIANTS)
def test_default_variants_use_eco0412_sensor(variant):
    v = load_variant(variant)
    assert v["lift_sensor"] == "55-1180-1"
    cal = v["controls"]["sensors"]["lift"]
    assert (cal["v_lo_mv"], cal["v_hi_mv"]) == (500, 4500)
    assert (cal["deg_at_v_lo"], cal["deg_at_v_hi"]) == (-20.0, 180.0)
    assert v["hardware"]["sensors"]["lift"]["part_number"] == "55-1180-1"


def test_legacy_variant_keeps_55_1180_0():
    v = load_variant("asl200_diesel_autocar_legacy")
    assert v["lift_sensor"] == "55-1180-0"
    cal = v["controls"]["sensors"]["lift"]
    assert (cal["v_lo_mv"], cal["v_hi_mv"]) == (0, 5000)
    assert v["hardware"]["sensors"]["lift"]["part_number"] == "55-1180-0"


def test_unknown_lift_sensor_rejected():
    merged = load_variant("asl200_diesel_autocar")
    merged["lift_sensor"] = "55-9999-9"
    with pytest.raises(ValueError, match="lift_sensor"):
        resolve_lift_sensor(merged)


def test_diagnostic_bands_match_eco():
    """Both revisions use the ECO-0412 diagnostic bands: < 0.25 V open,
    > 4.75 V short-to-supply."""
    for variant in ("asl200_diesel_autocar", "asl200_diesel_autocar_legacy"):
        cal = load_variant(variant)["controls"]["sensors"]["lift"]
        assert (cal["open_circuit_mv"], cal["short_circuit_mv"]) == (250, 4750)
