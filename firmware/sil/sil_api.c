/*
 * Software-in-the-loop entry points. Wraps the production controller and CAN
 * codec in a frame-in / frame-out API so a host harness can drive it over a
 * (virtual) CAN bus. One shared library is built per variant; PARAMS_HEADER
 * selects the generated parameter set.
 */
#include "can_io.h"
#include "controller.h"
#include "sil_api.h"
#include PARAMS_HEADER

#if defined(_WIN32)
#define SIL_EXPORT __declspec(dllexport)
#else
#define SIL_EXPORT __attribute__((visibility("default")))
#endif

static state_t g_state;
static inputs_t g_inputs;
static outputs_t g_outputs;
static can_tx_sched_t g_sched;

SIL_EXPORT const char *sil_variant_name(void)
{
    return ASL200_VARIANT_NAME;
}

SIL_EXPORT uint32_t sil_step_ms(void)
{
    return CONTROLLER_STEP_MS;
}

SIL_EXPORT void sil_reset(void)
{
    can_io_init(&g_inputs, &g_sched);
    controller_init(&g_state, &PARAMS_ACTIVE);
}

/* Deliver received frames, run one controller step, return frames to send. */
SIL_EXPORT uint8_t sil_step(const can_frame_t *rx, uint32_t n_rx, can_frame_t *tx, uint8_t max_tx)
{
    uint32_t i;
    for (i = 0U; i < n_rx; i++) {
        (void)can_io_rx(&g_inputs, &rx[i]);
    }
    controller_step(&g_inputs, &g_outputs, &g_state);
    can_io_tick(&g_inputs, CONTROLLER_STEP_MS);
    return can_io_tx(&g_outputs, &g_state, &g_sched, tx, max_tx);
}
