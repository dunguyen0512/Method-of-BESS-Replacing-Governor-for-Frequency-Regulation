/* These are software-check samples, not a physical network trajectory.
 * PSCAD normally supplies simulation time, frequency, and current battery SOC. */
#include "bess_controller.h"
#include <stdio.h>

int main(void)
{
    /* time [s], frequency [Hz], current SOC [fraction] */
    const double samples[][3] = {
        {0.0, 60.0, 0.70},   /* State 6: recovery discharge. */
        {10.0, 59.2, 0.65},  /* State 9: LOW captured until 15 s. */
        {11.0, 60.0, 0.60},  /* State 9 held; live droop now zero. */
        {12.0, 60.8, 0.60},  /* Opposite crossing: retain LOW. */
        {15.0, 60.8, 0.60},  /* Expiry: capture HIGH until 20 s. */
        {20.0, 60.0, 0.60},  /* State 4: recovery charge. */
        {21.0, 59.2, 0.10}   /* State 8: emergency charge. */
    };
    BessConfig settings = bess_default_config();
    BessController memory;
    BessOutput output;
    unsigned int i;
    bess_reset(&memory);     /* Initialize ONCE, outside timestep loop. */
    puts("time_s,frequency_hz,soc,indicator,state,p_soc_mw,p_droop_mw,p_ess_mw");
    for (i = 0; i < sizeof(samples)/sizeof(samples[0]); ++i) {
        if (bess_step(&memory, &settings, samples[i][0], samples[i][1],
                      samples[i][2], &output) != 0) return 1;
        printf("%.1f,%.3f,%.3f,%d,%d,%.6f,%.6f,%.6f\n",
               samples[i][0], samples[i][1], samples[i][2],
               output.frequency_indicator, output.state, output.soc_mw,
               output.droop_mw, output.power_mw);
    }
    return 0;
}
