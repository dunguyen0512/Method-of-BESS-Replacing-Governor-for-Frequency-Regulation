#ifndef BESS_CONTROLLER_H
#define BESS_CONTROLLER_H

typedef struct {
    double nominal_hz, deadband_hz, generator_base_mw, pcs_mw, droop;
    double low, medium_low, medium_high, high;
} BessConfig;
typedef struct { int active; double held_soc_mw; } BessController;
typedef struct { double soc_mw, droop_mw, power_mw; int droop_active; } BessOutput;

BessConfig bess_default_config(void);
void bess_reset(BessController *controller);
/* Returns 0 on success, -1 for invalid arguments (state/output unchanged).
 * Positive MW = discharge; SOC is a fraction in [0, 1]. */
int bess_step(BessController *controller, const BessConfig *config,
              double frequency_hz, double soc, BessOutput *output);
#endif
