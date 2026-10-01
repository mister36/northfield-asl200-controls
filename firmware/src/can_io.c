/*
 * J1939 frame encode/decode for the ASL-200 body controller.
 * Byte layouts follow can/asl200.dbc (Intel / little-endian signals).
 */
#include "can_io.h"
#include "faults.h"
#include "scaling.h"

#define CCVS_TIMEOUT_SAT_MS 60000U
#define J1939_NA_BYTE       0xFFU

static uint16_t get_u16(const uint8_t *d, uint8_t at)
{
    return (uint16_t)((uint16_t)d[at] | (uint16_t)((uint16_t)d[at + 1U] << 8));
}

static void put_u16(uint8_t *d, uint8_t at, uint16_t v)
{
    d[at] = (uint8_t)(v & 0xFFU);
    d[at + 1U] = (uint8_t)((v >> 8) & 0xFFU);
}

static int16_t to_i16(float v, float scale)
{
    float raw = v / scale;
    raw = clampf(raw, -32768.0f, 32767.0f);
    raw = (raw >= 0.0f) ? (raw + 0.5f) : (raw - 0.5f);
    return (int16_t)raw;
}

static float temp_from_raw(uint16_t raw)
{
    return ((float)raw * 0.03125f) - 273.0f;
}

static void frame_init(can_frame_t *f, uint32_t id)
{
    uint8_t i;
    f->id = id;
    f->dlc = 8U;
    for (i = 0U; i < 8U; i++) {
        f->data[i] = J1939_NA_BYTE;
    }
}

void can_io_init(inputs_t *in, can_tx_sched_t *sched)
{
    in->vehicle_speed_kph = 0.0f;
    in->ccvs_age_ms = CCVS_TIMEOUT_SAT_MS;
    in->ambient_temp_c = 20.0f;
    in->batt_temp_c = 20.0f;
    in->batt_valid = false;
    in->lift_sensor_mv = 0U;
    in->reach_sensor_mv = 0U;
    in->gripper_pressure_bar = 0.0f;
    in->tailgate_open = false;
    in->auto_cycle_request = false;
    in->fault_reset = false;
    in->jog_lift_pct = 0;
    in->jog_reach_pct = 0;
    in->grip_request = 0U;
    in->lift_effort = 0.0f;
    sched->time_ms = 0U;
    sched->last_dm1_ms = 0U;
}

bool can_io_rx(inputs_t *in, const can_frame_t *f)
{
    const uint8_t *d = f->data;
    bool used = true;
    if (f->dlc < 8U) {
        used = false;
    } else {
        switch (f->id) {
        case CAN_ID_CCVS:
            in->vehicle_speed_kph = (float)get_u16(d, 1U) / 256.0f;
            in->ccvs_age_ms = 0U;
            break;
        case CAN_ID_AMB:
            in->ambient_temp_c = temp_from_raw(get_u16(d, 3U));
            break;
        case CAN_ID_JOY_CMD:
            in->auto_cycle_request = (d[0] & 0x01U) != 0U;
            in->fault_reset = (d[0] & 0x02U) != 0U;
            in->jog_lift_pct = (int8_t)d[1];
            in->jog_reach_pct = (int8_t)d[2];
            in->grip_request = (uint8_t)(d[3] & 0x03U);
            break;
        case CAN_ID_BODY_INPUTS:
            in->tailgate_open = (d[0] & 0x01U) != 0U;
            in->gripper_pressure_bar = (float)get_u16(d, 1U) * 0.1f;
            break;
        case CAN_ID_ARM_SENSORS:
            in->lift_sensor_mv = get_u16(d, 0U);
            in->reach_sensor_mv = get_u16(d, 2U);
            break;
        case CAN_ID_ACTUATOR_STATUS:
            in->lift_effort = (float)get_u16(d, 0U) * 0.1f;
            break;
        case CAN_ID_BATT_STATUS:
            in->batt_temp_c = temp_from_raw(get_u16(d, 0U));
            in->batt_valid = true;
            break;
        default:
            used = false;
            break;
        }
    }
    return used;
}

void can_io_tick(inputs_t *in, uint32_t dt_ms)
{
    if (in->ccvs_age_ms < CCVS_TIMEOUT_SAT_MS) {
        in->ccvs_age_ms += dt_ms;
    }
}

static void encode_arm_cmd(const outputs_t *out, can_frame_t *f)
{
    frame_init(f, CAN_ID_ARM_CMD);
    put_u16(f->data, 0U, (uint16_t)to_i16(out->lift_cmd_pct, 0.01f));
    put_u16(f->data, 2U, (uint16_t)to_i16(out->reach_cmd_pct, 0.01f));
    f->data[4] = (uint8_t)(0xFCU | ((uint8_t)out->grip_cmd & 0x03U));
}

static void encode_arm_state(const outputs_t *out, can_frame_t *f)
{
    uint8_t flags = 0U;
    frame_init(f, CAN_ID_ARM_STATE);
    f->data[0] = (uint8_t)(((uint8_t)out->state & 0x0FU) | (((uint8_t)out->lift_phase & 0x07U) << 4));
    flags |= out->ilk_vehicle_speed_ok ? 0x01U : 0x00U;
    flags |= out->ilk_grip_secured ? 0x02U : 0x00U;
    flags |= out->ilk_tailgate_closed ? 0x04U : 0x00U;
    flags |= out->soft_limit_active ? 0x08U : 0x00U;
    flags |= out->stall_detected ? 0x10U : 0x00U;
    f->data[1] = (uint8_t)(0xE0U | flags);
    put_u16(f->data, 2U, out->cycle_count);
}

static void encode_arm_position(const outputs_t *out, can_frame_t *f)
{
    frame_init(f, CAN_ID_ARM_POSITION);
    put_u16(f->data, 0U, (uint16_t)to_i16(out->lift_angle_deg, 0.01f));
    put_u16(f->data, 2U, (uint16_t)to_i16(out->reach_mm, 0.1f));
}

/* DM1 single-frame form: reports the first active DTC. */
static void encode_dm1(const state_t *s, can_frame_t *f)
{
    const dtc_t *dtc = faults_first_active(s);
    frame_init(f, CAN_ID_DM1);
    if (dtc == (const dtc_t *)0) {
        f->data[0] = 0x00U;
        put_u16(f->data, 2U, 0U);
        f->data[4] = 0x00U;
        f->data[5] = 0x00U;
    } else {
        f->data[0] = 0x14U; /* red stop lamp + amber warning lamp on */
        put_u16(f->data, 2U, (uint16_t)(dtc->spn & 0xFFFFUL));
        f->data[4] = (uint8_t)((dtc->fmi & 0x1FU) | (uint8_t)(((dtc->spn >> 16) & 0x07UL) << 5));
        f->data[5] = (uint8_t)(dtc->occurrence & 0x7FU);
    }
}

uint8_t can_io_tx(const outputs_t *out, const state_t *s, can_tx_sched_t *sched, can_frame_t *frames,
                  uint8_t max_frames)
{
    uint8_t n = 0U;
    sched->time_ms += CONTROLLER_STEP_MS;

    if (((sched->time_ms % CAN_PERIOD_ARM_CMD_MS) == 0U) && (n < max_frames)) {
        encode_arm_cmd(out, &frames[n]);
        n++;
    }
    if (((sched->time_ms % CAN_PERIOD_ARM_POSITION_MS) == 0U) && (n < max_frames)) {
        encode_arm_position(out, &frames[n]);
        n++;
    }
    if ((((sched->time_ms % CAN_PERIOD_ARM_STATE_MS) == 0U) || out->dtc_changed) && (n < max_frames)) {
        encode_arm_state(out, &frames[n]);
        n++;
    }
    if ((out->dtc_changed || ((sched->time_ms - sched->last_dm1_ms) >= CAN_PERIOD_DM1_MS)) && (n < max_frames)) {
        encode_dm1(s, &frames[n]);
        sched->last_dm1_ms = sched->time_ms;
        n++;
    }
    return n;
}
