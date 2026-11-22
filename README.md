# Method of BESS Replacing Governor for Frequency Regulation

C and Python reconstruction of the BESS frequency-regulation controller in
the paper below. The control decisions follow the **Fig. 6 state machine** and
**Fig. 7 flowchart**, with Fig. 5 and Eqs. (5), (7)-(8) defining droop and SOC
management. Python provides standalone tests and a PNG example.

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
control algorithm. The author describes a frequency-rise timing example of
**less than 5 seconds**. Whether that timing is a trigger window or a minimum
persistence condition, and the latch reset/release conditions, still need to
be specified before reconstructing that part of the original implementation.
The 5-second example comes from the author's implementation description; it
is not a numerical setting supplied by the paper.

This event latch is separate from holding the initial `P_SOC` contribution
during droop operation (Section 3.3.2). Retaining an activation flag does not
by itself specify that the numerical frequency measurement is frozen.

**Current repository status:** the C files contain a reusable controller core
and a standalone demonstration. The original PSCAD project, function-block
wrapper, port mapping, SOC model, and frequency-event latch are not included.
The present core takes current frequency and current SOC at each call; it has
no initial-SOC input or elapsed-time input. A PSCAD wrapper must initialize the
SOC model, preserve controller/latch state between simulation steps, and supply
the block's activation logic. The current examples therefore do not reproduce
the complete original PSCAD implementation or its network results.

## Paper

Nguyen-Hoang, N.-D., et al. (2022). *Operation Method of Energy Storage System
Replacing Governor for Frequency Regulation of Synchronous Generator without
Reserve*. **Energies, 15**, 798. https://doi.org/10.3390/en15030798

The paper is CC BY 4.0. The PDF is excluded from Git; use the DOI for the source.

## Quick start

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

On Windows, run `./build/bess_demo.exe`. Both demos print the same six samples
as CSV, including held SOC power and emergency overrides.

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
defaults remain 0.40/0.60. No unreported 65% recovery-target latch is introduced.

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
Return to live SOC recovery when frequency returns inside the deadband or a
directional emergency override disables droop. A direct frequency jump from one
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
- **Assumed examples:** symmetric +/-0.02 Hz deadband and SOC thresholds
  L=0.20, ML=0.40, MH=0.60, H=0.80. The paper gives no numerical values
  for these settings. Change `Config` / `BessConfig` for your application.
- Recovery magnitudes 15% and 10% come from Section 3.3; charging coefficients
  are negative under the explicit sign convention above.
- Exact deadband edges count as inside (1e-12 Hz roundoff tolerance).
  SOC threshold equality follows the table above, resolving inconsistent strict
  inequalities in the paper's figures/equations.
- Converter saturation and physical SOC=0/1 direction blocking are added guards.
  Reported `soc_mw` and `droop_mw` are contributions **before** these guards.
- The reconstructed core has no frequency-event latch or hold timer. Section
  3.3.2 mentions a service-dependent duration but gives no value. In the current
  core, droop ends on deadband return or the emergency override. The author's
  original PSCAD implementation also used activation-latch logic, described
  above, which remains to be reconstructed.
- Converter dynamics, efficiencies, battery dynamics, SOC integration, network
  faults and governor dynamics are outside this simple controller's scope.

For example, at 59.90 Hz, a zero held SOC bias gives
`P_droop = -612 * (-0.10 + 0.02) / (60 * 0.05) = +16.32 MW`.
At SOC=0.65, the +2.5 MW recovery bias gives +18.82 MW total.

## Files and integration

- `c/bess_controller.h`, `c/bess_controller.c`: reusable core intended for a
  PSCAD function-block wrapper; the wrapper and activation latch are pending.
- `c/demo.c`: standalone C example. Initialize state with `bess_reset()`.
- `python/bess_controller.py`: equivalent Python API and runnable example.
- `tests/test_controller.py`: numerical, boundary, transition and C/Python checks.

Use one controller instance per BESS, supplying measured generator frequency
and SOC each sample. Convert measured angular speed with `f = omega / (2*pi)`
for electrical rad/s; mechanical shaft speed also requires pole-pair conversion.
This educational reference needs plant-specific validation before integration.

## Verification status

Seven Python tests and 19 CSV expectations passed in the reconstruction environment.
The C build and C/Python comparison could not run: the installed MinGW GCC
failed to start with Windows error 623 (Illegal System DLL Relocation), and
execution outside the sandbox was declined. The cross-language test is provided
for running on a working GCC installation; C compilation is not yet verified.
