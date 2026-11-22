"""Run prescribed frequency/SOC traces; use a separate controller per case."""
import argparse
import csv
import json
from math import isfinite
from pathlib import Path

from bess_controller import Config, Controller


def run(input_path, output_path, config):
    controllers, last_time, results = {}, {}, []
    with open(input_path, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"case", "time_s", "frequency_hz", "soc"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Input needs columns: case,time_s,frequency_hz,soc")
        for line, row in enumerate(reader, 2):
            try:
                case = row["case"].strip()
                time = float(row["time_s"])
                if not case or not isfinite(time) or time < 0:
                    raise ValueError("Case must be named; time must be finite and nonnegative")
                if case in last_time and time <= last_time[case]:
                    raise ValueError("Time must increase within each case")
                controller = controllers.setdefault(case, Controller(config))
                frequency, soc = float(row["frequency_hz"]), float(row["soc"])
                out = controller.step(frequency, soc)
                last_time[case] = time
                expected = row.get("expected_power_mw", "").strip()
                passed = "" if not expected else abs(out.power_mw - float(expected)) <= 1e-6
                results.append(dict(case=case, time_s=time, frequency_hz=frequency,
                                    soc=soc, soc_mw=out.soc_mw, droop_mw=out.droop_mw,
                                    power_mw=out.power_mw, mode=out.mode,
                                    expected_power_mw=expected, passed=passed))
            except (ValueError, TypeError) as error:
                raise ValueError(f"Input line {line}: {error}") from error
    if not results:
        raise ValueError("Input has no samples")
    destination = Path(output_path)
    if Path(input_path).resolve() == destination.resolve():
        raise ValueError("Input and output paths must differ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    failures = sum(row["passed"] is False for row in results)
    checked = sum(row["passed"] != "" for row in results)
    print(f"{len(results)} samples, {len(controllers)} cases; {checked} expectations, {failures} failures")
    print(f"Results: {destination.resolve()}")
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input CSV")
    parser.add_argument("--output", default="results/results.csv")
    parser.add_argument("--config", help="Optional JSON containing Config overrides")
    args = parser.parse_args()
    try:
        overrides = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
        raise SystemExit(1 if run(args.input, args.output, Config(**overrides)) else 0)
    except (ValueError, TypeError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")
