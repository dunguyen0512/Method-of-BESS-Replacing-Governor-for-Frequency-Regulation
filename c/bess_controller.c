#include "bess_controller.h"
#include <math.h>
#include <stddef.h>

BessConfig bess_default_config(void) {
    BessConfig c = {60.0, 0.02, 612.0, 25.0, 0.05, 0.2, 0.4, 0.6, 0.8};
    return c;
}
void bess_reset(BessController *s) {
    if (s) { s->active = 0; s->held_soc_mw = 0.0; }
}
static int valid(const BessConfig *c) {
    return c && isfinite(c->nominal_hz) && c->nominal_hz > 0 &&
        isfinite(c->deadband_hz) && c->deadband_hz >= 0 && c->deadband_hz < c->nominal_hz &&
        isfinite(c->generator_base_mw) && c->generator_base_mw > 0 &&
        isfinite(c->pcs_mw) && c->pcs_mw > 0 && isfinite(c->droop) && c->droop > 0 &&
        0 < c->low && c->low < c->medium_low && c->medium_low < c->medium_high &&
        c->medium_high < c->high && c->high < 1;
}
int bess_step(BessController *s, const BessConfig *c, double f, double soc, BessOutput *out) {
    double recovery, delta, error, droop = 0.0, power;
    int high_f, low_f, enabled;
    if (!s || !out || !valid(c) || !isfinite(f) || f <= 0 ||
        !isfinite(soc) || soc < 0 || soc > 1) return -1;
    if (soc <= c->low) recovery = -0.15 * c->pcs_mw;
    else if (soc <= c->medium_low) recovery = -0.10 * c->pcs_mw;
    else if (soc <= c->medium_high) recovery = 0.0;
    else if (soc <= c->high) recovery = 0.10 * c->pcs_mw;
    else recovery = 0.15 * c->pcs_mw;
    delta = f - c->nominal_hz;
    high_f = delta > c->deadband_hz + 1e-12;
    low_f = delta < -c->deadband_hz - 1e-12;
    enabled = (high_f && soc <= c->high) || (low_f && soc > c->low);
    if (enabled) {
        if (!s->active) s->held_soc_mw = recovery;
        recovery = s->held_soc_mw;
        error = high_f ? delta - c->deadband_hz : delta + c->deadband_hz;
        droop = -c->generator_base_mw * error / (c->nominal_hz * c->droop);
    }
    s->active = enabled;
    power = fmax(-c->pcs_mw, fmin(c->pcs_mw, recovery + droop));
    if ((soc == 0 && power > 0) || (soc == 1 && power < 0)) power = 0;
    out->soc_mw = recovery; out->droop_mw = droop;
    out->power_mw = power; out->droop_active = enabled;
    return 0;
}
