#ifndef INTERLOCKS_H
#define INTERLOCKS_H

#include "asl200_types.h"

#define STALL_CMD_MIN_PCT 5.0f

/* All interlock_* functions return true when motion is PERMITTED. */
bool interlock_vehicle_speed(const inputs_t *in, const params_t *p);
bool interlock_tailgate(const inputs_t *in, const params_t *p);
bool interlock_battery_temp(const inputs_t *in, const params_t *p);
bool interlock_grip_secured(const inputs_t *in, const params_t *p,
                            uint32_t *secure_timer_ms, uint32_t dt_ms);

/* Clamp a lift/reach velocity request so the axis decelerates into its soft
 * limits. Sets *active when the clamp is limiting the request. */
float interlock_soft_limit_lift(float v_dps, float pos_deg, const params_t *p, bool *active);
float interlock_soft_limit_reach(float v_mmps, float pos_mm, const params_t *p, bool *active);

/* Stall detection: returns true when motion has been commanded but the
 * measured position has moved less than min_travel for timeout_ms. Until the
 * axis first moves after the command starts, start_allowance_ms is added to
 * the timeout (actuator brake release / start latency). */
void stall_monitor_reset(stall_monitor_t *m);
bool stall_monitor_update(stall_monitor_t *m, bool commanded, float pos, float min_travel,
                          uint32_t timeout_ms, uint32_t start_allowance_ms, uint32_t dt_ms);

/* Extra stall time allowed for an axis to start moving from rest, from the
 * traction-pack temperature (0 without a valid BATT_STATUS). */
uint32_t stall_start_allowance_ms(const inputs_t *in, const params_t *p);

#endif /* INTERLOCKS_H */
