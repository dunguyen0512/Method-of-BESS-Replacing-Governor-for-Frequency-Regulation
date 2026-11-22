import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from simple_bess import control_step,latch_frequency


@unittest.skipUnless(os.environ.get('BESS_TEST_C')=='1' and shutil.which('gcc'),
                     'Set BESS_TEST_C=1 to enable C compilation and comparison')
class CControllerTests(unittest.TestCase):
    def test_timed_c_matches_python_both_bases(self):
        build=ROOT/'build'
        build.mkdir(exist_ok=True)
        executable=build/('c_driver.exe' if sys.platform=='win32' else 'c_driver')
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-pedantic',
                        str(ROOT/'c/bess_controller.c'),str(ROOT/'tests/c_driver.c'),
                        '-lm','-o',str(executable)],check=True)
        for base in [50,60]:
            samples=[]
            for i in range(1200):
                time=i/10
                # Explicit software checks: boundary crossings, opposite events,
                # expiry, and all SOC regions including physical end stops.
                offset=[0,.5,.8,-.8,-.5,0,-.8,.8][(i//10)%8]
                soc=[0,.1,.2,.200001,.4,.6499,.65,.6501,.7,.8,.9,1][(i//80)%12]
                samples.append((time,base+offset,soc))
            text=''.join(f'{t} {f} {soc}\n' for t,f,soc in samples)
            # A repeated timestamp and invalid SOC must leave state/output intact.
            text+=f'{samples[-1][0]} {base} .5\n120 {base} -1\n'
            result=subprocess.run([str(executable),str(base)],input=text,text=True,
                                  capture_output=True,check=True)
            lines=result.stdout.splitlines()
            self.assertEqual(len(lines),len(samples)+2)
            indicator,expiry,held=0,0,None
            covered=set()
            for (time,f,soc),line in zip(samples,lines):
                indicator,expiry=latch_frequency(time,f,indicator,expiry,5,base,.5)
                state,ps,pd,p,held=control_step(f,soc,.05,25,held,indicator,base,.5)
                covered.add(state)
                fields=list(map(float,line.split()))
                self.assertEqual(fields[:3],[0,state,indicator])
                for actual,expected in zip(fields[3:],[expiry,ps,pd,p]):
                    self.assertAlmostEqual(actual,expected,places=9)
            self.assertEqual(covered,set(range(1,10)))
            for line in lines[-2:]:
                fields=line.split()
                self.assertEqual(fields[0],'-1')
                self.assertEqual(fields[1:],lines[-3].split()[1:])


if __name__=='__main__':
    unittest.main()
