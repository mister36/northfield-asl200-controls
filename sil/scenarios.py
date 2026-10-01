"""SIL scenario definitions.

A scenario is the world around the truck: weather, road speed, what the
operator does, and any injected hardware faults. The same scenario runs
against every variant; checks.py decides pass/fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SPN_LIFT_SENSOR = 520200
SPN_LIFT_ACTUATOR = 520210
FMI_VOLTAGE_BELOW_NORMAL = 4
FMI_MECHANICAL_NOT_RESPONDING = 7


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    ambient_c: float = 25.0
    batt_temp_c: float | None = None          # electric only; default tracks ambient
    duration_s: float = 22.0
    auto_cycle: bool = True                   # operator holds the auto-cycle switch
    auto_press_s: float = 0.5
    vehicle_speed_mph: tuple[tuple[float, float], ...] = ((0.0, 0.0),)  # (t, mph) steps
    jog: tuple[tuple[float, float, int, int], ...] = ()                  # (t0, t1, lift%, reach%)
    tailgate_open: tuple[tuple[float, float], ...] = ()
    lift_sensor_open_at_s: float | None = None
    gripper_max_bar: float | None = None      # gripper cannot build full clamp pressure
    lift_jam_above_deg: float | None = None   # lift axis seizes once past this angle
    expect_dtcs: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    expect_cycle_complete: bool = True
    check_cycle_time: bool = True
    expect_no_lift: bool = False
    variants: tuple[str, ...] | None = None   # None = every variant
    # Scripted operator console: (t, auto, reset, jog_lift%, jog_reach%, grip) steps.
    # When set, it replaces the built-in operator model (used for log replays).
    joy_script: tuple[tuple[float, int, int, int, int, int], ...] = ()

    def applies_to(self, variant: str) -> bool:
        return self.variants is None or variant in self.variants

    def speed_at(self, t: float) -> float:
        mph = 0.0
        for t0, v in self.vehicle_speed_mph:
            if t >= t0:
                mph = v
        return mph

    def joy_at(self, t: float) -> tuple[int, int, int, int, int]:
        cur = (0, 0, 0, 0, 0)
        for t0, *row in self.joy_script:
            if t >= t0:
                cur = tuple(row)
        return cur

    def jog_at(self, t: float) -> tuple[int, int]:
        if self.joy_script:
            _, _, lift, reach, _ = self.joy_at(t)
            return lift, reach
        for t0, t1, lift, reach in self.jog:
            if t0 <= t < t1:
                return lift, reach
        return 0, 0

    def tailgate_at(self, t: float) -> bool:
        return any(t0 <= t < t1 for t0, t1 in self.tailgate_open)

    def battery_temp(self) -> float:
        return self.batt_temp_c if self.batt_temp_c is not None else self.ambient_c + 2.0


SCENARIOS: dict[str, Scenario] = {s.name: s for s in [
    Scenario("normal", "Standard pick at 77F, truck stationary"),
    Scenario("cold", "Cold start at -4F (-20C), first pick of the shift",
             ambient_c=f_to_c(-4.0), batt_temp_c=-18.0, check_cycle_time=False,
             variants=("asl200_diesel_autocar", "asl200_cng_peterbilt", "asl200_diesel_mack_longreach")),
    Scenario("hot", "110F afternoon, hot hydraulic oil / warm pack",
             ambient_c=f_to_c(110.0), batt_temp_c=45.0),
    Scenario("arm_at_limit", "Operator jogs lift into the upper soft limit, then back down",
             auto_cycle=False, duration_s=9.0, jog=((0.5, 5.0, 100, 0), (5.5, 8.5, -100, 0)),
             expect_cycle_complete=False, check_cycle_time=False),
    Scenario("sensor_dropout", "Lift position sensor connector drops out mid-lift",
             lift_sensor_open_at_s=5.0, duration_s=10.0,
             expect_dtcs=frozenset({(SPN_LIFT_SENSOR, FMI_VOLTAGE_BELOW_NORMAL)}),
             expect_cycle_complete=False, check_cycle_time=False),
    Scenario("gripper_not_closed", "Can mis-positioned: gripper never reaches clamp pressure",
             gripper_max_bar=45.0, expect_cycle_complete=False, check_cycle_time=False,
             expect_no_lift=True),
    Scenario("vehicle_moving", "Operator requests cycle while rolling at 5 mph; truck stops, then creeps at 2.5 mph mid-cycle",
             vehicle_speed_mph=((0.0, 5.0), (2.0, 0.0), (6.0, 2.5), (8.0, 0.0)), duration_s=26.0,
             check_cycle_time=False),
    Scenario("lift_jam", "Lift cylinder seizes at 90 deg; controller must detect the stall",
             lift_jam_above_deg=90.0, duration_s=12.0,
             expect_dtcs=frozenset({(SPN_LIFT_ACTUATOR, FMI_MECHANICAL_NOT_RESPONDING)}),
             expect_cycle_complete=False, check_cycle_time=False),
]}
