# Variant matrix

Each variant file in `variants/` inherits `common.yaml` and overrides only what differs.
`controls:` is compiled into the firmware; `hardware:` is used only by the SIL plant model.

| | diesel_autocar | cng_peterbilt | electric_mack | diesel_mack_longreach | diesel_autocar_legacy |
|---|---|---|---|---|
| Chassis | diesel, cabover | CNG, conventional | battery-electric, low cab | diesel, low cab | diesel, cabover |
| Arm actuators | hydraulic (PTO pump) | hydraulic | electric (ePTO) | hydraulic, long-reach boom | hydraulic (PTO pump) |
| Lift sensor | 55-1180-1 | 55-1180-1 | 55-1180-1 | 55-1180-1 | **55-1180-0** |
| Vehicle-speed interlock | 3.0 mph | 3.0 mph | 3.0 mph | **2.0 mph** | 3.0 mph |
| Reach out / soft max | 1500 / 1700 mm | 1500 / 1700 mm | 1500 / 1700 mm | 2100 / 2300 mm | 1500 / 1700 mm |
| Lift soft limits | −2…155° | −2…155° | −2…155° | −2…155° | −2…155° |
| Lift / lower speed | 80 / 90 °/s | 80 / 90 °/s | 80 / **70** °/s | 80 / 90 °/s | 80 / 90 °/s |
| Reach speed | 1200 mm/s | 1200 mm/s | **1000** mm/s | 1200 mm/s | 1200 mm/s |
| Lift accel limit (cmd) | 200 °/s² | 200 °/s² | **120** °/s² | 200 °/s² | 200 °/s² |
| Lift decel zone | 30° | 30° | **36°** | 30° | 30° |
| Battery temp interlock | n/a | n/a | 55 °C | n/a | n/a |
| Stall timeout | 400 ms | 400 ms | 400 ms | 400 ms | 400 ms |
| Cycle-time budget | 11.5 s | 11.5 s | 13.5 s | 12.5 s | 11.5 s |

Notes

- ECO-0412: post-break variants fit P/N 55-1180-1 (0.5–4.5 V); `asl200_diesel_autocar_legacy` is the
  pre-break build for bodies < ASL2-26-04100 with P/N 55-1180-0 (0–5 V ratiometric). `lift_sensor`
  selects the calibration from `variants/sensors.yaml`; do not flash a build configured for the
  wrong sensor revision onto a body.
- The long-reach boom raises the overturning moment with the truck moving, so it inhibits arm motion
  at a lower road speed (`controls.interlocks.vehicle_speed_limit_mph`).
- The electric lift motor brakes regeneratively into the traction pack; its usable braking is lower
  than a hydraulic circuit's, hence the gentler accel limit and longer decel zone.
- The CNG chassis has a smaller PTO pump (`hardware.actuator.*_full_scale_*`).
