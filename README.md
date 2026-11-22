# Method of BESS Replacing Governor for Frequency Regulation

Simple C99 and Python implementations reconstructed from **Figure 5**, with
Sections 3.2-3.3, Eqs. (5), (7)-(8), and Figs. 6-8 used to clarify the logic.
This is a new reconstruction, not the recovered original C source or the full
PSCAD/EMTDC network model. The examples exercise the controller with prescribed
frequency/SOC inputs; they do not reproduce the paper's network results.

## Paper

Nguyen-Hoang, N.-D., et al. (2022). *Operation Method of Energy Storage System
Replacing Governor for Frequency Regulation of Synchronous Generator without
Reserve*. **Energies, 15**, 798. https://doi.org/10.3390/en15030798

The paper is CC BY 4.0. The PDF is excluded from Git; use the DOI for the source.

## Quick start

Python 3.8+ (standard library only):

```sh
python python/bess_controller.py
python -m unittest discover -s tests -v
```

C99 with GCC (Windows, Linux or macOS):

```sh
mkdir build
gcc -std=c99 -Wall -Wextra -pedantic c/bess_controller.c c/demo.c -lm -o build/bess_demo
./build/bess_demo
```

On Windows, run `./build/bess_demo.exe`. Both demos print the same six samples
as CSV, including held SOC power and emergency overrides.

## Figure 5 logic

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
- No hold timer is assumed: Section 3.3.2 mentions a service-dependent duration
  but gives no value. Droop ends on deadband return or the emergency override.
- Converter dynamics, efficiencies, battery dynamics, SOC integration, network
  faults and governor dynamics are outside this simple controller's scope.

For example, at 59.90 Hz, a zero held SOC bias gives
`P_droop = -612 * (-0.10 + 0.02) / (60 * 0.05) = +16.32 MW`.
At SOC=0.65, the +2.5 MW recovery bias gives +18.82 MW total.

## Files and integration

- `c/bess_controller.h`, `c/bess_controller.c`: reusable controller API.
- `c/demo.c`: standalone C example. Initialize state with `bess_reset()`.
- `python/bess_controller.py`: equivalent Python API and runnable example.
- `tests/test_controller.py`: numerical, boundary, transition and C/Python checks.

Use one controller instance per BESS, supplying measured generator frequency
and SOC each sample. Convert measured angular speed with `f = omega / (2*pi)`
for electrical rad/s; mechanical shaft speed also requires pole-pair conversion.
This educational reference needs plant-specific validation before integration.

## Verification status

The four Python behavior tests passed in the reconstruction environment.
The C build and C/Python comparison could not run: the installed MinGW GCC
failed to start with Windows error 623 (Illegal System DLL Relocation), and
execution outside the sandbox was declined. The cross-language test is provided
for running on a working GCC installation; C compilation is not yet verified.
