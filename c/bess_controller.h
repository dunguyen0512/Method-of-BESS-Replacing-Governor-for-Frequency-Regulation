#ifndef BESS_CONTROLLER_H
#define BESS_CONTROLLER_H

/* Units: seconds, Hz, MW, SOC fraction. Positive MW = discharge. */
typedef struct {
    double nominal_hz, deadband_hz, generator_base_mw, pcs_mw, droop;
    double low, medium_low, medium_high, high;
    double hold_seconds;
} BessConfig;

/* One persistent memory instance per PSCAD BESS block. */
typedef struct {
    int droop_active;
    double held_soc_mw;
    int state;
    int frequency_indicator; /* +1 high, -1 low, 0 normal */
    double hold_until_s;
    double last_time_s;
} BessController;

typedef struct {
    double soc_mw, droop_mw, power_mw;
    int droop_active, frequency_indicator, state;
} BessOutput;

BessConfig bess_default_config(void);
void bess_reset(BessController *memory);
int bess_detect_frequency(double frequency_hz, const BessConfig *settings);
int bess_latch_frequency(double time_s, int detected, double hold_seconds,
                         BessController *memory);
int bess_select_state(int indicator, double soc, const BessConfig *settings);
double bess_soc_power(double soc, const BessConfig *settings);
double bess_droop_power(double frequency_hz, int state, const BessConfig *settings);
double bess_limit_power(double power_mw, double soc, double pcs_mw);

/* Main PSCAD entry: reset once, then call once per increasing sample time.
 * Pass CURRENT battery SOC. Initial SOC initializes the PSCAD battery model.
 * Return 0 on success; -1 on invalid inputs (memory/output unchanged).
 * Helper functions assume valid inputs; this entry point checks them. */
int bess_step(BessController *memory, const BessConfig *settings,
              double time_s, double frequency_hz, double soc, BessOutput *output);
#endif
