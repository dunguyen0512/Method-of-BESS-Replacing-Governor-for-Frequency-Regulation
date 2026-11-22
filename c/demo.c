#include "bess_controller.h"
#include <stdio.h>
int main(void) {
    const double samples[][2] = {{60,.7},{59.9,.65},{59.9,.5},{60,.5},{59.9,.1},{60.1,.9}};
    BessController controller;
    BessConfig config = bess_default_config();
    BessOutput out;
    unsigned int i;
    bess_reset(&controller);
    puts("frequency_hz,soc,soc_mw,droop_mw,power_mw,mode");
    for (i = 0; i < sizeof(samples)/sizeof(samples[0]); ++i) {
        if (bess_step(&controller, &config, samples[i][0], samples[i][1], &out)) return 1;
        printf("%.9f,%.9f,%.9f,%.9f,%.9f,%s\n", samples[i][0], samples[i][1],
               out.soc_mw, out.droop_mw, out.power_mw, out.droop_active ? "droop" : "soc");
    }
    return 0;
}
