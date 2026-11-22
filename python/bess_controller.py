"""Simple reconstruction of Fig. 5 and Eqs. (7)-(8), Energies 15 (2022) 798."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Config:
    nominal_hz: float = 60.0
    deadband_hz: float = 0.02  # Example assumption, not specified in the paper.
    generator_base_mw: float = 612.0  # Numerical MVA base used for active-power pu.
    pcs_mw: float = 25.0
    droop: float = 0.05
    low: float = 0.20
    medium_low: float = 0.40
    medium_high: float = 0.60
    high: float = 0.80

    def __post_init__(self):
        if not all(isfinite(v) for v in vars(self).values()):
            raise ValueError("Parameters must be finite")
        if min(self.nominal_hz, self.generator_base_mw, self.pcs_mw, self.droop) <= 0:
            raise ValueError("Ratings, frequency and droop must be positive")
        if not 0 <= self.deadband_hz < self.nominal_hz:
            raise ValueError("Invalid deadband")
        if not 0 < self.low < self.medium_low < self.medium_high < self.high < 1:
            raise ValueError("SOC thresholds must be ordered within (0, 1)")


@dataclass(frozen=True)
class Output:
    soc_mw: float
    droop_mw: float
    power_mw: float
    mode: str


class Controller:
    def __init__(self, config=Config()):
        self.config = config
        self.reset()

    def reset(self):
        self.active = False
        self.held_soc_mw = 0.0

    def recovery_power(self, soc):
        c = self.config
        if soc <= c.low:
            return -0.15 * c.pcs_mw
        if soc <= c.medium_low:
            return -0.10 * c.pcs_mw
        if soc <= c.medium_high:
            return 0.0
        if soc <= c.high:
            return 0.10 * c.pcs_mw
        return 0.15 * c.pcs_mw

    def step(self, frequency_hz, soc):
        """Positive MW discharges; SOC is a fraction. Call once per sample."""
        if not isfinite(frequency_hz) or frequency_hz <= 0 or not isfinite(soc) or not 0 <= soc <= 1:
            raise ValueError("Expected positive finite Hz and SOC in [0, 1]")
        c = self.config
        # Inclusive deadband boundaries, with a tiny tolerance for roundoff.
        delta = frequency_hz - c.nominal_hz
        high_f = delta > c.deadband_hz + 1e-12
        low_f = delta < -c.deadband_hz - 1e-12
        enabled = (high_f and soc <= c.high) or (low_f and soc > c.low)
        recovery = self.recovery_power(soc)
        if enabled:
            if not self.active:
                self.held_soc_mw = recovery
            recovery = self.held_soc_mw
            error = delta - c.deadband_hz if high_f else delta + c.deadband_hz
            droop = -c.generator_base_mw * error / (c.nominal_hz * c.droop)
            mode = "droop"
        else:
            droop = 0.0
            mode = "soc"
        self.active = enabled
        power = max(-c.pcs_mw, min(c.pcs_mw, recovery + droop))
        # Added physical end-stop protection; Fig. 5 itself has no 0/1 clamp.
        if (soc == 0 and power > 0) or (soc == 1 and power < 0):
            power = 0.0
        return Output(recovery, droop, power, mode)


if __name__ == "__main__":
    controller = Controller()
    print("frequency_hz,soc,soc_mw,droop_mw,power_mw,mode")
    for frequency, soc in [(60, .7), (59.9, .65), (59.9, .5), (60, .5), (59.9, .1), (60.1, .9)]:
        out = controller.step(frequency, soc)
        print(f"{frequency},{soc},{out.soc_mw:.9f},{out.droop_mw:.9f},{out.power_mw:.9f},{out.mode}")
