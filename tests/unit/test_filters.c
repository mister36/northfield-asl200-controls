#include "filters.h"
#include "tiny_test.h"

static void test_lpf(void)
{
    float y = 0.0f;
    int i;
    y = lpf_first_order(y, 10.0f, 0.5f);
    CHECK_NEAR(y, 5.0f, 1e-6);
    for (i = 0; i < 50; i++) {
        y = lpf_first_order(y, 10.0f, 0.5f);
    }
    CHECK_NEAR(y, 10.0f, 1e-4);
    CHECK_NEAR(lpf_first_order(3.0f, 7.0f, 1.0f), 7.0f, 1e-6);
    CHECK_NEAR(lpf_first_order(3.0f, 7.0f, 0.0f), 3.0f, 1e-6);
}

static void test_rate_limit(void)
{
    CHECK_NEAR(rate_limit(0.0f, 10.0f, 2.0f), 2.0f, 1e-6);
    CHECK_NEAR(rate_limit(9.0f, 10.0f, 2.0f), 10.0f, 1e-6);
    CHECK_NEAR(rate_limit(10.0f, 3.0f, 2.0f), 3.0f, 1e-6);   /* decreases pass through */
    CHECK_NEAR(rate_limit(0.0f, -10.0f, 2.0f), -2.0f, 1e-6);
    CHECK_NEAR(rate_limit(5.0f, -10.0f, 2.0f), 0.0f, 1e-6);  /* reversal stops first */
    CHECK_NEAR(rate_limit(-5.0f, 10.0f, 2.0f), 0.0f, 1e-6);
}

static void test_debounce(void)
{
    debounce_t d = { 0U, false };
    int i;
    for (i = 0; i < 4; i++) {
        CHECK(!debounce_update(&d, true, 50U, 10U));
    }
    CHECK(debounce_update(&d, true, 50U, 10U));
    CHECK(debounce_update(&d, true, 50U, 10U));
    CHECK(!debounce_update(&d, false, 50U, 10U));
    CHECK(d.timer_ms == 0U);
}

int main(void)
{
    test_lpf();
    test_rate_limit();
    test_debounce();
    TEST_MAIN_END();
}
