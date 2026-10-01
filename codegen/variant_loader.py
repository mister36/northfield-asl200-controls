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


def load_variant(name: str) -> dict:
    path = VARIANT_DIR / f"{name}.yaml"
    raw = yaml.safe_load(path.read_text())
    base_name = raw.pop("inherits", None)
    merged = raw
    if base_name:
        base = yaml.safe_load((VARIANT_DIR / base_name).read_text())
        merged = _deep_merge(base, raw)
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(merged, schema)
    return merged


if __name__ == "__main__":
    for v in list_variants():
        load_variant(v)
        print(f"{v}: ok")
