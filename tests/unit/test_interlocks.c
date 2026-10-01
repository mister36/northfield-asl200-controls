#include "controller.h"
#include "interlocks.h"
#include "scaling.h"
#include PARAMS_HEADER
#include "tiny_test.h"

static void base_inputs(inputs_t *in)
{
    in->vehicle_speed_kph = 0.0f;
    in->ccvs_age_ms = 0U;
    in->batt_valid = false;
    in->batt_temp_c = 20.0f;
    in->tailgate_open = false;
    in->gripper_pressure_bar = 0.0f;
}

static void test_vehicle_speed(void)
{
    inputs_t in;
    const float lim = PARAMS_ACTIVE.interlocks.vehicle_speed_limit_mph * KPH_PER_MPH;
    base_inputs(&in);
    CHECK(interlock_vehicle_speed(&in, &PARAMS_ACTIVE));
    in.vehicle_speed_kph = lim - 0.1f;
    CHECK(interlock_vehicle_speed(&in, &PARAMS_ACTIVE));
    in.vehicle_speed_kph = lim + 0.1f;
    CHECK(!interlock_vehicle_speed(&in, &PARAMS_ACTIVE));
    in.vehicle_speed_kph = 0.0f;
    in.ccvs_age_ms = (uint32_t)PARAMS_ACTIVE.interlocks.ccvs_timeout_ms + 10U;
    CHECK(!interlock_vehicle_speed(&in, &PARAMS_ACTIVE)); /* stale road speed */
}

static void test_tailgate_and_battery(void)
{
    inputs_t in;
    base_inputs(&in);
    CHECK(interlock_tailgate(&in, &PARAMS_ACTIVE));
    in.tailgate_open = true;
    CHECK(!interlock_tailgate(&in, &PARAMS_ACTIVE));
    CHECK(interlock_battery_temp(&in, &PARAMS_ACTIVE)); /* no BMS on this variant */
    in.batt_valid = true;
    in.batt_temp_c = PARAMS_ACTIVE.interlocks.batt_temp_max_c + 1.0f;
    CHECK(!interlock_battery_temp(&in, &PARAMS_ACTIVE));
}

static void test_grip_secure_dwell(void)
{
    inputs_t in;
    uint32_t timer = 0U;
    uint32_t t;
    bool secured = false;
    base_inputs(&in);
    in.gripper_pressure_bar = PARAMS_ACTIVE.interlocks.grip_secure_pressure_bar + 5.0f;
    for (t = 10U; t < (uint32_t)PARAMS_ACTIVE.interlocks.grip_secure_time_ms; t += 10U) {
        secured = interlock_grip_secured(&in, &PARAMS_ACTIVE, &timer, 10U);
        CHECK(!secured);
    }
    secured = interlock_grip_secured(&in, &PARAMS_ACTIVE, &timer, 10U);
    CHECK(secured);
    in.gripper_pressure_bar = 10.0f;
    CHECK(!interlock_grip_secured(&in, &PARAMS_ACTIVE, &timer, 10U));
}

static void test_soft_limits(void)
{
    bool active = false;
    const float max = PARAMS_ACTIVE.limits.lift_soft_max_deg;
    CHECK_NEAR(interlock_soft_limit_lift(50.0f, 20.0f, &PARAMS_ACTIVE, &active), 50.0f, 1e-4);
    CHECK(!active);
    CHECK(interlock_soft_limit_lift(50.0f, max - 5.0f, &PARAMS_ACTIVE, &active) < 50.0f);
    CHECK(active);
    CHECK_NEAR(interlock_soft_limit_lift(50.0f, max + 1.0f, &PARAMS_ACTIVE, &active), 0.0f, 1e-4);
    /* moving away from a limit is never restricted */
    CHECK_NEAR(interlock_soft_limit_lift(-50.0f, max + 1.0f, &PARAMS_ACTIVE, &active), -50.0f, 1e-4);
    CHECK_NEAR(interlock_soft_limit_reach(-100.0f, -1.0f, &PARAMS_ACTIVE, &active), 0.0f, 1e-4);
}

static void test_approach_profile(void)
{
    CHECK_NEAR(motion_approach_velocity(100.0f, 60.0f, 6.0f, 30.0f), 60.0f, 1e-4);
    CHECK_NEAR(motion_approach_velocity(15.0f, 60.0f, 6.0f, 30.0f), 30.0f, 1e-4);
    CHECK_NEAR(motion_approach_velocity(2.0f, 60.0f, 6.0f, 30.0f), 6.0f, 1e-4);
    CHECK_NEAR(motion_approach_velocity(0.5f, 60.0f, 6.0f, 30.0f), 0.0f, 1e-4); /* inside stop band */
    CHECK_NEAR(motion_approach_velocity(0.0f, 60.0f, 6.0f, 30.0f), 0.0f, 1e-4);
}

static void test_target_profile(void)
{
    CHECK_NEAR(motion_target_velocity(100.0f, 60.0f, 6.0f, 30.0f), 60.0f, 1e-4);
    CHECK_NEAR(motion_target_velocity(15.0f, 60.0f, 6.0f, 30.0f), 42.4264f, 1e-3);
    CHECK_NEAR(motion_target_velocity(7.5f, 60.0f, 6.0f, 30.0f), 30.0f, 1e-3);
    CHECK_NEAR(motion_target_velocity(3.0f, 60.0f, 20.0f, 30.0f), 20.0f, 1e-4); /* creep floor */
    CHECK_NEAR(motion_target_velocity(0.5f, 60.0f, 6.0f, 30.0f), 0.0f, 1e-4);  /* inside stop band */
    CHECK_NEAR(motion_target_velocity(0.0f, 60.0f, 6.0f, 30.0f), 0.0f, 1e-4);
}

static void test_stall_monitor(void)
{
    stall_monitor_t m;
    int i;
    bool stalled = false;
    stall_monitor_reset(&m);
    for (i = 0; i < 100; i++) {
        stalled = stall_monitor_update(&m, true, (float)i * 0.2f, 1.0f, 400U, 10U);
        CHECK(!stalled);
    }
    for (i = 0; i < 39; i++) {
        stalled = stall_monitor_update(&m, true, 20.0f, 1.0f, 400U, 10U);
    }
    CHECK(!stalled);
    for (i = 0; i < 5; i++) {
        stalled = stall_monitor_update(&m, true, 20.0f, 1.0f, 400U, 10U);
    }
    CHECK(stalled);
    CHECK(!stall_monitor_update(&m, false, 20.0f, 1.0f, 400U, 10U));
}

int main(void)
{
    test_vehicle_speed();
    test_tailgate_and_battery();
    test_grip_secure_dwell();
    test_soft_limits();
    test_approach_profile();
    test_target_profile();
    test_stall_monitor();
    TEST_MAIN_END();
}
