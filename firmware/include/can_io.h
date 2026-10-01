#ifndef CAN_IO_H
#define CAN_IO_H

#include "asl200_types.h"

typedef struct {
    uint32_t id;       /* 29-bit J1939 identifier */
    uint8_t dlc;
    uint8_t data[8];
} can_frame_t;

/* J1939 identifiers (priority 6, see can/asl200.dbc) */
#define CAN_ID_CCVS            0x18FEF100UL
#define CAN_ID_AMB             0x18FEF500UL
#define CAN_ID_DM1             0x18FECA21UL
#define CAN_ID_JOY_CMD         0x18FF102CUL
#define CAN_ID_BODY_INPUTS     0x18FF1180UL
#define CAN_ID_ARM_SENSORS     0x18FF1280UL
#define CAN_ID_ACTUATOR_STATUS 0x18FF1381UL
#define CAN_ID_BATT_STATUS     0x18FF14E6UL
#define CAN_ID_ARM_CMD         0x18FF2021UL
#define CAN_ID_ARM_STATE       0x18FF2121UL
#define CAN_ID_ARM_POSITION    0x18FF2221UL

#define CAN_TX_MAX_FRAMES      8U

#define CAN_PERIOD_ARM_CMD_MS      10U
#define CAN_PERIOD_ARM_POSITION_MS 20U
#define CAN_PERIOD_ARM_STATE_MS    50U
#define CAN_PERIOD_DM1_MS          1000U

typedef struct {
    uint32_t time_ms;
    uint32_t last_dm1_ms;
} can_tx_sched_t;

/* Initialise the input image to safe defaults (no road speed, no requests). */
void can_io_init(inputs_t *in, can_tx_sched_t *sched);

/* Decode one received frame into the input image. Returns true if consumed. */
bool can_io_rx(inputs_t *in, const can_frame_t *f);

/* Called once per controller step to age timeouts. */
void can_io_tick(inputs_t *in, uint32_t dt_ms);

/* Encode the frames due this step. Returns number of frames written. */
uint8_t can_io_tx(const outputs_t *out, const state_t *s, can_tx_sched_t *sched,
                  can_frame_t *frames, uint8_t max_frames);

#endif /* CAN_IO_H */
