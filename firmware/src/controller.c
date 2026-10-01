/*
 * ASL-200 arm cycle controller.
 *
 * Fixed-step (10 ms) state machine for the automated side-loader arm:
 *   IDLE -> REACH_OUT -> GRIP -> LIFT -> DUMP -> LOWER -> RELEASE -> RETRACT -> IDLE
 * with FAULT_STOP entered on any latched fault. In IDLE the operator can jog
 * the arm from the console; every motion request passes through the same
 * interlock, soft-limit and stall-monitor chain.
 */
#include <math.h>

#include "controller.h"
#include "faults.h"
#include "filters.h"
#include "interlocks.h"
#include "scaling.h"

#define POS_LPF_ALPHA        0.5f
#define LIFT_ARRIVE_DEG      1.5f
#define REACH_ARRIVE_MM      10.0f
#define HOME_LIFT_MAX_DEG    5.0f
#define HOME_REACH_MAX_MM    50.0f
#define REACH_RAMP_TIME_S    0.25f
#define CMD_PCT_MAX          100.0f
#define STOP_LOOKAHEAD_S     0.1f

typedef struct {
    float lift_dps;
    float reach_mmps;
} motion_req_t;

float motion_approach_velocity(float distance, float v_max, float v_creep, float decel_zone)
{
    float v = 0.0f;
    if (distance <= (v_creep * STOP_LOOKAHEAD_S)) {
        v = 0.0f;
    } else if (distance >= decel_zone) {
        v = v_max;
    } else {
        v = v_max * (distance / decel_zone);
        if (v < v_creep) {
            v = v_creep;
        }
    }
    return v;
}

void controller_init(state_t *s, const params_t *p)
{
    s->p = p;
    s->time_ms = 0U;
    s->state = ST_IDLE;
    s->lift_phase = LP_NONE;
    s->state_timer_ms = 0U;
    s->cycle_aborted = false;
    s->cycle_count = 0U;
    s->lift_deg = 0.0f;
    s->reach_mm = 0.0f;
    s->lift_filter_init = false;
    s->lift_cmd_dps = 0.0f;
    s->reach_cmd_mmps = 0.0f;
    s->grip_cmd = GRIP_HOLD;
    s->grip_secure_timer_ms = 0U;
    stall_monitor_reset(&s->lift_stall);
    stall_monitor_reset(&s->reach_stall);
    s->lift_sensor_open.timer_ms = 0U;
    s->lift_sensor_open.tripped = false;
    s->lift_sensor_short.timer_ms = 0U;
    s->lift_sensor_short.tripped = false;
    s->reach_sensor_open.timer_ms = 0U;
    s->reach_sensor_open.tripped = false;
    s->reach_sensor_short.timer_ms = 0U;
    s->reach_sensor_short.tripped = false;
    s->prev_auto_request = false;
    s->prev_fault_reset = false;
    faults_init(s);
}

static void enter_state(state_t *s, cycle_state_t next)
{
    s->state = next;
    s->state_timer_ms = 0U;
    s->lift_phase = (next == ST_LIFT) ? LP_CLEAR : LP_NONE;
}

static void enter_fault(state_t *s, uint32_t spn, uint8_t fmi)
{
    faults_raise(s, spn, fmi);
    if (s->state != ST_FAULT_STOP) {
        s->cycle_aborted = true;
        enter_state(s, ST_FAULT_STOP);
    }
}

/* Sensor diagnostics and scaling. Returns false if a position is unusable. */
static bool update_sensors(const inputs_t *in, state_t *s)
{
    const params_t *p = s->p;
    const uint32_t deb = (uint32_t)p->sensors.debounce_ms;
    const sensor_status_t lift_st = sensor_check_mv(in->lift_sensor_mv, p->sensors.lift.open_circuit_mv,
                                                    p->sensors.lift.short_circuit_mv);
    const sensor_status_t reach_st = sensor_check_mv(in->reach_sensor_mv, p->sensors.reach.open_circuit_mv,
                                                     p->sensors.reach.short_circuit_mv);
    bool ok = true;

    if (debounce_update(&s->lift_sensor_open, lift_st == SENSOR_OPEN_CIRCUIT, deb, CONTROLLER_STEP_MS)) {
        enter_fault(s, SPN_ARM_LIFT_POSITION_SENSOR, FMI_VOLTAGE_BELOW_NORMAL);
        ok = false;
    }
    if (debounce_update(&s->lift_sensor_short, lift_st == SENSOR_SHORT_CIRCUIT, deb, CONTROLLER_STEP_MS)) {
        enter_fault(s, SPN_ARM_LIFT_POSITION_SENSOR, FMI_VOLTAGE_ABOVE_NORMAL);
        ok = false;
    }
    if (debounce_update(&s->reach_sensor_open, reach_st == SENSOR_OPEN_CIRCUIT, deb, CONTROLLER_STEP_MS)) {
        enter_fault(s, SPN_ARM_REACH_POSITION_SENSOR, FMI_VOLTAGE_BELOW_NORMAL);
        ok = false;
    }
    if (debounce_update(&s->reach_sensor_short, reach_st == SENSOR_SHORT_CIRCUIT, deb, CONTROLLER_STEP_MS)) {
        enter_fault(s, SPN_ARM_REACH_POSITION_SENSOR, FMI_VOLTAGE_ABOVE_NORMAL);
        ok = false;
    }

    /* Hold the last good position while a reading is out of range. */
    if (lift_st == SENSOR_OK) {
        const float deg = scale_lift_mv_to_deg(in->lift_sensor_mv, &p->sensors.lift);
        const float mm = scale_reach_mv_to_mm(in->reach_sensor_mv, &p->sensors.reach);
        if (!s->lift_filter_init) {
            s->lift_deg = deg;
            s->reach_mm = mm;
            s->lift_filter_init = true;
        } else {
            s->lift_deg = lpf_first_order(s->lift_deg, deg, POS_LPF_ALPHA);
            if (reach_st == SENSOR_OK) {
                s->reach_mm = lpf_first_order(s->reach_mm, mm, POS_LPF_ALPHA);
            }
        }
    } else {
        ok = false;
    }
    if (reach_st != SENSOR_OK) {
        ok = false;
    }
    return ok;
}

static void step_jog(const inputs_t *in, state_t *s, motion_req_t *req)
{
    const params_t *p = s->p;
    req->lift_dps = ((float)in->jog_lift_pct / 100.0f) * p->motion.lift_speed_dps;
    req->reach_mmps = ((float)in->jog_reach_pct / 100.0f) * p->motion.reach_speed_mmps;
    if (in->grip_request == 1U) {
        s->grip_cmd = GRIP_CLOSE;
    } else if (in->grip_request == 2U) {
        s->grip_cmd = GRIP_OPEN;
    } else {
        s->grip_cmd = GRIP_HOLD;
    }
}

static void step_lift(state_t *s, bool secured, motion_req_t *req)
{
    const params_t *p = s->p;
    s->grip_cmd = GRIP_CLOSE;
    if (!secured) {
        /* Bin not held: put it back down. */
        s->cycle_aborted = true;
        enter_state(s, ST_LOWER);
    } else if (s->lift_phase == LP_CLEAR) {
        req->lift_dps = motion_approach_velocity(p->motion.lift_clear_deg - s->lift_deg, p->motion.lift_speed_dps,
                                                 p->motion.creep_speed_dps, p->motion.decel_zone_deg);
        if (s->lift_deg >= (p->motion.lift_clear_deg - LIFT_ARRIVE_DEG)) {
            s->lift_phase = LP_GRIP_RECHECK;
            s->state_timer_ms = 0U;
            req->lift_dps = 0.0f;
        }
    } else if (s->lift_phase == LP_GRIP_RECHECK) {
        req->lift_dps = 0.0f;
        if (s->state_timer_ms >= (uint32_t)p->motion.grip_recheck_ms) {
            s->lift_phase = LP_RAISE;
            s->state_timer_ms = 0U;
        }
    } else {
        req->lift_dps = motion_approach_velocity(p->motion.dump_angle_deg - s->lift_deg, p->motion.lift_speed_dps,
                                                 p->motion.creep_speed_dps, p->motion.decel_zone_deg);
        if (s->lift_deg >= (p->motion.dump_angle_deg - LIFT_ARRIVE_DEG)) {
            req->lift_dps = 0.0f;
            enter_state(s, ST_DUMP);
        }
    }
}

static void step_cycle(const inputs_t *in, state_t *s, bool secured, motion_req_t *req)
{
    const params_t *p = s->p;
    switch (s->state) {
    case ST_REACH_OUT:
        s->grip_cmd = GRIP_OPEN;
        req->reach_mmps = motion_approach_velocity(p->motion.reach_out_mm - s->reach_mm, p->motion.reach_speed_mmps,
                                                   p->motion.reach_creep_mmps, p->motion.reach_decel_zone_mm);
        if (s->reach_mm >= (p->motion.reach_out_mm - REACH_ARRIVE_MM)) {
            req->reach_mmps = 0.0f;
            enter_state(s, ST_GRIP);
        }
        break;
    case ST_GRIP:
        s->grip_cmd = GRIP_CLOSE;
        if (secured) {
            enter_state(s, ST_LIFT);
        } else if (s->state_timer_ms >= (uint32_t)p->interlocks.grip_timeout_ms) {
            s->cycle_aborted = true;
            enter_state(s, ST_RELEASE);
        } else {
            /* waiting for clamp pressure */
        }
        break;
    case ST_LIFT:
        step_lift(s, secured, req);
        break;
    case ST_DUMP:
        s->grip_cmd = GRIP_CLOSE;
        if (s->state_timer_ms >= (uint32_t)p->motion.dump_dwell_ms) {
            enter_state(s, ST_LOWER);
        }
        break;
    case ST_LOWER:
        s->grip_cmd = GRIP_CLOSE;
        req->lift_dps = -motion_approach_velocity(s->lift_deg, p->motion.lower_speed_dps, p->motion.creep_speed_dps,
                                                  p->motion.decel_zone_deg);
        if (s->lift_deg <= LIFT_ARRIVE_DEG) {
            req->lift_dps = 0.0f;
            enter_state(s, ST_RELEASE);
        }
        break;
    case ST_RELEASE:
        s->grip_cmd = GRIP_OPEN;
        if (s->state_timer_ms >= (uint32_t)p->motion.release_time_ms) {
            enter_state(s, ST_RETRACT);
        }
        break;
    case ST_RETRACT:
        s->grip_cmd = GRIP_OPEN;
        req->reach_mmps = -motion_approach_velocity(s->reach_mm - p->limits.reach_soft_min_mm,
                                                    p->motion.reach_speed_mmps, p->motion.reach_creep_mmps,
                                                    p->motion.reach_decel_zone_mm);
        if (s->reach_mm <= (p->limits.reach_soft_min_mm + REACH_ARRIVE_MM)) {
            req->reach_mmps = 0.0f;
            if (!s->cycle_aborted) {
                s->cycle_count++;
            }
            enter_state(s, ST_IDLE);
        }
        break;
    default:
        break;
    }
    (void)in;
}

void controller_step(const inputs_t *in, outputs_t *out, state_t *s)
{
    const params_t *p = s->p;
    const float dt_s = (float)CONTROLLER_STEP_MS / 1000.0f;
    motion_req_t req = { 0.0f, 0.0f };
    bool sensors_ok;
    bool speed_ok;
    bool tailgate_ok;
    bool batt_ok;
    bool secured;
    bool permitted;
    bool auto_rise;
    bool reset_rise;
    bool lift_limited = false;
    bool reach_limited = false;
    bool lift_stalled;
    bool reach_stalled;
    float lift_v;
    float reach_v;

    s->time_ms += CONTROLLER_STEP_MS;
    s->state_timer_ms += CONTROLLER_STEP_MS;
    s->dtc_changed = false;

    sensors_ok = update_sensors(in, s);
    speed_ok = interlock_vehicle_speed(in, p);
    tailgate_ok = interlock_tailgate(in, p);
    batt_ok = interlock_battery_temp(in, p);
    secured = interlock_grip_secured(in, p, &s->grip_secure_timer_ms, CONTROLLER_STEP_MS);
    permitted = speed_ok && tailgate_ok && batt_ok && sensors_ok;

    auto_rise = in->auto_cycle_request && !s->prev_auto_request;
    reset_rise = in->fault_reset && !s->prev_fault_reset;
    s->prev_auto_request = in->auto_cycle_request;
    s->prev_fault_reset = in->fault_reset;

    if (s->state == ST_FAULT_STOP) {
        s->grip_cmd = GRIP_HOLD;
        if (reset_rise && sensors_ok) {
            faults_init(s);
            s->dtc_changed = true;
            stall_monitor_reset(&s->lift_stall);
            stall_monitor_reset(&s->reach_stall);
            enter_state(s, ST_IDLE);
        }
    } else if (s->state == ST_IDLE) {
        if (auto_rise && permitted && (s->lift_deg < HOME_LIFT_MAX_DEG) && (s->reach_mm < HOME_REACH_MAX_MM)) {
            s->cycle_aborted = false;
            enter_state(s, ST_REACH_OUT);
            step_cycle(in, s, secured, &req);
        } else {
            step_jog(in, s, &req);
        }
    } else {
        step_cycle(in, s, secured, &req);
        if (!in->auto_cycle_request) {
            /* Operator released the auto-cycle switch: hold position. */
            req.lift_dps = 0.0f;
            req.reach_mmps = 0.0f;
        }
    }

    if ((s->state == ST_FAULT_STOP) || !permitted) {
        req.lift_dps = 0.0f;
        req.reach_mmps = 0.0f;
    }

    lift_v = rate_limit(s->lift_cmd_dps, req.lift_dps, p->motion.lift_accel_dps2 * dt_s);
    reach_v = rate_limit(s->reach_cmd_mmps, req.reach_mmps, (p->motion.reach_speed_mmps / REACH_RAMP_TIME_S) * dt_s);
    lift_v = interlock_soft_limit_lift(lift_v, s->lift_deg, p, &lift_limited);
    reach_v = interlock_soft_limit_reach(reach_v, s->reach_mm, p, &reach_limited);
    s->lift_cmd_dps = lift_v;
    s->reach_cmd_mmps = reach_v;

    out->lift_cmd_pct = clampf((lift_v / p->motion.lift_cmd_full_scale_dps) * 100.0f, -CMD_PCT_MAX, CMD_PCT_MAX);
    out->reach_cmd_pct = clampf((reach_v / p->motion.reach_cmd_full_scale_mmps) * 100.0f, -CMD_PCT_MAX, CMD_PCT_MAX);

    lift_stalled = stall_monitor_update(&s->lift_stall, fabsf(out->lift_cmd_pct) >= STALL_CMD_MIN_PCT, s->lift_deg,
                                        p->stall.stall_min_travel_deg, (uint32_t)p->stall.stall_timeout_ms,
                                        CONTROLLER_STEP_MS);
    reach_stalled = stall_monitor_update(&s->reach_stall, fabsf(out->reach_cmd_pct) >= STALL_CMD_MIN_PCT, s->reach_mm,
                                         p->stall.stall_min_travel_mm, (uint32_t)p->stall.stall_timeout_ms,
                                         CONTROLLER_STEP_MS);
    if (lift_stalled) {
        enter_fault(s, SPN_ARM_LIFT_ACTUATOR, FMI_MECHANICAL_NOT_RESPONDING);
    }
    if (reach_stalled) {
        enter_fault(s, SPN_ARM_REACH_ACTUATOR, FMI_MECHANICAL_NOT_RESPONDING);
    }
    if (s->state == ST_FAULT_STOP) {
        s->lift_cmd_dps = 0.0f;
        s->reach_cmd_mmps = 0.0f;
        out->lift_cmd_pct = 0.0f;
        out->reach_cmd_pct = 0.0f;
        s->grip_cmd = GRIP_HOLD;
    }

    out->grip_cmd = s->grip_cmd;
    out->state = s->state;
    out->lift_phase = s->lift_phase;
    out->ilk_vehicle_speed_ok = speed_ok;
    out->ilk_grip_secured = secured;
    out->ilk_tailgate_closed = tailgate_ok;
    out->soft_limit_active = lift_limited || reach_limited;
    out->stall_detected = lift_stalled || reach_stalled;
    out->lift_angle_deg = s->lift_deg;
    out->reach_mm = s->reach_mm;
    out->cycle_count = s->cycle_count;
    out->dtc_changed = s->dtc_changed;
}
