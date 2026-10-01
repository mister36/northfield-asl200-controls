#include "scaling.h"

float clampf(float v, float lo, float hi)
{
    float r = v;
    if (r < lo) {
        r = lo;
    }
    if (r > hi) {
        r = hi;
    }
    return r;
}

float scale_lift_mv_to_deg(uint16_t mv, const params_sensors_lift_t *cal)
{
    const float span_mv = (float)(cal->v_hi_mv - cal->v_lo_mv);
    const float frac = ((float)mv - (float)cal->v_lo_mv) / span_mv;
    return cal->deg_at_v_lo + (frac * (cal->deg_at_v_hi - cal->deg_at_v_lo));
}

float scale_reach_mv_to_mm(uint16_t mv, const params_sensors_reach_t *cal)
{
    const float span_mv = (float)(cal->v_hi_mv - cal->v_lo_mv);
    const float frac = ((float)mv - (float)cal->v_lo_mv) / span_mv;
    return cal->mm_at_v_lo + (frac * (cal->mm_at_v_hi - cal->mm_at_v_lo));
}

sensor_status_t sensor_check_mv(uint16_t mv, int32_t open_mv, int32_t short_mv)
{
    sensor_status_t st = SENSOR_OK;
    if ((int32_t)mv < open_mv) {
        st = SENSOR_OPEN_CIRCUIT;
    } else if ((int32_t)mv > short_mv) {
        st = SENSOR_SHORT_CIRCUIT;
    } else {
        st = SENSOR_OK;
    }
    return st;
}
