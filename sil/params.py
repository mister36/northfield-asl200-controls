"""Resolved variant parameters (controls + hardware) for the harness."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import DEFAULT_BUILD_DIR, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "codegen"))
from variant_loader import list_variants, load_variant  # noqa: E402


def variants() -> list[str]:
    return list_variants()


def load(variant: str, build_dir: Path | None = None) -> dict:
    """Prefer the blob generated alongside the compiled library so the plant
    and the controller always see the same parameter set."""
    build = Path(build_dir or os.environ.get("ASL200_BUILD_DIR", DEFAULT_BUILD_DIR))
    blob = build / "generated" / f"params_{variant}.json"
    if blob.exists():
        return json.loads(blob.read_text())
    return load_variant(variant)
