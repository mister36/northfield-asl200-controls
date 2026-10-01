/*
 * ASL-200 automated side-loader body controller - shared types.
 * Northfield Body Works (fictional). C99, no dynamic allocation.
 */
#ifndef ASL200_TYPES_H
#define ASL200_TYPES_H

#include <stdbool.h>
#include <stdint.h>

#include "params_types.h"

#define CONTROLLER_STEP_MS   10U
#define DTC_TABLE_SIZE       8U

typedef enum {
    ST_IDLE = 0,
    ST_REACH_OUT = 1,
    ST_GRIP = 2,
    ST_LIFT = 3,
    ST_DUMP = 4,
    ST_LOWER = 5,
    ST_RELEASE = 6,
    ST_RETRACT = 7,
    ST_FAULT_STOP = 8
} cycle_state_t;

typedef enum {
    LP_NONE = 0,
    LP_CLEAR = 1,
    LP_GRIP_RECHECK = 2,
    LP_RAISE = 3
} lift_phase_t;

typedef enum {
    GRIP_HOLD = 0,
    GRIP_CLOSE = 1,
    GRIP_OPEN = 2
} grip_cmd_t;

/* Decoded controller inputs. Filled by can_io_rx() from received frames. */
typedef struct {
    /* CCVS (PGN 65265) */
    float vehicle_speed_kph;
    uint32_t ccvs_age_ms;
    /* AMB (PGN 65269) */
    float ambient_temp_c;
    /* BATT_STATUS (electric variant only) */
    float batt_temp_c;
    bool batt_valid;
    /* ARM_SENSORS: raw ratiometric voltages */
    uint16_t lift_sensor_mv;
    uint16_t reach_sensor_mv;
    /* BODY_INPUTS */
    float gripper_pressure_bar;
    bool tailgate_open;
    /* JOY_CMD */
    bool auto_cycle_request;
    bool fault_reset;
    int8_t jog_lift_pct;
    int8_t jog_reach_pct;
    uint8_t grip_request;
    /* ACTUATOR_STATUS */
    float lift_effort;
} inputs_t;

typedef struct {
    uint32_t spn;
    uint8_t fmi;
    uint8_t occurrence;
    bool active;
} dtc_t;

typedef struct {
    float lift_cmd_pct;
    float reach_cmd_pct;
    grip_cmd_t grip_cmd;
    cycle_state_t state;
    lift_phase_t lift_phase;
    bool ilk_vehicle_speed_ok;
    bool ilk_grip_secured;
    bool ilk_tailgate_closed;
    bool soft_limit_active;
    bool stall_detected;
    float lift_angle_deg;
    float reach_mm;
    uint16_t cycle_count;
    bool dtc_changed;
} outputs_t;

typedef struct {
    float ref_pos;
    uint32_t timer_ms;
    bool armed;
} stall_monitor_t;

typedef struct {
    uint32_t timer_ms;
    bool tripped;
} debounce_t;

typedef struct {
    const params_t *p;
    uint32_t time_ms;
    cycle_state_t state;
    lift_phase_t lift_phase;
    uint32_t state_timer_ms;
    bool cycle_aborted;
    uint16_t cycle_count;

    float lift_deg;
    float reach_mm;
    bool lift_filter_init;

    float lift_cmd_dps;
    float reach_cmd_mmps;
    grip_cmd_t grip_cmd;

    uint32_t grip_secure_timer_ms;
    stall_monitor_t lift_stall;
    stall_monitor_t reach_stall;
    debounce_t lift_sensor_open;
    debounce_t lift_sensor_short;
    debounce_t reach_sensor_open;
    debounce_t reach_sensor_short;

    bool prev_auto_request;
    bool prev_fault_reset;

    dtc_t dtcs[DTC_TABLE_SIZE];
    bool dtc_changed;
} state_t;

#endif /* ASL200_TYPES_H */
