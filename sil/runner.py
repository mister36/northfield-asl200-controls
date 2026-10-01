"""Run one variant x scenario through the SIL loop and produce a trace."""
from __future__ import annotations

import argparse
import json
import uuid
import zlib
from pathlib import Path

import can

from . import dbc, params as params_mod
from .checks import run_checks
from .ecu import ControllerECU
from .plant import SimPlant
from .scenarios import SCENARIOS, Scenario

DT_S = 0.010
STATE_NAMES = ["IDLE", "REACH_OUT", "GRIP", "LIFT", "DUMP", "LOWER", "RELEASE", "RETRACT", "FAULT_STOP"]
TRACE_VERSION = 1
CONTROLLER_TX_IDS = {dbc.frame_id(n) for n in ("ARM_CMD", "ARM_STATE", "ARM_POSITION", "DM1")}


def seed_for(variant: str, scenario: str) -> int:
    return zlib.crc32(f"{variant}/{scenario}".encode())


def _bus(channel: str) -> can.BusABC:
    return can.Bus(interface="virtual", channel=channel, preserve_timestamps=True, receive_own_messages=False)


def run(variant: str, scenario: Scenario | str, build_dir: Path | None = None, seed: int | None = None,
        candump_path: Path | None = None) -> dict:
    sc = SCENARIOS[scenario] if isinstance(scenario, str) else scenario
    prm = params_mod.load(variant, build_dir)
    seed = seed_for(variant, sc.name) if seed is None else seed
    channel = f"asl200-{uuid.uuid4().hex[:8]}"
    ecu_bus, plant_bus, log_bus = _bus(channel), _bus(channel), _bus(channel)
    ecu = ControllerECU(variant, ecu_bus, build_dir)
    plant = SimPlant(prm, sc, seed)
    plant.attach(plant_bus)

    names = ["t", "lift_deg", "lift_dps", "reach_mm", "lift_cmd_pct", "reach_cmd_pct", "grip_cmd", "grip_bar",
             "state", "lift_phase", "speed_mph", "tailgate_open", "ilk_speed_ok", "ilk_grip_secured",
             "soft_limit_active", "stall_detected", "ctrl_lift_deg", "lift_mv", "auto_request", "dtc_spn",
             "effort"]
    sig: dict[str, list] = {k: [] for k in names}
    events: list[dict] = []
    dtcs: list[dict] = []
    active_dtc = None
    frames: list[can.Message] = []
    state = 0
    cycle_count0 = None
    cycle_start = None
    cycle_time = None
    steps = int(round(sc.duration_s / DT_S))
    try:
        for k in range(steps):
            t = round(k * DT_S, 3)
            plant.tick(t, DT_S)
            ecu.step(t)
            while (msg := log_bus.recv(timeout=0)) is not None:
                frames.append(msg)
                decoded = dbc.decode(msg.arbitration_id, msg.data)
                if decoded and decoded[0] == "DM1":
                    d = dbc.dm1_dtc(decoded[1])
                    if d and (active_dtc is None or active_dtc[:2] != d[:2]):
                        dtcs.append({"t": t, "spn": d[0], "fmi": d[1], "oc": d[2]})
                        events.append({"t": t, "type": "dtc", "text": f"DTC SPN {d[0]} FMI {d[1]}"})
                    active_dtc = d
            tr = plant.truth()
            st = plant.ctrl_state
            new_state = int(st.get("CycleState", 0))
            if new_state != state:
                events.append({"t": t, "type": "state", "text": f"{STATE_NAMES[state]} -> {STATE_NAMES[new_state]}"})
                if state == 0 and cycle_start is None:
                    cycle_start = t
                state = new_state
            cc = int(st.get("CycleCount", 0))
            if cycle_count0 is None and st:
                cycle_count0 = cc
            if cycle_count0 is not None and cc > cycle_count0 and cycle_time is None and cycle_start is not None:
                cycle_time = round(t - sc.auto_press_s, 3)
            row = {
                "t": t, "lift_deg": round(tr["lift_deg"], 3), "lift_dps": round(tr["lift_dps"], 2),
                "reach_mm": round(tr["reach_mm"], 1),
                "lift_cmd_pct": round(float(plant.cmd["LiftVelocityCmd"]), 2),
                "reach_cmd_pct": round(float(plant.cmd["ReachVelocityCmd"]), 2),
                "grip_cmd": int(plant.cmd["GripCmd"]), "grip_bar": round(tr["grip_bar"], 1),
                "state": state, "lift_phase": int(st.get("LiftPhase", 0)),
                "speed_mph": tr["speed_mph"], "tailgate_open": int(tr["tailgate_open"]),
                "ilk_speed_ok": int(st.get("IlkVehicleSpeedOk", 0)),
                "ilk_grip_secured": int(st.get("IlkGripSecured", 0)),
                "soft_limit_active": int(st.get("SoftLimitActive", 0)),
                "stall_detected": int(st.get("StallDetected", 0)),
                "ctrl_lift_deg": round(float(plant.ctrl_pos.get("ArmLiftAngle", 0.0)), 2),
                "lift_mv": tr["lift_mv"], "auto_request": int(tr["auto_request"]),
                "dtc_spn": plant.dm1_active[0] if plant.dm1_active else 0,
                "effort": round(tr["effort"], 1),
            }
            for key in names:
                sig[key].append(row[key])
    finally:
        for b in (ecu_bus, plant_bus, log_bus):
            b.shutdown()

    trace = {
        "version": TRACE_VERSION,
        "meta": {"variant": variant, "scenario": sc.name, "description": sc.description, "seed": seed,
                 "dt_s": DT_S, "ambient_c": round(sc.ambient_c, 2),
                 "battery_c": sc.battery_temp() if prm["hardware"]["powertrain"] == "electric" else None,
                 "powertrain": prm["hardware"]["powertrain"], "params": prm, "state_names": STATE_NAMES,
                 "effort_unit": "A" if prm["hardware"]["powertrain"] == "electric" else "bar",
                 "source": "sil", "dbc": dbc.layout()},
        "signals": sig,
        "events": events,
        "dtcs": dtcs,
        "frames": [[round(m.timestamp, 3), f"{m.arbitration_id:08X}", bytes(m.data).hex().upper(),
                    "tx" if m.arbitration_id in CONTROLLER_TX_IDS else "rx"] for m in frames],
        "summary": {"cycle_time_s": cycle_time, "final_state": STATE_NAMES[state],
                    "peak_lift_deg": max(sig["lift_deg"]), "frames": len(frames)},
    }
    checks = run_checks(trace, sc)
    trace["checks"] = [c.to_dict() for c in checks]
    trace["passed"] = all(c.passed for c in checks)
    if candump_path is not None:
        write_candump(frames, candump_path)
    return trace


def write_candump(frames: list[can.Message], path: Path, channel: str = "can0", t0: float = 0.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for m in frames:
            fh.write(f"({t0 + m.timestamp:.6f}) {channel} {m.arbitration_id:08X}#{bytes(m.data).hex().upper()}\n")


def trace_path(out_dir: Path, variant: str, scenario: str) -> Path:
    return out_dir / variant / f"{scenario}.trace.json"


def save_trace(trace: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, separators=(",", ":")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", required=True, choices=params_mod.variants())
    ap.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--candump", action="store_true", help="also write the bus log in candump format")
    args = ap.parse_args()
    stem = f"{args.variant}/{args.scenario}"
    path = trace_path(args.out, args.variant, args.scenario)
    trace = run(args.variant, args.scenario, candump_path=path.with_suffix("").with_suffix(".log") if args.candump else None)
    save_trace(trace, path)
    print(f"trace: {path}")
    for c in trace["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
    print(f"{stem}: {'PASS' if trace['passed'] else 'FAIL'}")
    return 0 if trace["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
