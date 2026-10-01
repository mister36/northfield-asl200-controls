#ifndef HAL_H
#define HAL_H

#include "can_io.h"

/* Board support hooks implemented by the ECU BSP (weak defaults in target/main.c). */
void hal_init(void);
void hal_wait_tick(void);
bool hal_can_receive(can_frame_t *f);
void hal_can_send(const can_frame_t *f);
void hal_watchdog_kick(void);

#endif /* HAL_H */
