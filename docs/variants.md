# Variant matrix

Each variant file in `variants/` inherits `common.yaml` and overrides only what differs.
`controls:` is compiled into the firmware; `hardware:` is used only by the SIL plant model.

| | diesel_autocar | cng_peterbilt | electric_mack | diesel_mack_longreach |
|---|---|---|---|---|
| Chassis | diesel, cabover | CNG, conventional | battery-electric, low cab | diesel, low cab |
| Arm actuators | hydraulic (PTO pump) | hydraulic | electric (ePTO) | hydraulic, long-reach boom |
| Vehicle-speed interlock | 3.0 mph | 3.0 mph | 3.0 mph | **2.0 mph** |
| Reach out / soft max | 1500 / 1700 mm | 1500 / 1700 mm | 1500 / 1700 mm | 2100 / 2300 mm |
| Lift soft limits | −2…155° | −2…155° | −2…155° | −2…155° |
| Lift / lower speed | 92 / 104 °/s | 92 / 104 °/s | **80 / 81** °/s | 92 / 104 °/s |
| Reach speed | 1380 mm/s | 1380 mm/s | **1300** mm/s | 1380 mm/s |
| Lift accel limit (cmd) | 200 °/s² | 200 °/s² | **120** °/s² | 200 °/s² |
| Lift decel zone (soft limits) | 30° | 30° | **36°** | 30° |
| Lift / reach stop zone (auto-cycle) | 30° / 350 mm | 30° / 350 mm | **36° / 400 mm** | 30° / 350 mm |
| Battery temp interlock | n/a | n/a | 55 °C | n/a |
| Stall timeout | 400 ms | 400 ms | 400 ms | 400 ms |
| Cycle-time budget | 11.5 s | 11.5 s | 13.5 s | 12.5 s |

Notes

- The long-reach boom raises the overturning moment with the truck moving, so it inhibits arm motion
  at a lower road speed (`controls.interlocks.vehicle_speed_limit_mph`).
- The electric lift motor brakes regeneratively into the traction pack; its usable braking is lower
  than a hydraulic circuit's, hence the gentler accel limit and longer decel zone.
- The auto-cycle brakes into each target on a constant-deceleration profile over the stop zone
  (`*_stop_zone_*`, decel ≈ v²/2·zone); soft-limit approach keeps the linear decel-zone taper.
- The CNG chassis has a smaller PTO pump (`hardware.actuator.*_full_scale_*`).
