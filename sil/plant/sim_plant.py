"""Deterministic plant model of the ASL-200 arm, truck and operator console.

Deliberately simple: each axis is a velocity-commanded actuator with a dead
time, first-order lag and acceleration limits. Hydraulic and electric
actuators differ in how they start, stop and respond to temperature.
All randomness (sensor noise) comes from a seeded RNG.
"""
from __future__ import annotations

import random
from collections import deque

import can

from .. import dbc
from ..scenarios import Scenario
from .interface import PlantInterface

SUBSTEPS = 10
KPH_PER_MPH = 1.609344


def _lerp_clamped(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x <= x0:
        return y0
    if x >= x1:
        return y1
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


class Axis:
    """One arm axis driven by a velocity-commanded actuator."""

    def __init__(self, hw: dict, axis: str, powertrain: str, scenario: Scenario):
        act = hw["actuator"]
        self.electric = powertrain == "electric"
        self.full_scale = act["lift_full_scale_dps"] if axis == "lift" else act["reach_full_scale_mmps"]
        self.tau = (act["lift_tau_ms"] if axis == "lift" else act["reach_tau_ms"]) / 1000.0
        self.accel = act["lift_accel_limit_dps2"] if axis == "lift" else act["reach_accel_limit_mmps2"]
        self.axis = axis
        cold = scenario.ambient_c < 0.0
        hot = scenario.ambient_c > 35.0
        if self.electric:
            batt = scenario.battery_temp()
            self.derate = _lerp_clamped(batt, act["derate_min_c"], act["derate_full_c"],
                                        act["derate_min_factor"], 1.0)
            self.rate_factor = 1.0
            self.regen_power = 0.0 if axis != "lift" else act.get("regen_power_dps3", 0.0) * (act.get("regen_hot_factor", 1.0) if batt > 40.0 else 1.0)
            self.brake_engage = act["brake_engage_ms"] / 1000.0
            self.brake_release = act["brake_release_ms"] / 1000.0
            self.prove_loaded = act["torque_prove_loaded_ms"] / 1000.0
            self.prove_unloaded = act["torque_prove_unloaded_ms"] / 1000.0
        else:
            self.derate = 1.0
            self.rate_factor = act["cold_rate_factor"] if cold else (1.03 if hot else 1.0)
            self.onset = (act["cold_onset_delay_ms"] if cold else act["onset_delay_ms"]) / 1000.0
        self.pos = 0.0
        self.vel = 0.0
        self.mode = "stopped"   # stopped -> starting -> running
        self.timer = 0.0
        self.idle_time = 0.0
        self.jammed = False

    def start_delay(self, loaded: bool, raising: bool) -> float:
        if not self.electric:
            return self.onset
        # Holding torque must be proven before the brake releases under a raised load.
        prove = self.prove_loaded if (loaded and raising and self.axis == "lift") else self.prove_unloaded
        return self.brake_release + prove / self.derate

    def step(self, cmd_pct: float, loaded: bool, dt: float) -> None:
        commanded = abs(cmd_pct) >= 0.5
        if self.mode == "stopped":
            if commanded:
                self.mode = "starting"
                self.timer = self.start_delay(loaded, cmd_pct > 0.0)
        elif self.mode == "starting":
            if not commanded:
                self.mode = "stopped"
            else:
                self.timer -= dt
                if self.timer <= 0.0:
                    self.mode = "running"
                    self.idle_time = 0.0
        else:
            hold = self.brake_engage if self.electric else 0.05
            if not commanded and abs(self.vel) < 0.5:
                self.idle_time += dt
                if self.idle_time >= hold:
                    self.mode = "stopped"
                    self.vel = 0.0
            else:
                self.idle_time = 0.0

        target = 0.0
        if self.mode == "running":
            target = cmd_pct / 100.0 * self.full_scale * self.rate_factor
        dv = (target - self.vel) * min(1.0, dt / self.tau)
        speeding_up = abs(target) > abs(self.vel) and (target * self.vel >= 0.0)
        limit = self.accel
        if self.electric and speeding_up:
            limit *= max(self.derate, 0.5)
        if self.electric and not speeding_up and self.regen_power > 0.0 and abs(self.vel) > 1e-3:
            limit = min(limit, self.regen_power / abs(self.vel))
        dv = max(-limit * dt, min(limit * dt, dv))
        if self.mode == "stopped":
            self.vel = 0.0
        else:
            self.vel += dv
        if self.jammed:
            self.vel = 0.0
        self.pos += self.vel * dt


class SimPlant(PlantInterface):
    def __init__(self, params: dict, scenario: Scenario, seed: int):
        self.params = params
        self.hw = params["hardware"]
        self.scenario = scenario
        self.rng = random.Random(seed)
        self.powertrain = self.hw["powertrain"]
        self.lift = Axis(self.hw, "lift", self.powertrain, scenario)
        self.reach = Axis(self.hw, "reach", self.powertrain, scenario)
        self.bus: can.BusABC | None = None
        self.cmd = {"LiftVelocityCmd": 0.0, "ReachVelocityCmd": 0.0, "GripCmd": 0}
        self.ctrl_state: dict = {}
        self.ctrl_pos: dict = {}
        self.dtcs: dict[tuple[int, int], int] = {}
        self.dm1_active: tuple[int, int] | None = None
        self.grip_bar = 0.0
        self.gripped = False
        lat = self.hw["sensors"]["lift"]["latency_ms"] // 10
        self._lift_hist: deque = deque([0.0] * (lat + 1), maxlen=lat + 1)
        lat_r = self.hw["sensors"]["reach"]["latency_ms"] // 10
        self._reach_hist: deque = deque([0.0] * (lat_r + 1), maxlen=lat_r + 1)
        self.lift_mv = 0
        self.reach_mv = 0
        # operator model
        self.auto_held = False
        self.cycle_started = False
        self.cycle_done = False
        self.release_until = 0.0
        self.idle_since: float | None = None
        self.fault_reset = False
        self.t = 0.0

    # --- PlantInterface -------------------------------------------------
    def attach(self, bus: can.BusABC) -> None:
        self.bus = bus

    def truth(self) -> dict:
        return {
            "lift_deg": self.lift.pos, "lift_dps": self.lift.vel,
            "reach_mm": self.reach.pos, "reach_mmps": self.reach.vel,
            "grip_bar": self.grip_bar, "gripped": self.gripped,
            "speed_mph": self.scenario.speed_at(self.t),
            "tailgate_open": self.scenario.tailgate_at(self.t),
            "lift_mv": self.lift_mv, "reach_mv": self.reach_mv,
            "auto_request": self.auto_held,
            "lift_actuator": self.lift.mode,
            "effort": self._effort(),
        }

    def tick(self, t_s: float, dt_s: float) -> list[can.Message]:
        self.t = t_s
        self._receive()
        self._operator(t_s)
        self._physics(dt_s)
        return self._transmit(t_s)

    # --- internals ------------------------------------------------------
    def _receive(self) -> None:
        assert self.bus is not None
        while True:
            msg = self.bus.recv(timeout=0)
            if msg is None:
                break
            decoded = dbc.decode(msg.arbitration_id, msg.data)
            if decoded is None:
                continue
            name, sig = decoded
            if name == "ARM_CMD":
                self.cmd = sig
            elif name == "ARM_STATE":
                self.ctrl_state = sig
            elif name == "ARM_POSITION":
                self.ctrl_pos = sig
            elif name == "DM1":
                d = dbc.dm1_dtc(sig)
                self.dm1_active = None if d is None else (d[0], d[1])
                if d is not None:
                    self.dtcs[(d[0], d[1])] = d[2]

    def _operator(self, t: float) -> None:
        sc = self.scenario
        self.fault_reset = False
        if sc.joy_script:
            auto, reset, _, _, _ = sc.joy_at(t)
            self.auto_held = bool(auto)
            self.fault_reset = bool(reset)
            return
        if not sc.auto_cycle or self.cycle_done:
            self.auto_held = False
            return
        state = int(self.ctrl_state.get("CycleState", 0))
        if t < sc.auto_press_s or t < self.release_until:
            self.auto_held = False
            return
        if state == 8:
            self.cycle_done = True
            self.auto_held = False
            return
        if state != 0:
            self.cycle_started = True
            self.idle_since = None
        elif self.cycle_started:
            self.cycle_done = True
            self.auto_held = False
            return
        elif self.auto_held:
            # Cycle refused (e.g. interlock): let go and try again shortly.
            if self.idle_since is None:
                self.idle_since = t
            elif t - self.idle_since > 1.0:
                self.auto_held = False
                self.release_until = t + 0.3
                self.idle_since = None
                return
        self.auto_held = True

    def _physics(self, dt: float) -> None:
        sc = self.scenario
        h = dt / SUBSTEPS
        arm = self.hw["arm"]
        act = self.hw["actuator"]
        clamp_bar = act["gripper_clamp_bar"]
        if sc.gripper_max_bar is not None:
            clamp_bar = min(clamp_bar, sc.gripper_max_bar)
        rate = act["gripper_rate_bar_per_s"]
        reach_target = self.params["controls"]["motion"]["reach_out_mm"]
        at_can = abs(self.reach.pos - reach_target) < 100.0
        for _ in range(SUBSTEPS):
            loaded = self.gripped and self.lift.pos > 3.0
            if sc.lift_jam_above_deg is not None and self.lift.pos >= sc.lift_jam_above_deg:
                self.lift.jammed = True
            self.lift.step(float(self.cmd["LiftVelocityCmd"]), loaded, h)
            self.reach.step(float(self.cmd["ReachVelocityCmd"]), False, h)
            for ax, lo, hi in ((self.lift, arm["lift_hard_min_deg"], arm["lift_hard_max_deg"]),
                               (self.reach, 0.0, arm["reach_hard_max_mm"])):
                if ax.pos < lo:
                    ax.pos, ax.vel = lo, 0.0
                elif ax.pos > hi:
                    ax.pos, ax.vel = hi, 0.0
            grip = int(self.cmd["GripCmd"])
            if grip == 1 and (at_can or self.gripped):
                self.grip_bar = min(clamp_bar, self.grip_bar + rate * h)
            elif grip == 2:
                self.grip_bar = max(0.0, self.grip_bar - 2.0 * rate * h)
        self.gripped = self.grip_bar > 60.0

        cal_l = self.hw["sensors"]["lift"]
        cal_r = self.hw["sensors"]["reach"]
        self._lift_hist.append(self.lift.pos)
        self._reach_hist.append(self.reach.pos)
        self.lift_mv = self._to_mv(self._lift_hist[0], cal_l, "deg")
        self.reach_mv = self._to_mv(self._reach_hist[0], cal_r, "mm")
        if sc.lift_sensor_open_at_s is not None and self.t >= sc.lift_sensor_open_at_s:
            self.lift_mv = max(0, int(round(abs(self.rng.gauss(12.0, 4.0)))))

    def _to_mv(self, value: float, cal: dict, unit: str) -> int:
        lo, hi = cal[f"{unit}_at_v_lo"], cal[f"{unit}_at_v_hi"]
        mv = cal["v_lo_mv"] + (value - lo) / (hi - lo) * (cal["v_hi_mv"] - cal["v_lo_mv"])
        mv += self.rng.gauss(0.0, cal["noise_mv"])
        return int(max(0, min(5000, round(mv))))

    def _effort(self) -> float:
        frac = abs(self.lift.vel) / self.lift.full_scale
        load = 1.0 if (self.gripped and self.lift.pos > 3.0) else 0.0
        if self.powertrain == "electric":
            return 15.0 + 110.0 * frac + 55.0 * load
        return 25.0 + 90.0 * frac + 45.0 * load

    def _transmit(self, t: float) -> list[can.Message]:
        sc = self.scenario
        ms = int(round(t * 1000.0))
        out: list[tuple[str, dict]] = [
            ("ARM_SENSORS", {"LiftSensorVoltage": self.lift_mv, "ReachSensorVoltage": self.reach_mv}),
        ]
        if ms % 20 == 0:
            lift_j, reach_j = sc.jog_at(t)
            out.append(("JOY_CMD", {"AutoCycleRequest": int(self.auto_held), "FaultReset": int(self.fault_reset),
                                    "JogLift": lift_j, "JogReach": reach_j,
                                    "GripRequest": sc.joy_at(t)[4] if sc.joy_script else 0}))
            out.append(("BODY_INPUTS", {"TailgateOpen": int(sc.tailgate_at(t)), "HopperFull": 0,
                                        "GripperPressure": round(self.grip_bar + self.rng.gauss(0.0, 0.3), 1)
                                        if self.grip_bar > 0.5 else 0.0}))
            out.append(("ACTUATOR_STATUS", {"LiftActuatorEffort": round(self._effort(), 1),
                                            "ActuatorTemperature": sc.ambient_c + 5.0}))
        if ms % 100 == 0:
            out.append(("CCVS", {"WheelBasedVehicleSpeed": sc.speed_at(t) * KPH_PER_MPH}))
            if self.powertrain == "electric":
                out.append(("BATT_STATUS", {"BatteryTemperature": sc.battery_temp(), "StateOfCharge": 78.0}))
        if ms % 1000 == 0:
            out.append(("AMB", {"AmbientAirTemperature": sc.ambient_c}))
        sent = []
        for name, sig in out:
            msg = can.Message(arbitration_id=dbc.frame_id(name), is_extended_id=True,
                              data=dbc.encode(name, sig), timestamp=t)
            assert self.bus is not None
            self.bus.send(msg)
            sent.append(msg)
        return sent
