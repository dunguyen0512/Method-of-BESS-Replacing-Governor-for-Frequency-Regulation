import random
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from simple_bess import frequency_indicator, latch_frequency, control_step
from test_frequency_signals import generate_signals, signal_offset, evaluate_case


class FrequencyMatrixTests(unittest.TestCase):
    def test_reproducibility_duration_and_base(self):
        time,signals=generate_signals(60,1,.03)
        time2,signals2=generate_signals(50,1,.03)
        self.assertEqual(time,time2)
        self.assertEqual((time[0],time[-1],len(time)),(0,6000,6001))
        self.assertAlmostEqual(signals['normal_noise'][0],60+random.Random(100).gauss(0,.03))
        self.assertEqual(signals,generate_signals(60,1,.03)[1])
        for name in signals:
            for a,b in zip(signals[name],signals2[name]):
                self.assertAlmostEqual(a-b,10,places=12)

    def test_threshold_and_soc_boundaries_both_bases(self):
        for base in [50,60]:
            for frequency in [base-.5,base,base+.5]:
                self.assertEqual(frequency_indicator(frequency,base,.5),0)
            self.assertEqual(frequency_indicator(base+.500001,base,.5),1)
            self.assertEqual(frequency_indicator(base-.500001,base,.5),-1)
            for frequency,soc,state in [(base+.8,.65,1),(base+.8,.9,2),
                 (base,.2,3),(base,.6499,4),(base,.65,5),(base,.6501,5),
                 (base,.7,6),(base,.8,6),(base,.9,7),
                 (base-.8,.2,8),(base-.8,.200001,9)]:
                result=control_step(frequency,soc,.05,25,nominal_hz=base,threshold_hz=.5)
                self.assertEqual(result[0],state)
            self.assertAlmostEqual(control_step(base-.6,.65,.05,25,
                nominal_hz=base,threshold_hz=.5)[2],612*.1/(base*.05))

    def test_pulse_duration_vs_five_second_hold(self):
        for direction in [-1,1]:
            for length in [4.9,5,5.1]:
                indicator,expiry=latch_frequency(1000,60+direction*.8,0,0,5,60,.5)
                self.assertEqual((indicator,expiry),(direction,1005))
                # No early reset even if pulse has ended before the hold.
                self.assertEqual(latch_frequency(1004.99,60,indicator,expiry,5,60,.5),
                                 (direction,1005))
                frequency=60+direction*.8 if length>5 else 60
                actual=latch_frequency(1005,frequency,indicator,expiry,5,60,.5)
                self.assertEqual(actual,(direction,1010) if length>5 else (0,1005))

    def test_sensor_delay_and_nonzero_held_bias(self):
        times=[i*.1 for i in range(301)]
        signal=[60+(-.8 if 10<=t<11 else 0) for t in times]
        summary,rows=evaluate_case(times,signal,.65,60,.05,25,6.25,2)
        self.assertEqual(summary['status'],'PASS')
        activation=next(row[0] for row in rows if row[7]==-1)
        self.assertAlmostEqual(activation,12)
        self.assertEqual(signal_offset('held_bias',10),.8)
        signal=[60+signal_offset('held_bias',t) for t in times]
        summary,rows=evaluate_case(times,signal,.7,60,.05,25,6.25)
        self.assertEqual(summary['status'],'PASS')
        self.assertTrue(all(row[4]==2.5 for row in rows if row[0]>=10))


if __name__=='__main__':
    unittest.main()
