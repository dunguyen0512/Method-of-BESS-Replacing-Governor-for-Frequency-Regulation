# C controller function guide

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
