#include "filters.h"

float lpf_first_order(float prev, float sample, float alpha)
{
    return prev + (alpha * (sample - prev));
}

/* Limit how fast |target| may grow relative to prev; reductions pass through. */
float rate_limit(float prev, float target, float max_increase)
{
    float out;
    if ((target > 0.0f) && (target > (prev + max_increase)) && (prev >= 0.0f)) {
        out = prev + max_increase;
    } else if ((target < 0.0f) && (target < (prev - max_increase)) && (prev <= 0.0f)) {
        out = prev - max_increase;
    } else if ((target > 0.0f) && (prev < 0.0f)) {
        out = 0.0f;
    } else if ((target < 0.0f) && (prev > 0.0f)) {
        out = 0.0f;
    } else {
        out = target;
    }
    return out;
}

bool debounce_update(debounce_t *d, bool condition, uint32_t threshold_ms, uint32_t dt_ms)
{
    if (condition) {
        if (d->timer_ms < threshold_ms) {
            d->timer_ms += dt_ms;
        }
        if (d->timer_ms >= threshold_ms) {
            d->tripped = true;
        }
    } else {
        d->timer_ms = 0U;
        d->tripped = false;
    }
    return d->tripped;
}
