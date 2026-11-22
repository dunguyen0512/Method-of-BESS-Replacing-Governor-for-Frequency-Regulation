/* Figures 6-7: state machine / flowchart from the paper.
 * The author additionally specified the 5-second frequency-event latch.
 * No confidential Korean network data or topology is used. */
#include "bess_controller.h"
#include <math.h>

/* 1. Settings for the PSCAD block. Ratings and 5% droop: paper Table 1.
 * +/-0.5 Hz is the requested TEST threshold. SOC thresholds are illustrative,
 * not recovered original settings. Change nominal_hz to 50 for a 50 Hz study. */
BessConfig bess_default_config(void)
{
    BessConfig settings;
    settings.nominal_hz = 60.0;
    settings.deadband_hz = 0.5;
    settings.generator_base_mw = 612.0;
    settings.pcs_mw = 25.0;
    settings.droop = 0.05;
    settings.low = 0.20;
    settings.medium_low = 0.6499;
    settings.medium_high = 0.6501;
    settings.high = 0.80;
    settings.hold_seconds = 5.0;
    return settings;
}

/* 2. Initialize ONCE at simulation start, not at every timestep.
 * Reset again before restarting a simulation or changing settings. */
void bess_reset(BessController *memory)
{
    if (!memory) return;
    memory->droop_active = 0;
    memory->held_soc_mw = 0.0;
    memory->state = 0;
    memory->frequency_indicator = 0;
    memory->hold_until_s = 0.0;
    memory->last_time_s = -1.0;
}

/* 3. Fig. 7 first two decisions: above upper / below lower frequency limit?
 * Exact equality counts as normal; tolerance avoids roundoff activation. */
int bess_detect_frequency(double frequency_hz, const BessConfig *settings)
{
    double deviation = frequency_hz - settings->nominal_hz;
    if (deviation > settings->deadband_hz + 1e-12) return 1;
    if (deviation < -settings->deadband_hz - 1e-12) return -1;
    return 0;
}

/* 4. Event latch BEFORE Fig. 7: capture high/low, hold 5 seconds, re-evaluate.
 * Deadband return or opposite crossing cannot interrupt an active hold.
 * At expiry: normal clears it; high/low begins another hold.
 * Hold the INDICATOR, never the measured numerical frequency. */
int bess_latch_frequency(double time_s, int detected, double hold_seconds,
                         BessController *memory)
{
    if (memory->frequency_indicator != 0 && time_s < memory->hold_until_s) {
        return memory->frequency_indicator;
    }
    memory->frequency_indicator = detected;
    memory->hold_until_s = time_s;
    if (detected != 0) memory->hold_until_s = time_s + hold_seconds;
    return memory->frequency_indicator;
}

/* 5. Follow Fig. 7 TOP to BOTTOM; numbers match Fig. 6.
 * SOC emergency states 2/8 override droop even during a held event. */
int bess_select_state(int indicator, double soc, const BessConfig *settings)
{
    if (indicator == 1) {
        if (soc > settings->high) return 2; /* Emergency discharge. */
        return 1;                         /* High-frequency droop. */
    }
    if (indicator == -1) {
        if (soc <= settings->low) return 8; /* Emergency charge. */
        return 9;                         /* Low-frequency droop. */
    }
    /* Normal-frequency SOC cascade: states 7 -> 6 -> 5 -> 4 -> 3. */
    if (soc > settings->high) return 7;        /* Emergency discharge. */
    if (soc > settings->medium_high) return 6; /* Recovery discharge. */
    if (soc > settings->medium_low) return 5;  /* Center: zero power. */
    if (soc > settings->low) return 4;         /* Recovery charge. */
    return 3;                                /* Emergency charge. */
}

/* 6. Fig. 5 / Eq. (8): SOC recovery contribution, fraction of PCS rating.
 * States 3/8: -15%; 4: -10%; 5: zero; 6: +10%; 2/7: +15%.
 * Also computes the initial SOC bias captured on entry to states 1/9. */
double bess_soc_power(double soc, const BessConfig *settings)
{
    if (soc <= settings->low) return -0.15 * settings->pcs_mw;
    if (soc <= settings->medium_low) return -0.10 * settings->pcs_mw;
    if (soc <= settings->medium_high) return 0.0;
    if (soc <= settings->high) return 0.10 * settings->pcs_mw;
    return 0.15 * settings->pcs_mw;
}

/* 7. States 1/9: Eq. (7), deadband-adjusted LIVE frequency, converted Hz to pu.
 * Droop uses GENERATOR base (Eq. 5), not PCS base.
 * While an indicator is held, permit only its droop direction: high charges,
 * low discharges. Inside deadband / opposite side gives zero droop power.
 * This direction guard is an explicit implementation choice for the latch. */
double bess_droop_power(double frequency_hz, int state, const BessConfig *settings)
{
    double deviation = frequency_hz - settings->nominal_hz;
    double error_hz = 0.0;
    if (state == 1 && deviation > settings->deadband_hz) {
        error_hz = deviation - settings->deadband_hz;
    }
    if (state == 9 && deviation < -settings->deadband_hz) {
        error_hz = deviation + settings->deadband_hz;
    }
    return -settings->generator_base_mw * error_hz /
           (settings->nominal_hz * settings->droop);
}

/* 8. Added physical guards: converter rating and SOC end stops. */
double bess_limit_power(double power_mw, double soc, double pcs_mw)
{
    if (power_mw > pcs_mw) power_mw = pcs_mw;
    if (power_mw < -pcs_mw) power_mw = -pcs_mw;
    if (soc == 0.0 && power_mw > 0.0) power_mw = 0.0;
    if (soc == 1.0 && power_mw < 0.0) power_mw = 0.0;
    return power_mw;
}

/* Keep input checking outside the main control sequence for readability. */
static int valid_settings(const BessConfig *settings)
{
    if (!settings) return 0;
    if (!isfinite(settings->nominal_hz) || settings->nominal_hz <= 0) return 0;
    if (!isfinite(settings->deadband_hz) || settings->deadband_hz < 0 ||
        settings->deadband_hz >= settings->nominal_hz) return 0;
    if (!isfinite(settings->generator_base_mw) || settings->generator_base_mw <= 0) return 0;
    if (!isfinite(settings->pcs_mw) || settings->pcs_mw <= 0) return 0;
    if (!isfinite(settings->droop) || settings->droop <= 0) return 0;
    if (!isfinite(settings->hold_seconds) || settings->hold_seconds < 0) return 0;
    if (!(0 < settings->low && settings->low < settings->medium_low &&
          settings->medium_low < settings->medium_high &&
          settings->medium_high < settings->high && settings->high < 1)) return 0;
    return 1;
}

/* 9. MAIN FUNCTION BLOCK: call once per increasing PSCAD control-sample time.
 * Input SOC is CURRENT SOC from the battery model, not its initial value. */
int bess_step(BessController *memory, const BessConfig *settings,
              double time_s, double frequency_hz, double soc, BessOutput *output)
{
    int detected, indicator, state, active;
    double p_soc, p_droop, p_ess;
    if (!memory || !output || !valid_settings(settings)) return -1;
    if (!isfinite(time_s) || time_s < 0 || time_s <= memory->last_time_s) return -1;
    if (!isfinite(frequency_hz) || frequency_hz <= 0) return -1;
    if (!isfinite(soc) || soc < 0 || soc > 1) return -1;

    /* A. Read the frequency region; latch its activation for 5 seconds. */
    detected = bess_detect_frequency(frequency_hz, settings);
    indicator = bess_latch_frequency(time_s, detected, settings->hold_seconds, memory);

    /* B. Fig. 7: choose state using activation and current SOC. */
    state = bess_select_state(indicator, soc, settings);
    active = (state == 1 || state == 9);

    /* C. Eq. (8), then Section 3.3.2: hold initial P_SOC during droop.
     * This SOC-bias memory is SEPARATE from the frequency-event latch. */
    p_soc = bess_soc_power(soc, settings);
    if (active) {
        if (!memory->droop_active) memory->held_soc_mw = p_soc;
        p_soc = memory->held_soc_mw;
    } else {
        memory->held_soc_mw = 0.0;
    }

    /* D. Eq. (7): droop in states 1/9; zero in every other state. */
    p_droop = bess_droop_power(frequency_hz, state, settings);

    /* E. Fig. 7 FINAL block: P_ESS = P_droop + P_SOC, then limit power. */
    p_ess = bess_limit_power(p_droop + p_soc, soc, settings->pcs_mw);

    /* F. Retain memory for next sample; expose outputs for PSCAD plotting. */
    memory->droop_active = active;
    memory->state = state;
    memory->last_time_s = time_s;
    output->soc_mw = p_soc;
    output->droop_mw = p_droop;
    output->power_mw = p_ess;
    output->droop_active = active;
    output->frequency_indicator = indicator;
    output->state = state;
    return 0;
}
