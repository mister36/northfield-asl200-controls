# Variant matrix

Each variant file in `variants/` inherits `common.yaml` and overrides only what differs.
ECO-0412 files inherit their chassis variant, which in turn inherits `common.yaml`.
`controls:` is compiled into the firmware; `hardware:` is used only by the SIL plant model.

| | diesel_autocar | cng_peterbilt | electric_mack | diesel_mack_longreach |
|---|---|---|---|---|
| Chassis | diesel, cabover | CNG, conventional | battery-electric, low cab | diesel, low cab |
| Arm actuators | hydraulic (PTO pump) | hydraulic | electric (ePTO) | hydraulic, long-reach boom |
| Vehicle-speed interlock | 3.0 mph | 3.0 mph | 3.0 mph | **2.0 mph** |
| Reach out / soft max | 1500 / 1700 mm | 1500 / 1700 mm | 1500 / 1700 mm | 2100 / 2300 mm |
| Lift soft limits | −2…155° | −2…155° | −2…155° | −2…155° |
| Lift / lower speed | 80 / 90 °/s | 80 / 90 °/s | 80 / **70** °/s | 80 / 90 °/s |
| Reach speed | 1200 mm/s | 1200 mm/s | **1000** mm/s | 1200 mm/s |
| Lift accel limit (cmd) | 200 °/s² | 200 °/s² | **120** °/s² | 200 °/s² |
| Lift decel zone | 30° | 30° | **36°** | 30° |
| Battery temp interlock | n/a | n/a | 55 °C | n/a |
| Stall timeout | 400 ms | 400 ms | 400 ms | 400 ms |
| Cycle-time budget | 11.5 s | 11.5 s | 13.5 s | 12.5 s |

Notes

- The long-reach boom raises the overturning moment with the truck moving, so it inhibits arm motion
  at a lower road speed (`controls.interlocks.vehicle_speed_limit_mph`).
- The electric lift motor brakes regeneratively into the traction pack; its usable braking is lower
  than a hydraulic circuit's, hence the gentler accel limit and longer decel zone.
- The CNG chassis has a smaller PTO pump (`hardware.actuator.*_full_scale_*`).

## Lift sensor effectivity (ECO-0412)

| Body / installed sensor | Variant selection |
|---|---|
| Through ASL2-26-04099, 55-1180-0 (including WIP) | Existing chassis variant above |
| ASL2-26-04100 onward, 55-1180-1 | Same chassis variant with `_eco0412` suffix |
| Earlier body retrofitted with 55-1180-1 | Same chassis variant with `_eco0412` suffix |

The four ECO builds change only lift transfer endpoints (500/4500 mV), identify
55-1180-1 in the hardware blob, and explicitly use the ECO diagnostic thresholds
(250/4750 mV). Angle endpoints stay −20/180°. All chassis tuning and reach parameters
are inherited. Both sensor families run every applicable scenario in CI.
Firmware does not receive the body serial or detect the sensor family over CAN;
manufacturing/service must select the image from the installed sensor and chassis.
See [release notes](release-notes/ECO-0412.md).
