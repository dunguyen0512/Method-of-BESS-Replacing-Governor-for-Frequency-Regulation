# Testing the Python controller

See [test.md](test.md) for the input-frequency scope and PSCAD adaptation note.

## Recommended simple version

```powershell
cd C:\Users\Desktop\BESS_GOV
py -m pip install -r requirements-plot.txt
py python/simple_bess.py --initial-soc 0.70 --droop-rate 0.05 --ess-power-mw 25 --ess-energy-mwh 6.25
```

Open `results/simple_bess.png`. The code uses small functions with explicit
inputs and no classes. This version includes the author's confirmed rule:
capture high/low frequency activation, hold for 5 seconds, then re-evaluate.
For another test, change the four numeric arguments and use
`--output results/test2.png`. SOC is a fraction; droop is the generator-base
fraction; ESS power is MW and energy is MWh. See the README for function order.
The sections below describe the earlier test interfaces, which remain available.

## Export a chart like Figure 8

Run from the main project folder (not its `python` subfolder):

```powershell
cd C:\Users\Desktop\BESS_GOV
py -m pip install -r requirements-plot.txt
py python/simulate_figure8.py
```

Use `python` instead of `py` if that is your working launcher. Matplotlib is
needed only for plotting. Open `results/figure8_state_machine.png` for the three panels:
frequency with deadband, SOC in percent, and P_SOC / P_droop / P_ESS in MW.
The figure command exports PNG only.

This new demo calculates SOC from output power using an **ideal battery**:
`SOC_next = SOC - P_ESS_MW * dt_seconds / (3600 * energy_MWh)`.
The paper's 6.25 MWh capacity is used, with assumed 70% initial SOC, unity
efficiency and a 1-second time step. Frequency is a prescribed piecewise-linear dip from
60 to 59.955 Hz, crossing the lower deadband around 900 and 2150 s,
recovering to 60 Hz by 2300 s; it is not calculated
from a network. These are illustrative settings, not recovered original data.
The revised demo uses an assumed +/-0.02 Hz deadband and L=20%, H=80%, with
a narrow center band ML=64.99%, MH=65.01%, to illustrate the approximately
65% plateaus in Fig. 8. These thresholds are not recovered paper parameters.
The reusable controller defaults are unchanged. Change `frequency_at()` in `python/simulate_figure8.py` to design
another frequency event. Compare smaller time steps when studying boundaries.

```powershell
py python/simulate_figure8.py --initial-soc 0.75 --dt 0.5 --output results/my_figure8
```

For your own prescribed frequency/SOC CSV, export a separate chart per case:

```powershell
py python/run_cases.py examples/my_cases.csv --output results/my_results.csv --plot-dir results/my_charts
```

Each independent case gets its own chart, so unrelated experiments are not
joined as a continuous time trace. A useful time plot needs multiple samples
in the same case; the short Fig. 5 examples mainly test individual points.

## 1. Open PowerShell in the project folder

```powershell
cd C:\Users\Desktop\BESS_GOV
python --version
python python/bess_controller.py
```

Python 3.8+ is sufficient; no pip packages are needed. If your Python launcher
uses `py`, substitute `py` for `python` in these commands. If neither works,
select an installed Python interpreter in your editor or install Python.
The compiler installation is separate from Python.

## 2. Run automated Python checks

```powershell
python -m unittest discover -s tests -v
```

Expected: 15 Python tests pass, with the optional C comparison skipped.
These check SOC boundaries, recovery magnitudes, droop calculation, held SOC
bias, emergency overrides, saturation, reset, and invalid inputs.

## 3. Run the editable example cases

```powershell
python python/run_cases.py examples/fig5_cases.csv --output results/fig5_results.csv
```

Expected: **19 samples, 13 cases; 19 expectations, 0 failures**.
Open `results/fig5_results.csv` in Excel or a text editor. Positive `power_mw`
is discharge; negative is charge. `soc_mw` and `droop_mw` are contributions
before converter saturation. `passed` compares final power with the optional
expected value, within 0.000001 MW. A failed expectation exits with code 1;
invalid inputs exit with code 2.

The cases exercise Fig. 5 and Eqs. (7)-(8):

| Case | Expected behavior with default parameters |
| --- | --- |
| EL / PEL | At 60 Hz, charge at -3.75 / -2.5 MW |
| center | At 60 Hz, zero power |
| PEH / EH | At 60 Hz, discharge at +2.5 / +3.75 MW |
| underfrequency | 59.90 Hz, SOC 0.5: +16.32 MW |
| overfrequency | 60.10 Hz, SOC 0.5: -16.32 MW |
| low_soc_override | Low frequency and SOC 0.1: charge at -3.75 MW |
| high_soc_override | High frequency and SOC 0.9: discharge at +3.75 MW |
| held_bias | +2.5 MW SOC bias remains fixed during droop despite SOC crossing MH |
| fig9_sequence | Illustrates the Fig. 9 state sequence 6 -> 5 -> 9 -> 4 |
| positive_limit / negative_limit | Final power clips to +/-25 MW |

The held-bias case illustrates the principle in Fig. 8; the frequency, SOC and
time values here are invented test inputs, not digitized values from that plot.
Likewise, the Fig. 9 sequence uses illustrative samples rather than a dynamic
simulation. Default SOC thresholds and deadband are assumptions documented
in the README, not numerical settings reported in the paper.

## 4. Create your own tests

Copy `examples/fig5_cases.csv` to `examples/my_cases.csv`. Each row is one
measured/prescribed sample:

```csv
case,time_s,frequency_hz,soc,expected_power_mw
my_event,0,60,0.7,2.5
my_event,1,59.9,0.65,18.82
my_event,2,59.9,0.5,18.82
my_event,3,60,0.5,0
another_event,0,60.1,0.5,-16.32
```

```powershell
python python/run_cases.py examples/my_cases.csv --output results/my_results.csv
```

- Use **SOC 0.7 for 70%**, not 70. Frequency is in Hz and time in seconds.
- Keep the same case name for successive samples of one event. The held bias
  persists between those rows. Times must increase within a case.
- Give each independent experiment a new name; it starts with fresh state.
- Leave `expected_power_mw` empty when exploring an unknown result.
- Test just below, exactly at, and just above L, ML, MH, H and both deadband edges.
  Also test returning to the deadband and reaching emergency SOC during droop.

To change parameters, copy/edit `examples/config.json` and run:

```powershell
python python/run_cases.py examples/my_cases.csv --config examples/config.json --output results/custom_results.csv
```

Change expected powers when changing parameters. Droop `0.05` means 5%.
For manual checking, at 59.90 Hz the deadband-adjusted deviation is
`59.90 - 60 + 0.02 = -0.08 Hz`, so droop power is
`-612 * (-0.08) / (60 * 0.05) = +16.32 MW`. Add the held SOC bias,
then apply the +/-25 MW limit.

## 5. Educational scope and original study data

The paper studied a Korean power network. Its underlying network data and grid
structure are confidential and are not included in this repository.

This repository is a simplified version for study: its purpose is to explain
the BESS state machine, frequency-event latch, droop control and SOC management,
and how these controls can operate with a generic **aggregate generator model**.
Such a model can represent the combined generator response through equivalent
inertia, damping and power balance, using illustrative parameters rather than
the Korean network data or topology.

The current CSV runner accepts supplied frequency and SOC samples. The Python
simulation examples calculate SOC with an ideal battery energy balance while
using artificial frequency inputs. A closed-loop aggregate-generator simulation
is a separate extension; it is not yet implemented in these examples.
