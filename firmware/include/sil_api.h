#ifndef SIL_API_H
#define SIL_API_H

#include "can_io.h"

/* Frame-level SIL interface; see firmware/sil/sil_api.c. */
const char *sil_variant_name(void);
uint32_t sil_step_ms(void);
void sil_reset(void);
uint8_t sil_step(const can_frame_t *rx, uint32_t n_rx, can_frame_t *tx, uint8_t max_tx);

#endif /* SIL_API_H */
