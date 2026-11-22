# Testing the Python controller

## 1. Open PowerShell in the project folder

```powershell
cd C:\Users\ndnguyen\Desktop\BESS_GOV
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

Expected: four Python tests pass, with the optional C comparison skipped.
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

## 5. Understand what these tests establish

This runner evaluates the controller against frequency and SOC that **you supply**.
Time labels order samples; it does not integrate battery energy or compute grid
frequency. SOC changes in the CSV are prescribed rather than calculated.
It therefore tests the Fig. 5 logic, not the network performance in Figs. 13-15.
The paper's generator trip, three-phase fault and line trip results require a
generator/network dynamic model and converter/battery models. A frequency trace
exported from such a model can be used as input here, but this runner alone
cannot establish the paper's frequency nadirs or governor comparison.
