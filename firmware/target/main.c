/*
 * ASL-200 body controller target entry point (Cortex-M class ECU).
 *
 * The HAL functions below are weak placeholders; the production board support
 * package provides CAN driver and 10 ms tick implementations. Only the
 * controller and CAN codec are shared with the SIL build.
 */
#include "can_io.h"
#include "controller.h"
#include "hal.h"
#include PARAMS_HEADER

#define RX_BATCH_MAX 16U

__attribute__((weak)) void hal_init(void) {}
__attribute__((weak)) void hal_wait_tick(void) {}
__attribute__((weak)) bool hal_can_receive(can_frame_t *f)
{
    (void)f;
    return false;
}
__attribute__((weak)) void hal_can_send(const can_frame_t *f)
{
    (void)f;
}
__attribute__((weak)) void hal_watchdog_kick(void) {}

static state_t g_state;
static inputs_t g_inputs;
static outputs_t g_outputs;
static can_tx_sched_t g_sched;

int main(void)
{
    can_frame_t rx;
    can_frame_t tx[CAN_TX_MAX_FRAMES];

    hal_init();
    can_io_init(&g_inputs, &g_sched);
    controller_init(&g_state, &PARAMS_ACTIVE);

    for (;;) {
        uint8_t n_rx = 0U;
        uint8_t n_tx;
        uint8_t i;
        hal_wait_tick();
        while ((n_rx < RX_BATCH_MAX) && hal_can_receive(&rx)) {
            (void)can_io_rx(&g_inputs, &rx);
            n_rx++;
        }
        controller_step(&g_inputs, &g_outputs, &g_state);
        can_io_tick(&g_inputs, CONTROLLER_STEP_MS);
        n_tx = can_io_tx(&g_outputs, &g_state, &g_sched, tx, CAN_TX_MAX_FRAMES);
        for (i = 0U; i < n_tx; i++) {
            hal_can_send(&tx[i]);
        }
        hal_watchdog_kick();
    }
}
