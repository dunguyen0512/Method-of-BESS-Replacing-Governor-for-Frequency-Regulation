"""The functional controller's event latch, separate from its SOC bias hold."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from simple_bess import latch_frequency, control_step, simulate


class SimpleBessTests(unittest.TestCase):
    def test_hold_then_reevaluate(self):
        indicator, expiry = latch_frequency(10,59.9,0,0)
        self.assertEqual((indicator,expiry),(-1,15))
        self.assertEqual(latch_frequency(11,60,indicator,expiry),(-1,15))
        self.assertEqual(latch_frequency(14.9,60.1,indicator,expiry),(-1,15))
        self.assertEqual(latch_frequency(15,60,indicator,expiry),(0,15))
        self.assertEqual(latch_frequency(15,60.1,indicator,expiry),(1,20))
        self.assertEqual(latch_frequency(15,59.9,indicator,expiry),(-1,20))

    def test_live_droop_and_direction(self):
        first = control_step(59.9,.65,.05,25,indicator=-1)
        second = control_step(59.95,.65,.05,25,first[4],indicator=-1)
        self.assertLess(second[2],first[2])
        self.assertEqual(control_step(60,.65,.05,25,first[4],indicator=-1)[0],9)
        self.assertEqual(control_step(60.1,.65,.05,25,first[4],indicator=-1)[2],0)
        self.assertEqual(control_step(59.9,.65,.05,25,indicator=1)[2],0)
        # SOC emergency overrides have priority even while the event is held.
        self.assertEqual(control_step(59.9,.1,.05,25,indicator=-1)[0],8)
        self.assertEqual(control_step(60.1,.9,.05,25,indicator=1)[0],2)

    def test_parameters_and_energy(self):
        rows = simulate(initial_soc=.7,droop_rate=.04,ess_power_mw=10,
                        ess_energy_mwh=3,dt_s=1,duration_s=2000)
        self.assertEqual(rows[0][2],.7)
        for first,second in zip(rows,rows[1:]):
            self.assertAlmostEqual(second[2],first[2]-first[6]/(3600*3))
            self.assertLessEqual(abs(first[6]),10)


if __name__ == "__main__":
    unittest.main()
