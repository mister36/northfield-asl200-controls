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


def _load_inherited(path: Path, chain: tuple[Path, ...] = ()) -> dict:
    if path in chain:
        raise ValueError(f"Cyclic variant inheritance: {path.name}")
    raw = yaml.safe_load(path.read_text())
    base_name = raw.pop("inherits", None)
    if base_name:
        base = _load_inherited(VARIANT_DIR / base_name, (*chain, path))
        return _deep_merge(base, raw)
    return raw


def load_variant(name: str) -> dict:
    merged = _load_inherited(VARIANT_DIR / f"{name}.yaml")
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(merged, schema)
    for axis, unit in (("lift", "deg"), ("reach", "mm")):
        control = merged["controls"]["sensors"][axis]
        hardware = merged["hardware"]["sensors"][axis]
        if control["v_hi_mv"] <= control["v_lo_mv"]:
            raise ValueError(f"{name}: {axis} sensor voltage span must be positive")
        for key in ("v_lo_mv", "v_hi_mv", f"{unit}_at_v_lo", f"{unit}_at_v_hi"):
            if control[key] != hardware[key]:
                raise ValueError(f"{name}: {axis} sensor {key} differs between controls and hardware")
    return merged


if __name__ == "__main__":
    for v in list_variants():
        load_variant(v)
        print(f"{v}: ok")
