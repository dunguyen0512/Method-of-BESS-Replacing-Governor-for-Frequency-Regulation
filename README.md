# Method of BESS Replacing Governor for Frequency Regulation

C and Python reconstruction of the BESS frequency-regulation controller in
the paper below. The repo is build following the Paper
## Paper

Nguyen-Hoang, N.-D., et al. (2022). *Operation Method of Energy Storage System
Replacing Governor for Frequency Regulation of Synchronous Generator without
Reserve*. **Energies, 15**, 798. https://doi.org/10.3390/en15030798

The paper is CC BY 4.0. The PDF is excluded from Git; use the DOI for the source.

## Educational purpose and confidential study data

The original paper used a Korean power network. Its underlying network data
and grid structure are confidential and are excluded from this repository.

This project provides a simple educational version of the paper's BESS
operation method. The aim is to study frequency-event activation, droop
control and SOC management, and their interaction with a generic **aggregate
generator model** using illustrative parameters. Reproducing the Korean
network or its topology is outside this project's scope.

In the author's original work, the **aggregate generator model was built in
Python**, integrating generator and governor/turbine models, including GENROU
and a hydro model. Initial values were obtained from PSS/E, and the model
parameters were supplied by the project manager. That original code was lost;
the original integrated aggregate model has not been reconstructed here.

The current Python examples use artificial frequency inputs and an ideal
battery energy balance to demonstrate the BESS controller. They do not include
the lost generator-model integration, PSS/E initialization, or project-supplied
parameters. This background describes the original implementation, not a
capability of the current repository.

## Original C implementation in PSCAD/EMTDC

The author's original C controller was embedded in a **PSCAD function block**.
PSCAD generated the frequency signal from the simulated generator/network and
supplied it to the block. The block also received the initial SOC and control
settings needed for the paper's BESS model. During the simulation, controller
decisions used the current SOC of the battery model, initialized from that
initial SOC, together with the incoming frequency signal.

The intended signal path is:

```text
PSCAD generator/network -> frequency -> frequency-event latch / activation
                                                    |
Initial SOC -> BESS SOC calculation -> current SOC   |
                                    |               v
                                    +----> state machine and droop control
                                                    |
                                                    v
                                       BESS active-power reference
                                                    |
                                                    v
                                      PSCAD converter/battery model
```

The C implementation included a **latch for the frequency-event signal**.
Its role was to retain the event/activation indication used to enable the
control algorithm. The author confirmed the rule: **hold for 5 seconds after
detection, then re-evaluate**. This duration comes from the author's implementation
description, not a numerical setting supplied by the paper.

The author clarified that actual frequency can fluctuate around the threshold
and sensor signals can be delayed. The latch therefore captures a **high- or
low-frequency event indicator** to activate the BESS algorithm. It retains the
event indication, rather than freezing the numerical frequency measurement
used for droop calculation. In `simple_bess.py`, deadband return or an opposite
crossing does not interrupt the active 5-second hold. At expiry, an in-band
measurement clears the indicator; an out-of-band measurement captures the
current direction for another hold interval. Reset both latch variables at the
start of a simulation. Re-evaluation happens on the first sample at/after expiry.

During a hold the live droop contribution is limited to the captured direction:
high-frequency activation permits charging droop, low-frequency activation
permits discharging droop. If the measured frequency enters the deadband or
crosses the opposite threshold, that droop contribution becomes zero until
re-evaluation; the held SOC contribution remains. This direction-limiting
choice is explicit in `control_step()`. SOC emergency overrides still take priority.

This event latch is separate from holding the initial `P_SOC` contribution
during droop operation (Section 3.3.2).

**Current repository status:** both the C controller and functional Python
example include the 5-second frequency-event latch. C uses small numbered
functions, with comments following Fig. 6 states and Fig. 7 branches.
See [c/README.md](c/README.md) for the function guide and [test.md](test.md)
for a brief note about artificial frequency inputs and PSCAD adaptation.
The original PSCAD project, wrapper, port mapping and battery/SOC model are not
included. Initial SOC and energy capacity initialize the external battery
model; current SOC and simulation time are supplied to the controller.



## Quick start

For **seed-100 artificial frequency signals and an evaluation matrix**, run:

```powershell
py python/test_frequency_signals.py --base-hz 60 --output-dir results/frequency_tests_60hz
```

Choose `--base-hz 50` for a 50 Hz system. Each signal lasts 6000 s; thresholds
are +/-0.5 Hz. The default suite evaluates 16 profiles at five initial SOC
values, exports PNG figures, and writes numerical signals and the test matrix
as CSV. See [TEST_MATRIX.md](TEST_MATRIX.md) for scenarios, expected behavior,
noise settings and pass/fail criteria. This runner passes its nominal frequency
and threshold explicitly; it does not change the older Fig. 8 demo defaults.
These are software checks of the controller. For educational power-system
studies, a generic aggregate generator can represent generation/load imbalance
without the original Korean network data or topology. The guide describes
suitable equivalent disturbances and BESS power/energy measurements.

**Start with `python/simple_bess.py`** for the readable function-by-function
version. It has no controller classes, enums or configuration objects:

```powershell
py -m pip install -r requirements-plot.txt
py python/simple_bess.py --initial-soc 0.70 --droop-rate 0.05 --ess-power-mw 25 --ess-energy-mwh 6.25
```

Output: `results/simple_bess.png` only. SOC `0.70` means 70%; droop `0.05`
means 5% on the generator base. ESS size needs two values: PCS power in MW
and stored energy in MWh. The example uses the same assumed narrow center
band and frequency trace as the Figure 8 demo; edit the clearly labeled
constants at the top to change thresholds.

Read the functions in this order:

1. `frequency_input(time_s)` supplies the illustrative frequency trace.
2. `frequency_indicator(...)` detects high (+1), low (-1), or normal (0).
3. `latch_frequency(...)` holds the event direction for 5 seconds.
4. `select_state(...)` follows Fig. 7 using the retained indicator and current SOC.
5. `soc_power(...)` and `droop_power(...)` calculate the two power contributions.
6. `control_step(...)` combines them and retains the SOC contribution in droop.
7. `update_soc(...)` calculates the next SOC for the ideal battery example.
8. `simulate(...)` runs successive samples; `save_png(...)` exports the figure.

For direct Python use:

```python
from simple_bess import simulate, save_png

results = simulate(initial_soc=0.70, droop_rate=0.05,
                   ess_power_mw=25.0, ess_energy_mwh=6.25)
save_png(results, "results/my_test.png")
```

Each result row contains `(time_s, frequency_hz, soc, state, p_soc, p_droop, p_ess)`.
`held_soc_power` retains the SOC contribution, not the frequency signal.
`indicator` and `hold_until_s` retain event direction and latch expiry separately.
Use `--hold-seconds 5` to set the hold duration (default 5). The earlier
class-based interface remains available for existing tests; it and the earlier
`simulate_figure8.py` example do not include this new event latch.

To export three panels like **Figure 8** (frequency, SOC, and ESS power):

```powershell
py -m pip install -r requirements-plot.txt
py python/simulate_figure8.py
```

Open `results/figure8_state_machine.png`. This command exports PNG only.
This illustrative example uses a prescribed frequency disturbance and an ideal
6.25 MWh battery energy balance to calculate SOC. It is not a reproduction of
the original Fig. 8 data or a grid simulation. See [TESTING.md](TESTING.md).

Python 3.8+ (standard library only):

```sh
python python/bess_controller.py
python -m unittest discover -s tests -v
python python/run_cases.py examples/fig5_cases.csv
```

See [TESTING.md](TESTING.md) for a Windows walkthrough and creating more cases.
Python tests run without C by default. To enable the C comparison in PowerShell,
set `$env:BESS_TEST_C = "1"` before running unittest.

Optional standalone C99 demonstration with GCC (separate from PSCAD integration):

```sh
mkdir build
gcc -std=c99 -Wall -Wextra -pedantic c/bess_controller.c c/demo.c -lm -o build/bess_demo
./build/bess_demo
```

On Windows, run `./build/bess_demo.exe`. The C demo prints seven samples with
simulation time, latched indicator, state and power to demonstrate the hold.

## Figure 5 logic

The implementation now selects explicit numbered states by the **Fig. 7
flowchart**, with transitions observable as in **Fig. 6**. CSV exports include
`state`. Fig. 9's example sequence is tested as 6 -> 5 -> 9 -> 4 (then 5).

| State | Branch / action |
| --- | --- |
| 1 | High frequency, SOC not high: droop + held SOC contribution |
| 2 | High frequency, high SOC: emergency discharge |
| 3 | Deadband, low SOC: emergency charge |
| 4 | Deadband, medium-low SOC: recovery charge |
| 5 | Deadband, center SOC: zero power |
| 6 | Deadband, medium-high SOC: recovery discharge |
| 7 | Deadband, high SOC: emergency discharge |
| 8 | Low frequency, low SOC: emergency charge |
| 9 | Low frequency, SOC not low: droop + held SOC contribution |

On entering states 1/9, the SOC contribution is captured and then held while
remaining in droop states, as described in Section 3.3.2. Other states update
the recovery contribution and set droop power to zero. This refactor makes the
existing branch logic explicit; it does not invent an additional recovery latch.
The figure has incomplete/inconsistent equality branches and an apparent
Yes/No label typo; boundary conventions are documented below.

The **Figure 8 demo** uses separate illustrative ML=0.6499, MH=0.6501 settings
to show recovery to approximately 65%, as visible in that figure. They are
assumptions for this example, not recovered parameters. The reusable controller
class-based Python defaults remain 0.40/0.60. The functional Python example
and revised C defaults use 0.6499/0.6501. No recovery-target latch is introduced.

Positive power means **discharging into the grid**; negative means charging.
SOC is a fraction, frequency is Hz, and output power is MW.

| Frequency region | SOC condition | Action |
| --- | --- | --- |
| Above upper deadband | SOC <= H | Droop + held SOC power |
| Above upper deadband | SOC > H | Emergency-high discharge only |
| Inside deadband | Any | SOC recovery table below |
| Below lower deadband | SOC > L | Droop + held SOC power |
| Below lower deadband | SOC <= L | Emergency-low charge only |

| SOC region | Recovery power |
| --- | --- |
| SOC <= L | -0.15 PCS rating |
| L < SOC <= ML | -0.10 PCS rating |
| ML < SOC <= MH | 0 |
| MH < SOC <= H | +0.10 PCS rating |
| H < SOC | +0.15 PCS rating |

At droop activation, capture the recovery power for the **current measured SOC**.
Hold it while droop remains enabled, even if SOC crosses an interior threshold.
With the event latch, return to live SOC recovery when activation clears at
re-evaluation or an emergency override disables droop. The older class-based
Python interface instead uses instantaneous frequency. A direct frequency jump from one
droop side to the other retains the held value if neither sample disables droop.
Call `reset()` / `bess_reset()` when starting a new run. Keep configuration fixed
during a run, or reset after changing it. Measurements/SOC estimation are external.

## Units and reconstruction choices

For deviation `df = f - f_nominal`, remove the deadband width before applying
droop, as in Eq. (7):

```text
e_hz = df - deadband_hz     (high frequency)
e_hz = df + deadband_hz     (low frequency)
P_droop_MW = -P_generator_base_MW * e_hz / (f_nominal_Hz * R_generator)
P_ESS_MW = clamp(P_droop_MW + P_SOC_MW, -PCS_MW, +PCS_MW)
```

This explicitly normalizes Hz to per-unit frequency. Equivalently,
`R_ESS = R_generator * PCS_MW / P_generator_base_MW` from Eq. (5).
Do not apply the 5% generator droop directly on the 25 MW PCS base.

- Table 1 supplies 60 Hz, 5% generator droop, 25 MW PCS, 6.25 MWh energy,
  and a 612 MVA generator rating. Here 612 is the numerical active-power
  per-unit base; this does not assert a 612 MW operating point.
- **Earlier class-based Python defaults:** +/-0.02 Hz deadband and SOC
  boundaries 0.20/0.40/0.60/0.80. Revised C defaults use +/-0.5 Hz and
  0.20/0.6499/0.6501/0.80. These are assumptions/test settings, not numerical
  thresholds supplied by the paper. Set them explicitly for your application.
- Recovery magnitudes 15% and 10% come from Section 3.3; charging coefficients
  are negative under the explicit sign convention above.
- Exact deadband edges count as inside (1e-12 Hz roundoff tolerance).
  SOC threshold equality follows the table above, resolving inconsistent strict
  inequalities in the paper's figures/equations.
- Converter saturation and physical SOC=0/1 direction blocking are added guards.
  Reported `soc_mw` and `droop_mw` are contributions **before** these guards.
- The revised C and functional Python controllers include the author's
  5-second frequency-event latch. The older class-based Python interface has
  no event timer. Section 3.3.2 does not specify the numerical hold duration.
- Converter dynamics, efficiencies, battery dynamics, SOC integration, network
  faults and governor dynamics are outside this simple controller's scope.

For the earlier +/-0.02 Hz example, at 59.90 Hz a zero held SOC bias gives
`P_droop = -612 * (-0.10 + 0.02) / (60 * 0.05) = +16.32 MW`.
At SOC=0.65, the +2.5 MW recovery bias gives +18.82 MW total.

## Files and integration

- `c/bess_controller.h`, `c/bess_controller.c`: reusable core intended for a
  PSCAD wrapper, including frequency-event latch and SOC-bias memory.
- `c/demo.c`: standalone C example. Initialize state with `bess_reset()`.
- `python/bess_controller.py`: earlier instantaneous-frequency Python API.
- `tests/test_controller.py`: numerical, boundary and transition checks.
- `tests/test_c_controller.py`: timed C/functional-Python comparison.

Use one controller instance per BESS, supplying measured generator frequency
and SOC each sample. Convert measured angular speed with `f = omega / (2*pi)`
for electrical rad/s; mechanical shaft speed also requires pole-pair conversion.
This educational reference needs plant-specific validation before integration.

## Verification status

Fifteen Python tests and the original 19 CSV expectations passed. The artificial
frequency suite also passed 80 cases at 50 Hz and 80 cases at 60 Hz, with all
nine states covered at each base frequency. See [TEST_MATRIX.md](TEST_MATRIX.md).
The revised C code compiled with GCC using `-Wall -Wextra -Werror -pedantic`.
All 16 tests passed, including the C/functional-Python comparison at 50/60 Hz
(1200 samples per base, all nine states), and the standalone C demo ran.
This verifies the C controller core, not the missing PSCAD wrapper or original
integrated aggregate generator model.
