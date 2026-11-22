/* Test-only stdin/stdout bridge, portable across 32/64-bit C/Python installs. */
#include "../c/bess_controller.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    BessConfig settings = bess_default_config();
    BessController memory;
    BessOutput output = {0};
    double time_s, frequency_hz, soc;
    int result;
    if (argc == 2) settings.nominal_hz = atof(argv[1]);
    bess_reset(&memory);
    while (scanf("%lf %lf %lf", &time_s, &frequency_hz, &soc) == 3) {
        result = bess_step(&memory, &settings, time_s, frequency_hz, soc, &output);
        printf("%d %d %d %.17g %.17g %.17g %.17g\n", result,
               memory.state, memory.frequency_indicator, memory.hold_until_s,
               output.soc_mw, output.droop_mw, output.power_mw);
    }
    return 0;
}
