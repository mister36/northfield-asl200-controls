#include "can_io.h"
#include "controller.h"
#include "faults.h"
#include "scaling.h"
#include "params_asl200_diesel_autocar_eco0412.h"
#include "tiny_test.h"

static void test_datasheet_points(void)
{
    const params_sensors_lift_t *cal = &PARAMS_ACTIVE.sensors.lift;
    CHECK_NEAR(scale_lift_mv_to_deg(500U, cal), -20.0f, 0.01);
    CHECK_NEAR(scale_lift_mv_to_deg(900U, cal), 0.0f, 0.01);
    CHECK_NEAR(scale_lift_mv_to_deg(2500U, cal), 80.0f, 0.01);
    CHECK_NEAR(scale_lift_mv_to_deg(3900U, cal), 150.0f, 0.01);
    CHECK_NEAR(scale_lift_mv_to_deg(4140U, cal), 162.0f, 0.01);
    CHECK_NEAR(scale_lift_mv_to_deg(4500U, cal), 180.0f, 0.01);
    CHECK_NEAR(scale_reach_mv_to_mm(500U, &PARAMS_ACTIVE.sensors.reach), 0.0f, 0.01);
    CHECK_NEAR(scale_reach_mv_to_mm(4500U, &PARAMS_ACTIVE.sensors.reach), 2000.0f, 0.01);
}

static void test_diagnostic_bands(void)
{
    const params_sensors_lift_t *cal = &PARAMS_ACTIVE.sensors.lift;
    const uint16_t valid[] = { 250U, 499U, 500U, 900U, 4500U, 4501U, 4750U };
    unsigned int i;
    CHECK(cal->open_circuit_mv == 250);
    CHECK(cal->short_circuit_mv == 4750);
    CHECK(sensor_check_mv(249U, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_OPEN_CIRCUIT);
    CHECK(sensor_check_mv(4751U, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_SHORT_CIRCUIT);
    for (i = 0U; i < sizeof(valid) / sizeof(valid[0]); i++) {
        CHECK(sensor_check_mv(valid[i], cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_OK);
    }
}

static void test_can_position(void)
{
    inputs_t in;
    outputs_t out = { 0 };
    state_t st;
    can_tx_sched_t sched;
    can_frame_t sensor = { CAN_ID_ARM_SENSORS, 8U, { 0x3CU, 0x0FU, 0xF4U, 0x01U, 0U, 0U, 0U, 0U } };
    can_frame_t frames[CAN_TX_MAX_FRAMES];
    bool saw_position = false;
    unsigned int step;
    can_io_init(&in, &sched);
    controller_init(&st, &PARAMS_ACTIVE);
    CHECK(can_io_rx(&in, &sensor));
    CHECK(in.lift_sensor_mv == 3900U);
    in.ccvs_age_ms = 0U;
    for (step = 0U; step < 5U; step++) {
        uint8_t i;
        uint8_t n;
        controller_step(&in, &out, &st);
        can_io_tick(&in, CONTROLLER_STEP_MS);
        n = can_io_tx(&out, &st, &sched, frames, CAN_TX_MAX_FRAMES);
        for (i = 0U; i < n; i++) {
            if (frames[i].id == CAN_ID_ARM_POSITION) {
                saw_position = true;
                CHECK(frames[i].data[0] == 0x98U);
                CHECK(frames[i].data[1] == 0x3AU);
            }
        }
    }
    CHECK(saw_position);
    CHECK_NEAR(out.lift_angle_deg, 150.0f, 0.01);
}

static void test_fault_debounce_and_reset(uint16_t mv, uint8_t fmi)
{
    inputs_t in;
    outputs_t out = { 0 };
    state_t st;
    can_tx_sched_t sched;
    unsigned int i;
    bool saw_dtc = false;
    can_io_init(&in, &sched);
    controller_init(&st, &PARAMS_ACTIVE);
    in.ccvs_age_ms = 0U;
    in.reach_sensor_mv = 500U;
    in.lift_sensor_mv = 900U;
    in.jog_lift_pct = 100;
    controller_step(&in, &out, &st);
    CHECK(out.lift_cmd_pct > 0.0f);
    in.lift_sensor_mv = mv;
    for (i = 0U; i < 4U; i++) {
        controller_step(&in, &out, &st);
        CHECK(st.state != ST_FAULT_STOP);
        CHECK_NEAR(out.lift_cmd_pct, 0.0f, 0.0);
    }
    controller_step(&in, &out, &st);
    CHECK(st.state == ST_FAULT_STOP);
    for (i = 0U; i < DTC_TABLE_SIZE; i++) {
        if (st.dtcs[i].active && st.dtcs[i].spn == SPN_ARM_LIFT_POSITION_SENSOR && st.dtcs[i].fmi == fmi) {
            saw_dtc = true;
        }
    }
    CHECK(saw_dtc);
    in.fault_reset = true;
    controller_step(&in, &out, &st);
    CHECK(st.state == ST_FAULT_STOP);
    in.fault_reset = false;
    in.lift_sensor_mv = 900U;
    controller_step(&in, &out, &st);
    CHECK(st.state == ST_FAULT_STOP);
    in.fault_reset = true;
    controller_step(&in, &out, &st);
    CHECK(st.state == ST_IDLE);
    for (i = 0U; i < DTC_TABLE_SIZE; i++) {
        CHECK(!st.dtcs[i].active);
    }
}

int main(void)
{
    test_datasheet_points();
    test_diagnostic_bands();
    test_can_position();
    test_fault_debounce_and_reset(249U, FMI_VOLTAGE_BELOW_NORMAL);
    test_fault_debounce_and_reset(4751U, FMI_VOLTAGE_ABOVE_NORMAL);
    TEST_MAIN_END();
}
