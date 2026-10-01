"""ASL-200 software-in-the-loop harness.

The production C controller (built as a per-variant shared library) and a
plant model exchange J1939 frames over a python-can virtual bus. Nothing is
passed between them except encoded CAN frames defined in can/asl200.dbc.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DBC_PATH = REPO_ROOT / "can" / "asl200.dbc"
DEFAULT_BUILD_DIR = REPO_ROOT / "build"
