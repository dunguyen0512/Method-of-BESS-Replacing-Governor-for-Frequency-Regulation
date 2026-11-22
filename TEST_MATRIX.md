# Artificial frequency test matrix

The test runner is `python/test_frequency_signals.py`. Functions are separated
into waveform creation, noise generation, case evaluation and PNG plotting.
It exercises the functional controller in `python/simple_bess.py`.

## Run

From the main project folder:

```powershell
py -m pip install -r requirements-plot.txt
py python/test_frequency_signals.py --base-hz 60 --output-dir results/frequency_tests_60hz
py python/test_frequency_signals.py --base-hz 50 --output-dir results/frequency_tests_50hz
```

Each run uses:

- Duration **6000 s**, including samples at 0 and 6000 s.
- Default time step **0.1 s**: 60,001 samples per signal.
- Thresholds **base - 0.5 Hz** and **base + 0.5 Hz**. Exact equality is inside.
- A local `random.Random(100)` generator: Gaussian noise, mean 0 Hz, default
  standard deviation **0.03 Hz**. The same noise array is added to each waveform
  for fair comparison. Exact-edge tests deliberately disable noise. Gaussian
  noise is unbounded; this standard deviation is an example assumption.
- Initial SOC values **10%, 40%, 65%, 70%, 90%**, one in each configured region.
  This gives **16 frequency profiles x 5 initial SOC values = 80 cases** per base.
  `--initial-soc` adds a custom value if it is not already in that set.
- 5-second event-indicator hold, 5% generator-base droop, 25 MW PCS,
  6.25 MWh ideal battery, and generator numerical base 612 MW.
- SOC thresholds from the current functional example: L=20%, ML=64.99%,
  MH=65.01%, H=80%. These remain example assumptions, not recovered paper values.

Change input parameters without editing functions:

```powershell
py python/test_frequency_signals.py --base-hz 50 --noise-std-hz 0.05 --initial-soc 0.75 --droop-rate 0.04 --ess-power-mw 20 --ess-energy-mwh 5 --output-dir results/custom_tests
```

Use `--dt 0.05` for finer timing. The step must divide 6000 s and the specified
2, 4.9, 5 and 5.1 s intervals exactly. Noise is generated per sample; changing
the time step changes its time-domain realization even with the same seed.

## Frequency profiles and expected behavior

Offsets below are relative to the selected base. Gaussian noise is added
unless the row explicitly states otherwise. Event interval ends are exclusive.

| Profile | Artificial input | Expected behavior |
| --- | --- | --- |
| normal_noise | Base plus noise | SOC recovery while measurement is inside thresholds |
| high_step | +0.8 Hz, 1000-2000 s | High indicator; charging droop unless high-SOC override applies |
| low_step | -0.8 Hz, 1000-2000 s | Low indicator; discharging droop unless low-SOC override applies |
| short_high | +0.8 Hz, 1000-1001 s | High indicator remains held for 5 s; live droop becomes zero on deadband return |
| short_low | -0.8 Hz, 1000-1001 s | Low indicator remains held for 5 s; live droop becomes zero on deadband return |
| pulse_lengths | Alternating pulses, 4.9/5.0/5.1 s | Below/equal/above hold-time behavior; re-capture if still outside at expiry |
| high_chatter | +0.5 Hz plus 1 Hz sine of amplitude 0.015 Hz, 1000-2000 s | Noise crosses upper threshold; latch prevents an early activation reset |
| low_chatter | -0.5 Hz plus same sine, 1000-2000 s | Noise crosses lower threshold; latch prevents an early activation reset |
| reversal | Smooth half-cosine transitions: 0 Hz at 998 s, +0.8 at 1000, -0.8 at 1004, +0.8 at 1008, 0 at 1012 | Frequency stays continuous; opposite crossing cannot change the retained direction before expiry |
| ramp | 0 -> +1 -> 0 -> -1 -> 0 Hz, 1000-5000 s | Both activation directions, deadband re-entry and SOC response |
| oscillation | 0.8 Hz amplitude, 120 s period, 1000-5000 s | Repeated activations and recovery; bounded power/SOC |
| large_events | -2 Hz 1000-2500, +2 Hz 3000-4500 s | PCS saturation, available-energy limits and SOC emergency overrides |
| upper_edge | Exactly +0.5 Hz, no noise | No frequency-event activation |
| lower_edge | Exactly -0.5 Hz, no noise | No frequency-event activation |
| sensor_delay | Low 1000-2000, high 3000-4000 s; measurement delayed 2 s | Controller activates on delayed measurement, not on inaccessible physical frequency |
| held_bias | +0.8 Hz, 10-2000 s | Early activation captures nonzero recovery bias for appropriate initial SOC |

The delayed-sensor example is a pure transport delay, not a sensor estimator
or delay compensation algorithm. The 2-second delay is an assumed stress case.

The reversal waveform has continuous frequency and continuous first derivative,
with zero slope at the specified time points. Its maximum absolute rate of
change before measurement noise is approximately **0.63 Hz/s**. This is a severe
synthetic excursion, not a validated network response. The noise is interpreted
as measurement noise. The other step/pulse profiles remain deliberate abrupt
logic tests; they should not be interpreted as physical grid-frequency dynamics.

## Evaluation criteria

The runner audits **every sample** using explicit formulas and timing rules:

| Check | Pass condition |
| --- | --- |
| Event latch | Retains direction until expiry; then re-evaluates against +/-0.5 Hz |
| State selection | Matches Fig. 7 branches using retained indicator and current SOC |
| SOC recovery | Correct 0%, +/-10%, +/-15% of PCS rating outside droop |
| Held SOC bias | Constant during successive droop states, refreshed on re-entry |
| Live droop | Uses measured deviation beyond threshold and selected nominal frequency |
| Droop direction | Cannot reverse against the retained high/low activation direction |
| Converter limit | Command is clipped to +/-PCS MW |
| SOC end stops | Empty battery cannot discharge; full battery cannot charge |
| Battery energy | Applied interval power respects available energy/headroom; SOC matches the ideal energy balance |
| State coverage | Combined matrix visits all nine states; missing coverage causes nonzero exit status |

These checks compare the implementation with stated control requirements;
they are not evidence that the reconstructed settings match the original
PSCAD model or that closed-loop grid performance is acceptable.

Separate automated tests cover exact SOC boundaries, exact frequency edges
and neighboring values, both nominal frequencies, 4.9/5/5.1-second pulses,
noise reproducibility, sensor delay and a nonzero held SOC bias:

```powershell
py -m unittest discover -s tests -v
```

## Outputs

- `frequency_signals.png`: overview of all 16 full-duration inputs.
- `test_matrix.png`: pass/fail table, profile versus initial SOC.
- `short_high.png`, `reversal.png`, `sensor_delay.png`: focused 995-1020 s views
  of noisy input/delayed measurement, activation indicator, SOC and power.
  The reversal plot also shows the smooth underlying waveform before noise.
- `held_bias.png`: full-duration response at 70% initial SOC to show held bias.
- `frequency_inputs.csv`: time and the 16 physical-frequency signals; reusable
  input data, with noise already included. The delayed measurement is formed
  by the evaluator for the sensor-delay case.
- `test_matrix.csv`: parameters, pass/fail, failed rule names, states visited,
  minimum/final SOC, power range and raw/latched activation-change counts.

All figures are PNG only. CSVs are numerical test inputs and the evaluation
matrix. A raw change counts a change in instantaneous frequency region;
a latched change counts a change of the retained event indicator. Zero droop
power can coexist with a held indicator when the measurement returns inside.

The runner exits 0 if every case passes and all states are covered, 1 if a
check fails or coverage is incomplete, and 2 for invalid CLI arguments or a
missing plotting dependency. Generated files stay under ignored `results/`.

This finite suite covers the listed operating regions and transition classes.
It cannot exhaust every continuous frequency/SOC trajectory or reproduce the
paper's fault studies: frequency is prescribed, rather than generated by a
closed-loop network model.

## Verified default runs

Both 50 Hz and 60 Hz runs passed all **80 cases** and visited states 1-9.
The additional automated suite passed **15 Python tests**; the optional C
comparison was skipped. In the seeded 60 Hz high-threshold chatter example,
the instantaneous frequency-region indicator changed 4740 times, while the
held indicator changed 178 times. This measures the specified latch behavior;
it does not imply that live droop power is held constant or smoothed.
