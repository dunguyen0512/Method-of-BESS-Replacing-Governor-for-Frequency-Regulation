import ctypes
import math
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from bess_controller import Controller, Config


class ControllerTests(unittest.TestCase):
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

    @unittest.skipUnless(shutil.which("gcc"), "GCC required for cross-language check")
    def test_c_python_agree(self):
        class CConfig(ctypes.Structure):
            _fields_ = [(n,ctypes.c_double) for n in vars(Config())]
        class State(ctypes.Structure):
            _fields_ = [("active",ctypes.c_int),("held",ctypes.c_double)]
        class Out(ctypes.Structure):
            _fields_ = [("soc",ctypes.c_double),("droop",ctypes.c_double),
                        ("power",ctypes.c_double),("active",ctypes.c_int)]
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        dll = build / ("bess_test.dll" if sys.platform == "win32" else "bess_test.so")
        subprocess.run(["gcc","-std=c99","-Wall","-Wextra","-pedantic","-shared",
                        "-fPIC",str(ROOT/"c/bess_controller.c"),"-lm","-o",str(dll)],check=True)
        lib = ctypes.CDLL(str(dll))
        lib.bess_step.argtypes = [ctypes.POINTER(State),ctypes.POINTER(CConfig),
                                 ctypes.c_double,ctypes.c_double,ctypes.POINTER(Out)]
        lib.bess_step.restype = ctypes.c_int
        config = CConfig(*vars(Config()).values())
        state, output, python = State(), Out(), Controller()
        # Sequential sweep also checks transitions and frozen biases.
        for frequency in [60,59.98,60.02,59.9,60.1,59,61,60]:
            for soc in [0,.1,.2,.200001,.4,.5,.6,.8,.800001,1]:
                expected = python.step(frequency,soc)
                self.assertEqual(lib.bess_step(ctypes.byref(state),ctypes.byref(config),
                                 frequency,soc,ctypes.byref(output)),0)
                for a,b in [(output.soc,expected.soc_mw),(output.droop,expected.droop_mw),
                            (output.power,expected.power_mw)]:
                    self.assertAlmostEqual(a,b,places=10)
                self.assertEqual(bool(output.active),expected.mode == "droop")
        self.assertEqual(lib.bess_step(ctypes.byref(state),ctypes.byref(config),
                         60,math.nan,ctypes.byref(output)),-1)


if __name__ == "__main__":
    unittest.main()
