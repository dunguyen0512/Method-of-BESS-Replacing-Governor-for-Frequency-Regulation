# C function blocks for PSCAD integration

Read `bess_controller.c` in numbered function order:

| Function | Paper/control role |
| --- | --- |
| `bess_default_config` | Ratings, droop, thresholds and hold duration |
| `bess_reset` | Initialize persistent memory once |
| `bess_detect_frequency` | Fig. 7 upper/lower frequency decisions |
| `bess_latch_frequency` | Author's 5-second event-indicator hold |
| `bess_select_state` | Fig. 7 branches, state numbers from Fig. 6 |
| `bess_soc_power` | Eq. (8), SOC recovery contribution |
| `bess_droop_power` | Eq. (7), live-frequency droop in states 1/9 |
| `bess_limit_power` | Added PCS rating and SOC end-stop limits |
| `bess_step` | Main block: call functions in order; hold SOC bias during droop |

There are two separate memories: the frequency-event indicator is held for
5 seconds; the initial SOC power contribution is held throughout successive
droop states. Numerical frequency is never frozen.

## Call sequence

During simulation initialization:

```c
BessConfig settings = bess_default_config();
BessController memory;
BessOutput output;
settings.nominal_hz = 60.0;   /* Or 50.0. */
settings.deadband_hz = 0.5;
settings.pcs_mw = 25.0;
settings.droop = 0.05;       /* Generator-base droop: 5%. */
settings.hold_seconds = 5.0;
bess_reset(&memory);
```

Keep settings and memory alive between samples, one instance per BESS.
Initialize PSCAD's battery model with initial SOC (e.g. 0.70) and energy
capacity (e.g. 6.25 MWh); those belong to the external battery/SOC model.

Once per increasing control-sample time:

```c
int result = bess_step(&memory, &settings,
                       time_s, measured_frequency_hz, current_soc, &output);
if (result == 0) {
    /* Connect output.power_mw to the BESS active-power reference.
     * Expose output.state and output.frequency_indicator for checking. */
}
```

Positive MW discharges; negative MW charges. Pass CURRENT SOC, not the initial
value on every call. Adapt ports, storage, calling convention, initialization
and MW/pu conversion in your PSCAD component; this is a C call example, not a
ready-to-import PSCAD block. Handle a nonzero return in that wrapper.
Repeated/decreasing time or invalid inputs return -1 without changing memory
or output. Reset before restarting or changing configuration. Sample once
per control step rather than repeatedly during solver iterations.

High/low activation cannot change before hold expiry. At expiry normal clears
the indicator; high/low begins another hold. Emergency SOC states 2/8 still
override droop. Live droop is limited to the retained direction: it becomes
zero inside deadband or on an opposite measurement. The held SOC bias may
remain nonzero. This direction guard is an explicit latch integration choice.

Default SOC boundaries 20/64.99/65.01/80% are illustrative. The requested test
threshold +/-0.5 Hz differs from the earlier Python Figure 8 example.

## Verification

From the repository root (create `build` first if needed):

```powershell
gcc -std=c99 -Wall -Wextra -Werror -pedantic c/bess_controller.c c/demo.c -lm -o build/bess_demo.exe
./build/bess_demo.exe
$env:BESS_TEST_C = "1"
py -m unittest discover -s tests -v
```

The demo supplies labeled software samples, not physical network events.
The optional C test compares 1200 samples at each of 50 and 60 Hz with the
functional Python implementation, visiting all nine states and testing both
holds, boundaries, power limits, SOC end stops and rejection of invalid calls.
It uses a standalone executable, so 32-bit GCC works with 64-bit Python.
