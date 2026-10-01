#ifndef SCALING_H
#define SCALING_H

#include "asl200_types.h"

typedef enum {
    SENSOR_OK = 0,
    SENSOR_OPEN_CIRCUIT = 1,
    SENSOR_SHORT_CIRCUIT = 2
} sensor_status_t;

#define KPH_PER_MPH 1.609344f

float scale_lift_mv_to_deg(uint16_t mv, const params_sensors_lift_t *cal);
float scale_reach_mv_to_mm(uint16_t mv, const params_sensors_reach_t *cal);
sensor_status_t sensor_check_mv(uint16_t mv, int32_t open_mv, int32_t short_mv);
float clampf(float v, float lo, float hi);

#endif /* SCALING_H */
