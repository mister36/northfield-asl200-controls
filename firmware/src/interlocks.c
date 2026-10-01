/*
 * Arm-motion interlocks for the ASL-200 body controller.
 * Each interlock returns true when arm motion is permitted.
 */
#include <math.h>

#include "interlocks.h"
#include "controller.h"
#include "scaling.h"

bool interlock_vehicle_speed(const inputs_t *in, const params_t *p)
{
    const float limit_kph = p->interlocks.vehicle_speed_limit_mph * KPH_PER_MPH;
    bool ok = true;
    if (in->ccvs_age_ms > (uint32_t)p->interlocks.ccvs_timeout_ms) {
        ok = false; /* no valid road speed: fail safe */
    } else if (in->vehicle_speed_kph > limit_kph) {
        ok = false;
    } else {
        ok = true;
    }
    return ok;
}

bool interlock_tailgate(const inputs_t *in, const params_t *p)
{
    return !(p->interlocks.tailgate_inhibit && in->tailgate_open);
}

bool interlock_battery_temp(const inputs_t *in, const params_t *p)
{
    return !(in->batt_valid && (in->batt_temp_c > p->interlocks.batt_temp_max_c));
}

bool interlock_grip_secured(const inputs_t *in, const params_t *p,
                            uint32_t *secure_timer_ms, uint32_t dt_ms)
{
    if (in->gripper_pressure_bar >= p->interlocks.grip_secure_pressure_bar) {
        if (*secure_timer_ms < (uint32_t)p->interlocks.grip_secure_time_ms) {
            *secure_timer_ms += dt_ms;
        }
    } else {
        *secure_timer_ms = 0U;
    }
    return *secure_timer_ms >= (uint32_t)p->interlocks.grip_secure_time_ms;
}

float interlock_soft_limit_lift(float v_dps, float pos_deg, const params_t *p, bool *active)
{
    float v = v_dps;
    float allowed;
    *active = false;
    if (v > 0.0f) {
        allowed = motion_approach_velocity(p->limits.lift_soft_max_deg - pos_deg, p->motion.lift_speed_dps,
                                           p->motion.creep_speed_dps, p->motion.decel_zone_deg);
        if (allowed < v) {
            v = allowed;
            *active = true;
        }
    } else if (v < 0.0f) {
        allowed = motion_approach_velocity(pos_deg - p->limits.lift_soft_min_deg, p->motion.lower_speed_dps,
                                           p->motion.creep_speed_dps, p->motion.decel_zone_deg);
        if (allowed < -v) {
            v = -allowed;
            *active = true;
        }
    } else {
        v = 0.0f;
    }
    return v;
}

float interlock_soft_limit_reach(float v_mmps, float pos_mm, const params_t *p, bool *active)
{
    float v = v_mmps;
    float allowed;
    *active = false;
    if (v > 0.0f) {
        allowed = motion_approach_velocity(p->limits.reach_soft_max_mm - pos_mm, p->motion.reach_speed_mmps,
                                           p->motion.reach_creep_mmps, p->motion.reach_decel_zone_mm);
        if (allowed < v) {
            v = allowed;
            *active = true;
        }
    } else if (v < 0.0f) {
        allowed = motion_approach_velocity(pos_mm - p->limits.reach_soft_min_mm, p->motion.reach_speed_mmps,
                                           p->motion.reach_creep_mmps, p->motion.reach_decel_zone_mm);
        if (allowed < -v) {
            v = -allowed;
            *active = true;
        }
    } else {
        v = 0.0f;
    }
    return v;
}

void stall_monitor_reset(stall_monitor_t *m)
{
    m->armed = false;
    m->moved = false;
    m->timer_ms = 0U;
    m->ref_pos = 0.0f;
}

bool stall_monitor_update(stall_monitor_t *m, bool commanded, float pos, float min_travel,
                          uint32_t timeout_ms, uint32_t start_allowance_ms, uint32_t dt_ms)
{
    bool stalled = false;
    if (!commanded) {
        stall_monitor_reset(m);
    } else if (!m->armed) {
        m->armed = true;
        m->moved = false;
        m->ref_pos = pos;
        m->timer_ms = 0U;
    } else if (fabsf(pos - m->ref_pos) >= min_travel) {
        m->moved = true;
        m->ref_pos = pos;
        m->timer_ms = 0U;
    } else {
        const uint32_t limit_ms = m->moved ? timeout_ms : (timeout_ms + start_allowance_ms);
        m->timer_ms += dt_ms;
        stalled = m->timer_ms >= limit_ms;
    }
    return stalled;
}

uint32_t stall_start_allowance_ms(const inputs_t *in, const params_t *p)
{
    const float full_c = p->stall.cold_start_full_c;
    const float min_c = p->stall.cold_start_min_c;
    const float max_ms = (float)p->stall.cold_start_allowance_ms;
    float frac = 0.0f;
    if (!in->batt_valid || (max_ms <= 0.0f) || (in->batt_temp_c >= full_c)) {
        frac = 0.0f;
    } else if ((in->batt_temp_c <= min_c) || (full_c <= min_c)) {
        frac = 1.0f;
    } else {
        frac = (full_c - in->batt_temp_c) / (full_c - min_c);
    }
    return (uint32_t)((frac * max_ms) + 0.5f);
}
