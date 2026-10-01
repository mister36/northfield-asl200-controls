/* Minimal assertion helpers for host-side C unit tests. */
#ifndef TINY_TEST_H
#define TINY_TEST_H

#include <math.h>
#include <stdio.h>

static int tt_failures = 0;
static int tt_checks = 0;

#define CHECK(cond)                                                              \
    do {                                                                         \
        tt_checks++;                                                             \
        if (!(cond)) {                                                           \
            tt_failures++;                                                       \
            printf("%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond);      \
        }                                                                        \
    } while (0)

#define CHECK_NEAR(actual, expected, tol)                                        \
    do {                                                                         \
        const double tt_a = (double)(actual);                                    \
        const double tt_e = (double)(expected);                                  \
        tt_checks++;                                                             \
        if (fabs(tt_a - tt_e) > (double)(tol)) {                                 \
            tt_failures++;                                                       \
            printf("%s:%d: CHECK_NEAR failed: %s = %g, expected %g (tol %g)\n",  \
                   __FILE__, __LINE__, #actual, tt_a, tt_e, (double)(tol));      \
        }                                                                        \
    } while (0)

#define TEST_MAIN_END()                                                          \
    do {                                                                         \
        printf("%d checks, %d failures\n", tt_checks, tt_failures);              \
        return (tt_failures == 0) ? 0 : 1;                                       \
    } while (0)

#endif
