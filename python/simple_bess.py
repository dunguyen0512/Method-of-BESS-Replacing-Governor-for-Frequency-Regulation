"""Readable, function-by-function BESS example. Run this file first."""
import argparse
from math import isfinite
from pathlib import Path

# Paper Table 1: generator base, nominal frequency.
NOMINAL_HZ = 60.0
GENERATOR_BASE_MW = 612.0

# Example assumptions, not recovered paper settings.
DEADBAND_HZ = 0.02
LOW_SOC = 0.20
MEDIUM_LOW_SOC = 0.6499
MEDIUM_HIGH_SOC = 0.6501
HIGH_SOC = 0.80


def frequency_input(time_s):
    """Example frequency trace. In PSCAD, use its measured frequency instead."""
    points = [(0, 60.0), (900, 59.98), (1700, 59.955),
              (2150, 59.98), (2300, 60.0)]
    for (start, f_start), (end, f_end) in zip(points, points[1:]):
        if time_s < end:
            return f_start + (f_end - f_start) * (time_s - start) / (end - start)
    return NOMINAL_HZ


def frequency_indicator(frequency_hz):
    """+1 = high frequency, -1 = low frequency, 0 = inside deadband."""
    deviation = frequency_hz - NOMINAL_HZ
    if deviation > DEADBAND_HZ + 1e-12:
        return 1
    if deviation < -DEADBAND_HZ - 1e-12:
        return -1
    return 0


def latch_frequency(time_s, frequency_hz, indicator, hold_until_s, hold_seconds=5.0):
    """Hold event direction for 5 s after detection, then re-evaluate.

    Pass both returned values into the next call. At expiry: reset if inside
    deadband, or capture the current direction for a new hold interval.
    Neither deadband return nor opposite crossing interrupts an active hold.
    """
    if not all(isfinite(x) for x in (time_s, frequency_hz, hold_until_s, hold_seconds)):
        raise ValueError("Latch inputs must be finite")
    if time_s < 0 or frequency_hz <= 0 or hold_seconds < 0 or indicator not in (-1,0,1):
        raise ValueError("Invalid latch time, frequency, duration or indicator")
    if indicator != 0 and time_s < hold_until_s:
        return indicator, hold_until_s
    indicator = frequency_indicator(frequency_hz)
    if indicator != 0:
        return indicator, time_s + hold_seconds
    return 0, time_s


def select_state(frequency_hz, soc, indicator=None):
    """Figure 7: check frequency first, then SOC. Return state 1 to 9."""
    if indicator is None:
        indicator = frequency_indicator(frequency_hz)
    if indicator == 1:
        if soc > HIGH_SOC:
            return 2
        return 1
    if indicator == -1:
        if soc <= LOW_SOC:
            return 8
        return 9
    if soc > HIGH_SOC:
        return 7
    if soc > MEDIUM_HIGH_SOC:
        return 6
    if soc > MEDIUM_LOW_SOC:
        return 5
    if soc > LOW_SOC:
        return 4
    return 3


def soc_power(soc, ess_power_mw):
    """SOC recovery power: negative charges, positive discharges."""
    if soc <= LOW_SOC:
        return -0.15 * ess_power_mw
    if soc <= MEDIUM_LOW_SOC:
        return -0.10 * ess_power_mw
    if soc <= MEDIUM_HIGH_SOC:
        return 0.0
    if soc <= HIGH_SOC:
        return 0.10 * ess_power_mw
    return 0.15 * ess_power_mw


def droop_power(frequency_hz, droop_rate):
    """Generator-base droop. Use 0.05 for 5%, output in MW."""
    deviation = frequency_hz - NOMINAL_HZ
    if deviation > DEADBAND_HZ:
        error_hz = deviation - DEADBAND_HZ
    elif deviation < -DEADBAND_HZ:
        error_hz = deviation + DEADBAND_HZ
    else:
        return 0.0
    return -GENERATOR_BASE_MW * error_hz / (NOMINAL_HZ * droop_rate)


def control_step(frequency_hz, soc, droop_rate, ess_power_mw, held_soc_power=None,
                 indicator=None):
    """One sample. Pass returned held_soc_power into the next call.

    None means droop was inactive. A number (including zero) is the SOC
    contribution held during states 1/9. The separate indicator argument comes
    from latch_frequency(). If omitted, use the instantaneous frequency region.
    """
    if not all(isfinite(x) for x in (frequency_hz, soc, droop_rate, ess_power_mw)):
        raise ValueError("Inputs must be finite")
    if frequency_hz <= 0 or not 0 <= soc <= 1 or droop_rate <= 0 or ess_power_mw <= 0:
        raise ValueError("Use positive frequency, droop and MW rating; SOC in [0,1]")
    if indicator is not None and indicator not in (-1,0,1):
        raise ValueError("Indicator must be -1, 0 or +1")
    state = select_state(frequency_hz, soc, indicator)
    p_soc = soc_power(soc, ess_power_mw)
    p_droop = 0.0
    if state == 1 or state == 9:
        if held_soc_power is None:
            held_soc_power = p_soc
        p_soc = held_soc_power
        p_droop = droop_power(frequency_hz, droop_rate)
        # Keep the held event's direction, but never freeze measured frequency.
        # If it returns inside deadband or crosses the other side, droop is 0
        # until the latch is re-evaluated. The held SOC bias remains unchanged.
        if state == 1:
            p_droop = min(0.0, p_droop)
        else:
            p_droop = max(0.0, p_droop)
    else:
        held_soc_power = None
    p_ess = max(-ess_power_mw, min(ess_power_mw, p_soc + p_droop))
    if (soc == 0 and p_ess > 0) or (soc == 1 and p_ess < 0):
        p_ess = 0.0
    return state, p_soc, p_droop, p_ess, held_soc_power


def update_soc(soc, power_mw, dt_s, ess_energy_mwh):
    """Ideal battery energy balance; positive power reduces SOC."""
    return max(0.0, min(1.0, soc - power_mw * dt_s / (3600 * ess_energy_mwh)))


def simulate(initial_soc=0.70, droop_rate=0.05, ess_power_mw=25.0,
             ess_energy_mwh=6.25, dt_s=1.0, duration_s=6000.0, hold_seconds=5.0):
    """User inputs: initial SOC, generator droop, PCS MW and battery MWh."""
    values = (initial_soc, droop_rate, ess_power_mw, ess_energy_mwh, dt_s, duration_s)
    if not all(isfinite(x) for x in values) or not 0 <= initial_soc <= 1 or min(values[1:]) <= 0:
        raise ValueError("SOC must be in [0,1]; other simulation inputs must be positive and finite")
    if not isfinite(hold_seconds) or hold_seconds < 0:
        raise ValueError("Hold time must be finite and nonnegative")
    soc = initial_soc
    held_soc_power = None
    time_s = 0.0
    indicator = 0
    hold_until_s = 0.0
    results = []
    while True:
        frequency_hz = frequency_input(time_s)
        indicator, hold_until_s = latch_frequency(
            time_s, frequency_hz, indicator, hold_until_s, hold_seconds)
        state, p_soc, p_droop, p_ess, held_soc_power = control_step(
            frequency_hz, soc, droop_rate, ess_power_mw, held_soc_power, indicator)
        step_s = min(dt_s, duration_s - time_s)
        if step_s > 0:
            p_ess = min(p_ess, soc * ess_energy_mwh * 3600 / step_s)
            p_ess = max(p_ess, -(1 - soc) * ess_energy_mwh * 3600 / step_s)
        results.append((time_s, frequency_hz, soc, state, p_soc, p_droop, p_ess))
        if step_s <= 0:
            break
        soc = update_soc(soc, p_ess, step_s, ess_energy_mwh)
        time_s = min(duration_s, time_s + step_s)
    return results


def save_png(results, filename):
    """Three panels like Fig. 8. Export PNG only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    time, frequency, soc, state, p_soc, p_droop, p_ess = zip(*results)
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True, constrained_layout=True)
    fig.suptitle("Illustrative Figure 8 example - assumed inputs and SOC thresholds")
    axes[0].plot(time, frequency, label="Frequency")
    axes[0].axhline(NOMINAL_HZ + DEADBAND_HZ, color="gray", linestyle="--")
    axes[0].axhline(NOMINAL_HZ - DEADBAND_HZ, color="gray", linestyle="--", label="Deadband")
    axes[0].set_ylabel("(a) Frequency [Hz]")
    axes[0].ticklabel_format(axis="y", useOffset=False)
    axes[1].plot(time, [100 * value for value in soc], label="SOC")
    axes[1].set_ylabel("(b) SOC [%]")
    axes[2].plot(time, p_ess, label="P_ESS")
    axes[2].plot(time, p_soc, "--", label="P_SOC")
    axes[2].plot(time, p_droop, ":", label="P_droop")
    axes[2].set_ylabel("(c) ESS power [MW]")
    axes[2].set_xlabel("Time [s]")
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.legend()
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, format="png", dpi=200)
    plt.close(fig)
    print(f"Saved: {filename}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial-soc", type=float, default=0.70)
    parser.add_argument("--droop-rate", type=float, default=0.05)
    parser.add_argument("--ess-power-mw", type=float, default=25.0)
    parser.add_argument("--ess-energy-mwh", type=float, default=6.25)
    parser.add_argument("--hold-seconds", type=float, default=5.0)
    parser.add_argument("--output", default="results/simple_bess.png")
    args = parser.parse_args()
    try:
        results = simulate(args.initial_soc, args.droop_rate,
                           args.ess_power_mw, args.ess_energy_mwh,
                           hold_seconds=args.hold_seconds)
        save_png(results, args.output)
    except ImportError:
        parser.exit(2, "Install Matplotlib: py -m pip install -r requirements-plot.txt\n")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()
