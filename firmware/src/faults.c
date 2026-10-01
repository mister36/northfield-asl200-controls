#include "faults.h"

void faults_init(state_t *s)
{
    uint8_t i;
    for (i = 0U; i < DTC_TABLE_SIZE; i++) {
        s->dtcs[i].spn = 0U;
        s->dtcs[i].fmi = 0U;
        s->dtcs[i].occurrence = 0U;
        s->dtcs[i].active = false;
    }
    s->dtc_changed = false;
}

static int8_t faults_find(const state_t *s, uint32_t spn, uint8_t fmi)
{
    int8_t idx = -1;
    uint8_t i;
    for (i = 0U; i < DTC_TABLE_SIZE; i++) {
        if ((s->dtcs[i].occurrence > 0U) && (s->dtcs[i].spn == spn) && (s->dtcs[i].fmi == fmi)) {
            idx = (int8_t)i;
            break;
        }
    }
    return idx;
}

void faults_raise(state_t *s, uint32_t spn, uint8_t fmi)
{
    int8_t idx = faults_find(s, spn, fmi);
    if (idx < 0) {
        uint8_t i;
        for (i = 0U; i < DTC_TABLE_SIZE; i++) {
            if (s->dtcs[i].occurrence == 0U) {
                idx = (int8_t)i;
                s->dtcs[i].spn = spn;
                s->dtcs[i].fmi = fmi;
                break;
            }
        }
    }
    if ((idx >= 0) && (!s->dtcs[idx].active)) {
        s->dtcs[idx].active = true;
        if (s->dtcs[idx].occurrence < 126U) {
            s->dtcs[idx].occurrence++;
        }
        s->dtc_changed = true;
    }
}

void faults_clear(state_t *s, uint32_t spn, uint8_t fmi)
{
    int8_t idx = faults_find(s, spn, fmi);
    if ((idx >= 0) && s->dtcs[idx].active) {
        s->dtcs[idx].active = false;
        s->dtc_changed = true;
    }
}

bool faults_is_active(const state_t *s, uint32_t spn, uint8_t fmi)
{
    int8_t idx = faults_find(s, spn, fmi);
    return (idx >= 0) && s->dtcs[idx].active;
}

uint8_t faults_active_count(const state_t *s)
{
    uint8_t n = 0U;
    uint8_t i;
    for (i = 0U; i < DTC_TABLE_SIZE; i++) {
        if (s->dtcs[i].active) {
            n++;
        }
    }
    return n;
}

const dtc_t *faults_first_active(const state_t *s)
{
    const dtc_t *d = (const dtc_t *)0;
    uint8_t i;
    for (i = 0U; i < DTC_TABLE_SIZE; i++) {
        if (s->dtcs[i].active) {
            d = &s->dtcs[i];
            break;
        }
    }
    return d;
}
