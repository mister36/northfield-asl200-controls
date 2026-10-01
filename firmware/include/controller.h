#ifndef CONTROLLER_H
#define CONTROLLER_H

#include "asl200_types.h"

void controller_init(state_t *s, const params_t *p);

/* Fixed-step controller update. Call every CONTROLLER_STEP_MS. */
void controller_step(const inputs_t *in, outputs_t *out, state_t *s);

/* Velocity profile used when moving an axis toward a target position. */
float motion_approach_velocity(float distance, float v_max, float v_creep, float decel_zone);

#endif /* CONTROLLER_H */
