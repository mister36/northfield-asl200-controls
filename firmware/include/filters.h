#ifndef FILTERS_H
#define FILTERS_H

#include "asl200_types.h"

float lpf_first_order(float prev, float sample, float alpha);
float rate_limit(float prev, float target, float max_increase);
bool debounce_update(debounce_t *d, bool condition, uint32_t threshold_ms, uint32_t dt_ms);

#endif /* FILTERS_H */
