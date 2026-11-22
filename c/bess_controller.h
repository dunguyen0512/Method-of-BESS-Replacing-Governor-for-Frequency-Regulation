#ifndef BESS_CONTROLLER_H
#define BESS_CONTROLLER_H

typedef struct {
    double nominal_hz, deadband_hz, generator_base_mw, pcs_mw, droop;
    double low, medium_low, medium_high, high;
} BessConfig;
typedef enum {
    BESS_HIGH_F_DROOP = 1, BESS_HIGH_F_HIGH_SOC = 2,
    BESS_DEADBAND_LOW_SOC = 3, BESS_DEADBAND_MEDIUM_LOW_SOC = 4,
    BESS_DEADBAND_CENTER = 5, BESS_DEADBAND_MEDIUM_HIGH_SOC = 6,
    BESS_DEADBAND_HIGH_SOC = 7, BESS_LOW_F_LOW_SOC = 8,
    BESS_LOW_F_DROOP = 9
} BessState;
typedef struct { int active; double held_soc_mw; BessState state; } BessController;
typedef struct { double soc_mw, droop_mw, power_mw; int droop_active; } BessOutput;

BessConfig bess_default_config(void);
void bess_reset(BessController *controller);
/* Returns 0 on success, -1 for invalid arguments (state/output unchanged).
 * Positive MW = discharge; SOC is a fraction in [0, 1]. */
int bess_step(BessController *controller, const BessConfig *config,
              double frequency_hz, double soc, BessOutput *output);
#endif
