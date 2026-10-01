#include "can_io.h"
#include "controller.h"
#include "faults.h"
#include PARAMS_HEADER
#include "tiny_test.h"

static void test_rx_ccvs(void)
{
    inputs_t in;
    can_tx_sched_t sched;
    can_frame_t f = { CAN_ID_CCVS, 8U, { 0xFFU, 0x00U, 0x05U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU } };
    can_io_init(&in, &sched);
    CHECK(in.ccvs_age_ms > 1000U);
    CHECK(can_io_rx(&in, &f));
    CHECK_NEAR(in.vehicle_speed_kph, 5.0f, 1e-4); /* 0x0500 / 256 */
    CHECK(in.ccvs_age_ms == 0U);
    can_io_tick(&in, 10U);
    CHECK(in.ccvs_age_ms == 10U);
}

static void test_rx_sensors_and_joystick(void)
{
    inputs_t in;
    can_tx_sched_t sched;
    can_frame_t s = { CAN_ID_ARM_SENSORS, 8U, { 0xC4U, 0x09U, 0xE8U, 0x03U, 0xFFU, 0xFFU, 0xFFU, 0xFFU } };
    can_frame_t j = { CAN_ID_JOY_CMD, 8U, { 0x01U, 0xF6U, 0x14U, 0x01U, 0xFFU, 0xFFU, 0xFFU, 0xFFU } };
    can_frame_t u = { 0x18FEEE00UL, 8U, { 0 } };
    can_io_init(&in, &sched);
    CHECK(can_io_rx(&in, &s));
    CHECK(in.lift_sensor_mv == 2500U);
    CHECK(in.reach_sensor_mv == 1000U);
    CHECK(can_io_rx(&in, &j));
    CHECK(in.auto_cycle_request);
    CHECK(!in.fault_reset);
    CHECK(in.jog_lift_pct == -10);
    CHECK(in.jog_reach_pct == 20);
    CHECK(in.grip_request == 1U);
    CHECK(!can_io_rx(&in, &u));
}

static void test_tx_schedule_and_dm1(void)
{
    state_t st;
    outputs_t out = { 0 };
    can_tx_sched_t sched;
    inputs_t in;
    can_frame_t frames[CAN_TX_MAX_FRAMES];
    uint8_t n;
    uint8_t i;
    bool saw_dm1 = false;
    can_io_init(&in, &sched);
    controller_init(&st, &PARAMS_ACTIVE);
    out.lift_cmd_pct = -12.34f;
    n = can_io_tx(&out, &st, &sched, frames, CAN_TX_MAX_FRAMES);
    CHECK(n == 1U);
    CHECK(frames[0].id == CAN_ID_ARM_CMD);
    CHECK(frames[0].data[0] == 0x2EU); /* -1234 = 0xFB2E */
    CHECK(frames[0].data[1] == 0xFBU);

    faults_raise(&st, SPN_ARM_LIFT_ACTUATOR, FMI_MECHANICAL_NOT_RESPONDING);
    out.dtc_changed = true;
    n = can_io_tx(&out, &st, &sched, frames, CAN_TX_MAX_FRAMES);
    for (i = 0U; i < n; i++) {
        if (frames[i].id == CAN_ID_DM1) {
            const uint32_t spn = (uint32_t)frames[i].data[2] | ((uint32_t)frames[i].data[3] << 8) |
                                 ((uint32_t)(frames[i].data[4] >> 5) << 16);
            saw_dm1 = true;
            CHECK(spn == SPN_ARM_LIFT_ACTUATOR);
            CHECK((frames[i].data[4] & 0x1FU) == FMI_MECHANICAL_NOT_RESPONDING);
            CHECK(frames[i].data[5] == 1U);
        }
    }
    CHECK(saw_dm1);
}

int main(void)
{
    test_rx_ccvs();
    test_rx_sensors_and_joystick();
    test_tx_schedule_and_dm1();
    TEST_MAIN_END();
}
