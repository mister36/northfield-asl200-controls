#include "scaling.h"
#include PARAMS_HEADER
#include "tiny_test.h"

static void test_lift_scaling(void)
{
    const params_sensors_lift_t *cal = &PARAMS_ACTIVE.sensors.lift;
    CHECK_NEAR(scale_lift_mv_to_deg((uint16_t)cal->v_lo_mv, cal), cal->deg_at_v_lo, 1e-4);
    CHECK_NEAR(scale_lift_mv_to_deg((uint16_t)cal->v_hi_mv, cal), cal->deg_at_v_hi, 1e-4);
    /* Lift sensor P/N 55-1180-0 datasheet points */
    CHECK_NEAR(scale_lift_mv_to_deg(500U, cal), 0.0f, 0.01);
    CHECK_NEAR(scale_lift_mv_to_deg(2500U, cal), 80.0f, 0.01);
    CHECK_NEAR(scale_lift_mv_to_deg(4250U, cal), 150.0f, 0.01);
}

static void test_reach_scaling(void)
{
    const params_sensors_reach_t *cal = &PARAMS_ACTIVE.sensors.reach;
    CHECK_NEAR(scale_reach_mv_to_mm(500U, cal), 0.0f, 0.01);
    CHECK_NEAR(scale_reach_mv_to_mm(4500U, cal), 2000.0f, 0.01);
    CHECK_NEAR(scale_reach_mv_to_mm(2500U, cal), 1000.0f, 0.01);
}

static void test_sensor_range_check(void)
{
    const params_sensors_lift_t *cal = &PARAMS_ACTIVE.sensors.lift;
    CHECK(sensor_check_mv(0U, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_OPEN_CIRCUIT);
    CHECK(sensor_check_mv((uint16_t)(cal->open_circuit_mv - 1), cal->open_circuit_mv, cal->short_circuit_mv) ==
          SENSOR_OPEN_CIRCUIT);
    CHECK(sensor_check_mv((uint16_t)cal->open_circuit_mv, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_OK);
    CHECK(sensor_check_mv(2500U, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_OK);
    CHECK(sensor_check_mv(5000U, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_SHORT_CIRCUIT);
    /* every angle inside the mechanical range must read as a valid voltage */
    CHECK(sensor_check_mv(300U, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_OK);  /* -5 deg */
    CHECK(sensor_check_mv(4550U, cal->open_circuit_mv, cal->short_circuit_mv) == SENSOR_OK); /* 162 deg */
}

static void test_clamp(void)
{
    CHECK_NEAR(clampf(5.0f, 0.0f, 1.0f), 1.0f, 0.0);
    CHECK_NEAR(clampf(-5.0f, 0.0f, 1.0f), 0.0f, 0.0);
    CHECK_NEAR(clampf(0.25f, 0.0f, 1.0f), 0.25f, 0.0);
}

int main(void)
{
    test_lift_scaling();
    test_reach_scaling();
    test_sensor_range_check();
    test_clamp();
    TEST_MAIN_END();
}
