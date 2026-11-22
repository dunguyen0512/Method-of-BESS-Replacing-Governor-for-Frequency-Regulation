"""Export one Figure 8-style chart per case (requires Matplotlib)."""
from pathlib import Path


def plot_case(rows, config, output_stem, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    time = [float(r["time_s"]) for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True,
                             constrained_layout=True)
    fig.suptitle(title, fontsize=12)
    axes[0].plot(time, [float(r["frequency_hz"]) for r in rows],
                 color="#2155a3", label="Frequency")
    for sign, label in [(1, "Upper deadband"), (-1, "Lower deadband")]:
        axes[0].axhline(config.nominal_hz + sign * config.deadband_hz,
                        color="0.45", linestyle="--" if sign == 1 else ":", label=label)
    axes[0].set_ylabel("(a) Frequency [Hz]")
    axes[0].ticklabel_format(axis="y", useOffset=False)
    axes[1].plot(time, [100 * float(r["soc"]) for r in rows],
                 color="#2155a3", label="SOC")
    axes[1].set_ylabel("(b) SOC [%]")
    for key, label, color, style in [
        ("soc_mw", r"$P_{SOC}$", "#298044", "--"),
        ("droop_mw", r"$P_{droop}$", "#c34a29", ":"),
        ("power_mw", r"$P_{ESS}$", "#2155a3", "-")]:
        axes[2].plot(time, [float(r[key]) for r in rows],
                     label=label, color=color, linestyle=style, linewidth=1.8)
    axes[2].set_ylabel("(c) ESS power [MW]")
    axes[2].set_xlabel("Time [s]")
    for ax in axes:
        ax.grid(True, alpha=.25)
        ax.legend(loc="best", fontsize=8)
    stem = Path(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    for extension in ["png", "pdf", "svg"]:
        fig.savefig(str(stem) + "." + extension, dpi=200)
    plt.close(fig)
    print(f"Charts: {stem}.png / .pdf / .svg")


def plot_csv(csv_path, config, directory):
    import csv
    groups = {}
    with open(csv_path, newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            groups.setdefault(row["case"], []).append(row)
    for index, (name, rows) in enumerate(groups.items(), 1):
        # Case names are chart labels, never filesystem paths.
        plot_case(rows, config, Path(directory) / f"case_{index:03d}", name)
