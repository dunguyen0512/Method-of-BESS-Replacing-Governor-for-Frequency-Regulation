# Test input frequency

The code currently uses **artificial frequency signals** to test the BESS
state machine, frequency-event latch, droop control and SOC management.
The tester can select a 50 Hz or 60 Hz base frequency. The artificial-frequency
test suite uses +/-0.5 Hz thresholds, 6000-second signals and seed-100 noise.
See [TESTING.md](TESTING.md) for commands and [TEST_MATRIX.md](TEST_MATRIX.md)
for the test cases.

When using PSCAD, the user can supply frequency from the simulated generator
or use a frequency/signal block to generate the input frequency.
The C code must be adapted to the PSCAD component syntax, the C/Fortran
interface, and the installed PSCAD and compiler versions. The current C files
are standalone reference code, not a ready-to-import PSCAD component.

The original paper used a Korean power network whose underlying data and
grid structure are confidential and excluded here. This repository provides
a simplified educational example of BESS operation without those data.
