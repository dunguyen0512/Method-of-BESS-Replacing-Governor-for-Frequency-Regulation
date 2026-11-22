"""Illustrative Fig. 8-style SOC response to a prescribed frequency event."""
import argparse
import csv
from math import isfinite
from pathlib import Path

from bess_controller import Config, Controller
from plot_results import plot_case


def frequency_at(time):
    # Approximate Fig. 8's event timing, not digitized original data.
    points = [(0,60.0),(900,59.98),(1700,59.955),(2150,59.98),(2300,60.0)]
    for (t0,f0),(t1,f1) in zip(points, points[1:]):
        if time < t1:
            return f0 + (f1-f0) * (time-t0) / (t1-t0)
    return 60.0


def simulate(dt=1.0, duration=6000.0, initial_soc=.70, energy_mwh=6.25):
    if not all(isfinite(x) for x in (dt, duration, initial_soc, energy_mwh)):
        raise ValueError("Simulation parameters must be finite")
    if dt <= 0 or duration <= 0 or energy_mwh <= 0 or not 0 <= initial_soc <= 1:
        raise ValueError("Use positive dt, duration and energy; SOC must be in [0,1]")
    # Fig. 8 visually returns to ~65% from both directions. Use an explicitly
    # assumed narrow center band here, without adding a recovery latch.
    config = Config(medium_low=.6499, medium_high=.6501)
    controller = Controller(config)
    soc, time, rows = initial_soc, 0.0, []
    while True:
        frequency = frequency_at(time)
        out = controller.step(frequency, soc)
        step = min(dt, duration - time)
        power = out.power_mw
        if step > 0:
            # Limit interval power to available energy/headroom before integration.
            power = min(power, soc * energy_mwh * 3600 / step)
            power = max(power, -(1 - soc) * energy_mwh * 3600 / step)
        rows.append(dict(time_s=time, frequency_hz=frequency, soc=soc,
                         soc_mw=out.soc_mw, droop_mw=out.droop_mw,
                         power_mw=power, mode=out.mode, state=int(out.state)))
        if step <= 0:
            break
        # Ideal unity-efficiency energy balance; forward Euler / zero-order hold.
        soc = max(0.0, min(1.0, soc - power * step / (3600 * energy_mwh)))
        time = min(duration, time + step)
    return config, rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dt", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=6000.0)
    parser.add_argument("--initial-soc", type=float, default=.70)
    parser.add_argument("--energy-mwh", type=float, default=6.25)
    parser.add_argument("--output", default="results/figure8_state_machine", help="Output filename stem")
    args = parser.parse_args()
    try:
        config, rows = simulate(args.dt, args.duration, args.initial_soc, args.energy_mwh)
        stem = Path(args.output)
        stem.parent.mkdir(parents=True, exist_ok=True)
        with Path(str(stem) + ".csv").open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        plot_case(rows, config, stem, "Illustrative Figure 8-style example (not original paper data)")
        print(f"Data: {stem}.csv")
    except ImportError:
        parser.exit(2, "Install plotting dependency: py -m pip install -r requirements-plot.txt\n")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")
