"""Turn a sequence of bus frames (a field log, or a log-driven SIL run) into a
trace in the same format the SIL runner writes, so the viewer can show both."""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from . import dbc
from .runner import CONTROLLER_TX_IDS, DT_S, STATE_NAMES, TRACE_VERSION

KPH_PER_MPH = 1.609344


def _scale(mv: float, cal: dict, unit: str) -> float:
    lo, hi = cal[f"{unit}_at_v_lo"], cal[f"{unit}_at_v_hi"]
    return lo + (mv - cal["v_lo_mv"]) * (hi - lo) / (cal["v_hi_mv"] - cal["v_lo_mv"])


def trace_from_frames(frames: Iterable[tuple[float, int, bytes]], params: dict, meta: dict) -> dict:
    """frames: (t relative to log start [s], can_id, data), time-ordered."""
    frames = list(frames)
    end = frames[-1][0] if frames else 0.0
    n = int(end / DT_S) + 1
    cal_l = params["controls"]["sensors"]["lift"]
    cal_r = params["controls"]["sensors"]["reach"]
    cur = {"lift_deg": 0.0, "reach_mm": 0.0, "lift_cmd_pct": 0.0, "reach_cmd_pct": 0.0, "grip_cmd": 0,
           "grip_bar": 0.0, "state": 0, "lift_phase": 0, "speed_mph": 0.0, "tailgate_open": 0, "ilk_speed_ok": 0,
           "ilk_grip_secured": 0, "soft_limit_active": 0, "stall_detected": 0, "ctrl_lift_deg": 0.0, "lift_mv": 0,
           "auto_request": 0, "dtc_spn": 0, "effort": 0.0}
    names = ["t", "lift_deg", "lift_dps"] + [k for k in cur if k != "lift_deg"]
    sig: dict[str, list] = {k: [] for k in names}
    events, dtcs, out_frames = [], [], []
    ambient = None
    battery = None
    state = 0
    active = None
    hist: deque = deque(maxlen=6)
    i = 0
    for k in range(n):
        t = round(k * DT_S, 3)
        while i < len(frames) and frames[i][0] < t + DT_S:
            ft, fid, data = frames[i]
            i += 1
            out_frames.append([round(ft, 4), f"{fid:08X}", data.hex().upper(), "tx" if fid in CONTROLLER_TX_IDS else "rx"])
            dec = dbc.decode(fid, data)
            if dec is None:
                continue
            name, s = dec
            if name == "ARM_SENSORS":
                cur["lift_mv"] = int(s["LiftSensorVoltage"])
                cur["lift_deg"] = _scale(s["LiftSensorVoltage"], cal_l, "deg")
                cur["reach_mm"] = _scale(s["ReachSensorVoltage"], cal_r, "mm")
            elif name == "ARM_CMD":
                cur["lift_cmd_pct"] = float(s["LiftVelocityCmd"])
                cur["reach_cmd_pct"] = float(s["ReachVelocityCmd"])
                cur["grip_cmd"] = int(s["GripCmd"])
            elif name == "ARM_STATE":
                cur["state"] = int(s["CycleState"])
                cur["lift_phase"] = int(s["LiftPhase"])
                cur["ilk_speed_ok"] = int(s["IlkVehicleSpeedOk"])
                cur["ilk_grip_secured"] = int(s["IlkGripSecured"])
                cur["soft_limit_active"] = int(s["SoftLimitActive"])
                cur["stall_detected"] = int(s["StallDetected"])
            elif name == "ARM_POSITION":
                cur["ctrl_lift_deg"] = float(s["ArmLiftAngle"])
            elif name == "BODY_INPUTS":
                cur["grip_bar"] = float(s["GripperPressure"])
                cur["tailgate_open"] = int(s["TailgateOpen"])
            elif name == "JOY_CMD":
                cur["auto_request"] = int(s["AutoCycleRequest"])
            elif name == "CCVS":
                cur["speed_mph"] = round(float(s["WheelBasedVehicleSpeed"]) / KPH_PER_MPH, 2)
            elif name == "ACTUATOR_STATUS":
                cur["effort"] = float(s["LiftActuatorEffort"])
            elif name == "AMB":
                ambient = float(s["AmbientAirTemperature"])
            elif name == "BATT_STATUS":
                battery = float(s["BatteryTemperature"])
            elif name == "DM1":
                d = dbc.dm1_dtc(s)
                cur["dtc_spn"] = d[0] if d else 0
                if d and (active is None or active[:2] != d[:2]):
                    dtcs.append({"t": t, "spn": d[0], "fmi": d[1], "oc": d[2]})
                    events.append({"t": t, "type": "dtc", "text": f"DTC SPN {d[0]} FMI {d[1]} (OC {d[2]})"})
                active = d
        if cur["state"] != state:
            events.append({"t": t, "type": "state", "text": f"{STATE_NAMES[state]} -> {STATE_NAMES[cur['state']]}"})
            state = cur["state"]
        hist.append(cur["ctrl_lift_deg"])
        dps = (hist[-1] - hist[0]) / (DT_S * (len(hist) - 1)) if len(hist) > 1 else 0.0
        sig["t"].append(t)
        sig["lift_deg"].append(round(cur["lift_deg"], 3))
        sig["lift_dps"].append(round(dps, 2))
        for key in names[3:]:
            v = cur[key]
            sig[key].append(round(v, 3) if isinstance(v, float) else v)
    meta = {"dt_s": DT_S, "params": params, "state_names": STATE_NAMES, "ambient_c": ambient, "battery_c": battery,
            "powertrain": params["hardware"]["powertrain"],
            "effort_unit": "A" if params["hardware"]["powertrain"] == "electric" else "bar", "dbc": dbc.layout(), **meta}
    return {"version": TRACE_VERSION, "meta": meta, "signals": sig, "events": events, "dtcs": dtcs,
            "frames": out_frames,
            "summary": {"cycle_time_s": None, "final_state": STATE_NAMES[state],
                        "peak_lift_deg": max(sig["lift_deg"]) if sig["lift_deg"] else 0.0, "frames": len(out_frames)}}
