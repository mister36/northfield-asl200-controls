"""Load and validate ASL-200 variant YAML files.

Variant files inherit from a base file (``inherits:``) and deep-merge their
overrides on top. The merged result is validated against
``variants/schema.json``.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import yaml

REPO = Path(__file__).resolve().parent.parent
VARIANT_DIR = REPO / "variants"
SCHEMA_PATH = VARIANT_DIR / "schema.json"
SENSOR_CATALOG_PATH = VARIANT_DIR / "sensors.yaml"

DEFAULT_LIFT_SENSOR = "55-1180-1"

# Keys of a catalog entry that make up the controls (params_t) calibration and
# the SIL plant's hardware sensor model, respectively.
_LIFT_CONTROL_KEYS = ("v_lo_mv", "v_hi_mv", "deg_at_v_lo", "deg_at_v_hi",
                      "open_circuit_mv", "short_circuit_mv")
_LIFT_HARDWARE_KEYS = ("v_lo_mv", "v_hi_mv", "deg_at_v_lo", "deg_at_v_hi",
                       "noise_mv", "latency_ms")


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def list_variants() -> list[str]:
    return sorted(p.stem for p in VARIANT_DIR.glob("asl200_*.yaml"))


def _lift_sensor_catalog() -> dict:
    return yaml.safe_load(SENSOR_CATALOG_PATH.read_text())["lift_sensors"]


def resolve_lift_sensor(merged: dict) -> dict:
    """Resolve the variant's `lift_sensor` selection into the controls and
    hardware sensor blocks from variants/sensors.yaml.

    Any `sensors.lift` keys written in a variant file merge on top of the
    selected catalog entry, so individual values can still be overridden.
    """
    catalog = _lift_sensor_catalog()
    sel = merged.get("lift_sensor", DEFAULT_LIFT_SENSOR)
    if sel not in catalog:
        raise ValueError(f"{merged.get('name', 'variant')}: lift_sensor {sel!r} not in "
                         f"{SENSOR_CATALOG_PATH.name} (choices: {', '.join(sorted(catalog))})")
    cal = catalog[sel]
    merged["lift_sensor"] = sel
    merged.setdefault("controls", {}).setdefault("sensors", {})["lift"] = _deep_merge(
        {k: cal[k] for k in _LIFT_CONTROL_KEYS},
        merged["controls"].get("sensors", {}).get("lift", {}))
    merged.setdefault("hardware", {}).setdefault("sensors", {})["lift"] = _deep_merge(
        {"part_number": sel, **{k: cal[k] for k in _LIFT_HARDWARE_KEYS}},
        merged["hardware"].get("sensors", {}).get("lift", {}))
    return merged


def load_variant(name: str) -> dict:
    path = VARIANT_DIR / f"{name}.yaml"
    raw = yaml.safe_load(path.read_text())
    base_name = raw.pop("inherits", None)
    merged = raw
    if base_name:
        base = yaml.safe_load((VARIANT_DIR / base_name).read_text())
        merged = _deep_merge(base, raw)
    merged = resolve_lift_sensor(merged)
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(merged, schema)
    return merged


if __name__ == "__main__":
    for v in list_variants():
        load_variant(v)
        print(f"{v}: ok")
