# I/O map

All body messages are J1939 29-bit, proprietary-B PGNs from source address 0x21 (body controller)
or the body I/O nodes. Standard PGNs are used where they exist. Source of truth: `can/asl200.dbc`.

## Inputs to the body controller

| Message (ID) | Signal | Scaling / units | Producer | Read by |
|---|---|---|---|---|
| CCVS 65265 (`18FEF100`) | WheelBasedVehicleSpeed | 1/256 km/h per bit, converted to mph | Engine ECU (SA 0x00), 100 ms | `can_io_rx()` → `inputs_t.vehicle_speed_mph`; `interlock_vehicle_speed()` |
| AMB 65269 (`18FEF500`) | AmbientAirTemperature | 0.03125 °C/bit, −273 offset | Engine ECU, 1 s | `inputs_t.ambient_c` (logged; diagnostics) |
| JOY_CMD (`18FF102C`) | AutoCycleRequest, FaultReset, JogLift, JogReach, GripRequest | bits; jog −100…100 % | Operator console (SA 0x2C), 50 ms | `step_cycle()`, `step_jog()`, fault reset in `controller_step()` |
| BODY_INPUTS (`18FF1180`) | TailgateOpen, HopperFull | bits | Arm I/O node (SA 0x80), 20 ms | `interlock_tailgate()` |
| BODY_INPUTS (`18FF1180`) | GripperPressure | 0.1 bar/bit | Arm I/O node | `interlock_grip_secured()` |
| ARM_SENSORS (`18FF1280`) | LiftSensorVoltage | 1 mV/bit, raw | Arm I/O node, 10 ms | `update_sensors()` → `scale_lift_mv_to_deg()`, `sensor_check_mv()` |
| ARM_SENSORS (`18FF1280`) | ReachSensorVoltage | 1 mV/bit, raw | Arm I/O node, 10 ms | `update_sensors()` → `scale_reach_mv_to_mm()`, `sensor_check_mv()` |
| ACTUATOR_STATUS (`18FF1381`) | LiftActuatorEffort, ActuatorTemperature | 0.1 bar or 0.1 A; °C | Actuator driver (SA 0x81), 20 ms | logged |
| BATT_STATUS (`18FF14E6`) | BatteryTemperature, StateOfCharge | 0.03125 °C/bit; 0.4 %/bit | BMS (SA 0xE6), 100 ms, electric only | `interlock_battery_temp()` |

A CCVS timeout (no frame for `ccvs_timeout_ms`) is treated as "vehicle speed unknown" and inhibits motion.

## Outputs from the body controller

| Message (ID) | Signal | Scaling / units | Period | Consumer |
|---|---|---|---|---|
| ARM_CMD (`18FF2021`) | LiftVelocityCmd, ReachVelocityCmd | 0.01 %/bit of actuator full scale, signed | 10 ms | Actuator driver |
| ARM_CMD | GripCmd | 0 hold, 1 close, 2 open | 10 ms | Actuator driver (gripper valve) |
| ARM_STATE (`18FF2121`) | CycleState, LiftPhase, Ilk* bits, SoftLimitActive, StallDetected, CycleCount | enums / bits | 100 ms | Cab display, telematics gateway |
| ARM_POSITION (`18FF2221`) | ArmLiftAngle, ArmReachPosition | 0.01 deg, 0.1 mm | 50 ms | Cab display, telematics gateway |
| DM1 65226 (`18FECA21`) | lamps, SPN, FMI, occurrence count | J1939-73 | 1 s, and on change | Cab display, service tool, telematics |

## Arm position sensors

| Sensor | Part number | Output | Calibration | Valid window (else DTC) |
|---|---|---|---|---|
| Lift angle | 55-1180-0 | 0–5 V ratiometric | 0 V = −20°, 5 V = 180° | 0.20–4.80 V (FMI 4 below / FMI 3 above) |
| Reach | 55-1192-0 (LR: 55-1193-0) | 0.5–4.5 V | 0.5 V = 0 mm, 4.5 V = 2000 mm (LR 2600 mm) | 0.40–4.60 V |

Calibration values live in `variants/common.yaml` (`controls.sensors`) and are compiled into `params_t`.
