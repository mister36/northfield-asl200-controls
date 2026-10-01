#!/usr/bin/env python3
"""Replay a candump field log through the SIL.

Two passes:

1. Open-loop: every frame the body controller *received* in the field
   (vehicle speed, temperatures, operator console, arm sensors, actuator
   status) is fed, on its original 10 ms tick, into the current firmware
   built for --variant. The frames the firmware sends back are compared with
   what the field ECU sent (ARM_CMD, ARM_STATE, DM1). Matching outputs mean
   the current code reproduces the field behaviour bit for bit.

2. Closed-loop re-simulation: the conditions from the log (ambient and
   battery temperature, vehicle speed, operator console inputs) drive the
   simulated plant and the current firmware together. This answers "what
   would this firmware do on that truck, that morning?" - the run to use for
   a regression test, and the one that changes once the firmware is fixed.

  tools/replay_log.py field_logs/unit4471_2026-01-14_0642.log --variant asl200_electric_mack
  tools/replay_log.py <log> --variant <v> --viz      # also write traces for viz/viewer.html
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import can

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sil import candump, dbc, params as params_mod  # noqa: E402
from sil.ecu import ControllerECU  # noqa: E402
from sil.logtrace import trace_from_frames  # noqa: E402
from sil.runner import CONTROLLER_TX_IDS, DT_S, STATE_NAMES, run, save_trace  # noqa: E402
from sil.scenarios import Scenario  # noqa: E402

from decode_dtc import describe  # noqa: E402

KPH_PER_MPH = 1.609344
CMD_TOL_PCT = 1.0


def utc(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def conditions(frames: list[candump.LoggedFrame], t0: float) -> dict:
    """Extract the operating conditions a re-simulation needs."""
    amb, batt = [], []
    speed: list[tuple[float, float]] = []
    joy: list[tuple[float, int, int, int, int, int]] = []
    for f in frames:
        dec = dbc.decode(f.can_id, f.data)
        if dec is None:
            continue
        name, s = dec
        t = round(f.t - t0, 3)
        if name == "AMB":
            amb.append(float(s["AmbientAirTemperature"]))
        elif name == "BATT_STATUS":
            batt.append(float(s["BatteryTemperature"]))
        elif name == "CCVS":
            mph = round(float(s["WheelBasedVehicleSpeed"]) / KPH_PER_MPH, 1)
            if not speed or speed[-1][1] != mph:
                speed.append((t, mph))
        elif name == "JOY_CMD":
            row = (int(s["AutoCycleRequest"]), int(s["FaultReset"]), int(s["JogLift"]), int(s["JogReach"]),
                   int(s["GripRequest"]))
            if not joy or joy[-1][1:] != row:
                joy.append((t, *row))
    return {
        "ambient_c": round(sum(amb) / len(amb), 1) if amb else None,
        "battery_c": round(sum(batt) / len(batt), 1) if batt else None,
        "vehicle_speed_mph": speed, "joy_script": joy,
        "duration_s": round(frames[-1].t - t0, 2),
    }


def scenario_from_log(log: Path, name: str = "field_replay") -> Scenario:
    """Closed-loop scenario reproducing a field log's conditions and operator inputs."""
    frames = candump.read(log)
    t0 = frames[0].t
    c = conditions(frames, t0)
    return Scenario(
        name=name, description=f"Conditions and operator inputs replayed from {log.name}",
        ambient_c=c["ambient_c"] if c["ambient_c"] is not None else 20.0, batt_temp_c=c["battery_c"],
        duration_s=c["duration_s"], auto_cycle=False, vehicle_speed_mph=tuple(c["vehicle_speed_mph"]) or ((0.0, 0.0),),
        joy_script=tuple(c["joy_script"]), expect_cycle_complete=False, check_cycle_time=False)


def open_loop(frames: list[candump.LoggedFrame], variant: str, t0: float) -> list[tuple[float, int, bytes]]:
    """Feed logged controller inputs into the current firmware; return its outputs."""
    channel = f"replay-{uuid.uuid4().hex[:8]}"
    feed = can.Bus(interface="virtual", channel=channel, preserve_timestamps=True)
    ecu_bus = can.Bus(interface="virtual", channel=channel, preserve_timestamps=True)
    ecu = ControllerECU(variant, ecu_bus)
    out: list[tuple[float, int, bytes]] = []
    inputs = [f for f in frames if f.can_id not in CONTROLLER_TX_IDS and dbc.decode(f.can_id, f.data) is not None]
    steps = int((frames[-1].t - t0) / DT_S) + 1
    i = 0
    try:
        for k in range(steps):
            t = k * DT_S
            while i < len(inputs) and inputs[i].t - t0 < t + DT_S / 2:
                feed.send(can.Message(arbitration_id=inputs[i].can_id, is_extended_id=True, data=inputs[i].data,
                                      timestamp=inputs[i].t - t0))
                i += 1
            for m in ecu.step(t):
                out.append((round(t, 4), m.arbitration_id, bytes(m.data)))
    finally:
        feed.shutdown()
        ecu_bus.shutdown()
    return out


def compare(field: list[tuple[float, int, bytes]], sil: list[tuple[float, int, bytes]]) -> dict:
    def series(frames, name):
        fid = dbc.frame_id(name)
        return [(t, dbc.decode(i, d)[1]) for t, i, d in frames if i == fid]

    def dtc_events(frames):
        ev, last = [], None
        for t, s in series(frames, "DM1"):
            d = dbc.dm1_dtc(s)
            if d and d != last:
                ev.append((t, d))
            last = d
        return ev

    def cmd_at(seq, t):
        v = 0.0
        for ts, s in seq:
            if ts > t + 1e-6:
                break
            v = float(s["LiftVelocityCmd"])
        return v

    f_cmd, s_cmd = series(field, "ARM_CMD"), series(sil, "ARM_CMD")
    diverge = None
    for t, s in f_cmd:
        if abs(float(s["LiftVelocityCmd"]) - cmd_at(s_cmd, t)) > CMD_TOL_PCT:
            diverge = (t, float(s["LiftVelocityCmd"]), cmd_at(s_cmd, t))
            break
    return {"field_dtcs": dtc_events(field), "sil_dtcs": dtc_events(sil), "first_cmd_divergence": diverge}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", type=Path)
    ap.add_argument("--variant", required=True, choices=params_mod.variants())
    ap.add_argument("--viz", action="store_true", help="write field / open-loop / re-sim traces for viz/viewer.html")
    ap.add_argument("--plot", action="store_true", help="write PNG plots of the field log and the re-simulation")
    ap.add_argument("--out", type=Path, default=Path("out/replay"))
    args = ap.parse_args()

    frames = candump.read(args.log)
    t0 = frames[0].t
    prm = params_mod.load(args.variant)
    c = conditions(frames, t0)
    unknown = sorted({f.can_id for f in frames if dbc.decode(f.can_id, f.data) is None})
    print(f"log        {args.log}  ({len(frames)} frames, {c['duration_s']:.1f} s, "
          f"{datetime.fromtimestamp(t0, tz=timezone.utc):%Y-%m-%d %H:%M:%S} UTC)")
    print(f"variant    {args.variant} ({prm['hardware']['powertrain']})")
    amb = c["ambient_c"]
    print(f"conditions ambient {amb:.1f} degC ({amb * 9 / 5 + 32:.0f} degF)" if amb is not None else "conditions ambient n/a",
          f"| battery {c['battery_c']:.1f} degC" if c["battery_c"] is not None else "| no BATT_STATUS",
          f"| max speed {max((v for _, v in c['vehicle_speed_mph']), default=0):.1f} mph")
    if unknown:
        print(f"           {len(unknown)} frame IDs not in asl200.dbc ignored: " + " ".join(f"{u:08X}" for u in unknown[:6]))

    field = [(round(f.t - t0, 4), f.can_id, f.data) for f in frames if f.can_id in CONTROLLER_TX_IDS]
    sil_out = open_loop(frames, args.variant, t0)
    cmp = compare(field, sil_out)

    print("\n== open-loop replay (logged inputs -> current firmware) ==")
    for t, (spn, fmi, oc) in cmp["field_dtcs"]:
        print(f"  field  {utc(t0 + t)}  +{t:7.2f}s  " + describe(spn, fmi).splitlines()[0] + f" (OC {oc})")
    for t, (spn, fmi, oc) in cmp["sil_dtcs"]:
        print(f"  sil    {utc(t0 + t)}  +{t:7.2f}s  " + describe(spn, fmi).splitlines()[0] + f" (OC {oc})")
    if not cmp["sil_dtcs"]:
        print("  sil    no DTCs raised")
    d = cmp["first_cmd_divergence"]
    if d is None:
        print("  ARM_CMD: current firmware matches the field ECU for the whole log")
    else:
        print(f"  ARM_CMD: first divergence at +{d[0]:.2f}s (field lift cmd {d[1]:.1f} %, sil {d[2]:.1f} %)")
    f_keys = [(round(t, 1), x[:2]) for t, x in cmp["field_dtcs"]]
    s_keys = [(round(t, 1), x[:2]) for t, x in cmp["sil_dtcs"]]
    reproduced = bool(f_keys) and f_keys == s_keys
    print("  verdict: " + ("field DTCs REPRODUCED by current firmware" if reproduced else
                           "field DTCs not reproduced" if f_keys else "no DTCs in field log"))

    print("\n== closed-loop re-simulation (log conditions + operator inputs -> plant + firmware) ==")
    sc = scenario_from_log(args.log)
    resim = run(args.variant, sc)
    for e in resim["events"]:
        if e["type"] == "dtc":
            print(f"  +{e['t']:7.2f}s  " + e["text"])
    states = [STATE_NAMES[s] for s in sorted(set(resim["signals"]["state"]))]
    print(f"  peak lift {resim['summary']['peak_lift_deg']:.1f} deg, states visited: {', '.join(states)}")
    print("  verdict: " + (f"{len(resim['dtcs'])} DTC(s) raised in re-simulation" if resim["dtcs"] else
                           "no DTCs - cycles complete in re-simulation"))

    if args.viz or args.plot:
        stem = args.log.stem
        meta = {"variant": args.variant, "seed": None, "description": f"Field log {args.log.name}"}
        field_trace = trace_from_frames([(round(f.t - t0, 4), f.can_id, f.data) for f in frames], prm,
                                        {**meta, "scenario": f"{stem} (field)", "source": "field_log"})
        resim["meta"]["scenario"] = f"{stem} (SIL re-sim)"
        resim["meta"]["source"] = "sil_replay"
        paths = {"field": args.out / f"{stem}.field.trace.json", "resim": args.out / f"{stem}.resim.trace.json"}
        if args.viz:
            save_trace(field_trace, paths["field"])
            save_trace(resim, paths["resim"])
            (args.out / f"{stem}.replay.json").write_text(json.dumps({
                "log": str(args.log), "variant": args.variant,
                "field_dtcs": cmp["field_dtcs"], "sil_dtcs": cmp["sil_dtcs"], "reproduced": reproduced}, indent=1))
            print(f"\ntraces     {paths['field']}\n           {paths['resim']}")
            print("open viz/viewer.html and load both files for side-by-side playback")
        if args.plot:
            from sil.plots import plot_trace
            field_trace["passed"] = not field_trace["dtcs"]
            print("plots      " + str(plot_trace(field_trace, args.out / f"{stem}.field.png")))
            print("           " + str(plot_trace(resim, args.out / f"{stem}.resim.png")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
