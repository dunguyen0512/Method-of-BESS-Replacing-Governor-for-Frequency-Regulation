import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from bess_controller import Controller, Config, State


class ControllerTests(unittest.TestCase):
    def test_all_nine_flowchart_states(self):
        samples = [(60.1,.5,1),(60.1,.9,2),(60,.1,3),(60,.3,4),
                   (60,.5,5),(60,.7,6),(60,.9,7),(59.9,.1,8),(59.9,.5,9)]
        for frequency,soc,state in samples:
            self.assertEqual(int(Controller().step(frequency,soc).state),state)

    def test_figure9_transitions(self):
        c = Controller()
        states = [c.step(f,s).state for f,s in [(60,.7),(60,.5),(59.9,.5),(60,.3),(60,.5)]]
        self.assertEqual(states,[6,5,9,4,5])

    def test_figure8_example_energy_and_states(self):
        from simulate_figure8 import simulate
        config, rows = simulate()
        transitions = []
        for row in rows:
            if not transitions or row['state'] != transitions[-1]:
                transitions.append(row['state'])
        self.assertEqual(transitions,[6,5,9,4,5])
        for first, second in zip(rows,rows[1:]):
            expected = first['soc'] - first['power_mw'] * (second['time_s']-first['time_s']) / 22500
            self.assertAlmostEqual(second['soc'],expected,places=12)
        self.assertTrue(all(row['power_mw'] == 0 for row in rows[3500:]))
        self.assertAlmostEqual(rows[-1]['soc'],.65,places=3)

    def test_soc_regions_and_edges(self):
        for soc, expected in [(0,-3.75),(.2,-3.75),(.3,-2.5),(.4,-2.5),
                              (.5,0),(.6,0),(.7,2.5),(.8,2.5),(1,3.75)]:
            self.assertEqual(Controller().step(60,soc).power_mw, expected)

    def test_droop_and_hold(self):
        c = Controller()
        self.assertAlmostEqual(c.step(59.9,.65).power_mw,18.82)
        self.assertEqual(c.step(59.9,.5).soc_mw,2.5)
        self.assertEqual(c.step(60,.5).power_mw,0)
        self.assertAlmostEqual(c.step(60.1,.5).power_mw,-16.32)
        c.reset()
        self.assertEqual(c.step(59.9,.5).soc_mw,0)

    def test_overrides_and_limits(self):
        c = Controller()
        self.assertEqual(c.step(59,.2).power_mw,-3.75)
        self.assertEqual(c.step(61,.81).power_mw,3.75)
        self.assertEqual(c.step(59,.5).power_mw,25)
        self.assertEqual(c.step(61,.5).power_mw,-25)
        self.assertEqual(c.step(59,1).power_mw,25)
        self.assertEqual(c.step(61,0).power_mw,-25)
        for f in [59.98,60.02]:
            self.assertEqual(Controller().step(f,.5).mode,"soc")

    def test_validation(self):
        for f,s in [(math.nan,.5),(60,math.inf),(0,.5),(60,-.1),(60,1.1)]:
            with self.assertRaises(ValueError): Controller().step(f,s)
        for kwargs in [{"droop":0},{"high":.3},{"pcs_mw":math.inf}]:
            with self.assertRaises(ValueError): Config(**kwargs)



if __name__ == "__main__":
    unittest.main()
