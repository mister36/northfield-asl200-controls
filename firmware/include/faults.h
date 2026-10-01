#ifndef FAULTS_H
#define FAULTS_H

#include "asl200_types.h"

/* Proprietary SPNs (J1939 manufacturer range 520192-524287). See can/faults.yaml. */
#define SPN_ARM_LIFT_POSITION_SENSOR   520200UL
#define SPN_ARM_REACH_POSITION_SENSOR  520201UL
#define SPN_ARM_LIFT_ACTUATOR          520210UL
#define SPN_ARM_REACH_ACTUATOR         520211UL
#define SPN_GRIPPER                    520220UL
#define SPN_ARM_LIFT_TRAVEL            520240UL

#define FMI_ABOVE_NORMAL_MOST_SEVERE   0U
#define FMI_DATA_ERRATIC               2U
#define FMI_VOLTAGE_ABOVE_NORMAL       3U
#define FMI_VOLTAGE_BELOW_NORMAL       4U
#define FMI_MECHANICAL_NOT_RESPONDING  7U

void faults_init(state_t *s);
void faults_raise(state_t *s, uint32_t spn, uint8_t fmi);
void faults_clear(state_t *s, uint32_t spn, uint8_t fmi);
bool faults_is_active(const state_t *s, uint32_t spn, uint8_t fmi);
uint8_t faults_active_count(const state_t *s);
const dtc_t *faults_first_active(const state_t *s);

#endif /* FAULTS_H */
