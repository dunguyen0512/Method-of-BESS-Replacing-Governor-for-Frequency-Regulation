"""Seed-100 artificial frequency signals and a BESS evaluation matrix."""
import argparse
import csv
import math
from pathlib import Path
import random

from simple_bess import (control_step, latch_frequency, update_soc,
                         LOW_SOC, MEDIUM_LOW_SOC, MEDIUM_HIGH_SOC, HIGH_SOC)

DURATION_S = 6000.0
THRESHOLD_HZ = 0.5
SEED = 100

# Offsets are in Hz relative to the tester's selected 50/60 Hz base.
PROFILES = [
    ("normal_noise", "Noise inside deadband; SOC recovery only"),
    ("high_step", "High event 1000-2000 s; charging droop or high-SOC override"),
    ("low_step", "Low event 1000-2000 s; discharging droop or low-SOC override"),
    ("short_high", "1 s high pulse; indicator retained for 5 s"),
    ("short_low", "1 s low pulse; indicator retained for 5 s"),
    ("pulse_lengths", "High/low pulses of 4.9, 5.0 and 5.1 s"),
    ("high_chatter", "Noise around upper threshold; test activation retention"),
    ("low_chatter", "Noise around lower threshold; test activation retention"),
    ("reversal", "Opposite crossings during a hold; switch only at expiry"),
    ("ramp", "Slow ramp crosses both thresholds in both directions"),
    ("oscillation", "Repeated high/low excursions and SOC transitions"),
    ("large_events", "Large +/-2 Hz events; converter saturation and SOC limits"),
    ("upper_edge", "Exactly upper threshold; no event (noise intentionally off)"),
    ("lower_edge", "Exactly lower threshold; no event (noise intentionally off)"),
    ("sensor_delay", "Low/high events measured after a 2 s sensor delay"),
    ("held_bias", "Event starts at 10 s to capture nonzero SOC recovery bias"),
]


def signal_offset(name, time_s):
    """Deterministic event waveform; noise is added separately."""
    if name in ("high_step", "low_step", "sensor_delay", "held_bias"):
        start = 10 if name=="held_bias" else 1000
        if start <= time_s < 2000:
            return -0.8 if name in ("low_step", "sensor_delay") else 0.8
        if name == "sensor_delay" and 3000 <= time_s < 4000:
            return 0.8
    if name == "short_high" and 1000 <= time_s < 1001:
        return 0.8
    if name == "short_low" and 1000 <= time_s < 1001:
        return -0.8
    if name == "pulse_lengths":
        for start, length, sign in [(1000,4.9,1),(2000,5.0,-1),(3000,5.1,1),
                                     (4000,4.9,-1),(4500,5.0,1),(5000,5.1,-1)]:
            if start <= time_s < start + length:
                return sign * 0.8
    if name in ("high_chatter", "low_chatter") and 1000 <= time_s < 2000:
        sign = 1 if name == "high_chatter" else -1
        return sign * 0.5 + 0.015 * math.sin(2 * math.pi * time_s)
    if name == "reversal":
        if 1000 <= time_s < 1002 or 1007 <= time_s < 1012:
            return 0.8
        if 1002 <= time_s < 1007:
            return -0.8
    if name == "ramp":
        points = [(0,0),(1000,0),(2000,1),(3000,0),(4000,-1),(5000,0),(6000,0)]
        for (t0,f0),(t1,f1) in zip(points,points[1:]):
            if t0 <= time_s < t1:
                return f0 + (f1-f0) * (time_s-t0) / (t1-t0)
    if name == "oscillation" and 1000 <= time_s < 5000:
        return 0.8 * math.sin(2 * math.pi * (time_s-1000) / 120)
    if name == "large_events":
        if 1000 <= time_s < 2500:
            return -2.0
        if 3000 <= time_s < 4500:
            return 2.0
    if name == "upper_edge":
        return 0.5
    if name == "lower_edge":
        return -0.5
    return 0.0


def generate_signals(base_hz=60, dt_s=0.1, noise_std_hz=0.03):
    """Common seed-100 Gaussian noise gives fair comparisons between profiles."""
    rng = random.Random(SEED)
    count = round(DURATION_S / dt_s)
    times = [round(i * dt_s,10) for i in range(count+1)]
    noise = [rng.gauss(0,noise_std_hz) for _ in times]
    signals = {}
    for name, description in PROFILES:
        noisy = name not in ("upper_edge", "lower_edge")
        signals[name] = [base_hz + signal_offset(name,t) + (n if noisy else 0)
                         for t,n in zip(times,noise)]
    return times, signals


def evaluate_case(times, signal, initial_soc, base_hz, droop_rate, ess_power_mw,
                  ess_energy_mwh, delay_s=0):
    """Run a fresh controller; audit latch, state, bias, power and energy rules."""
    indicator, expiry, held, soc = 0, 0.0, None, initial_soc
    states, failures, rows = set(), set(), []
    dt_s = times[1]-times[0]
    delay_steps = round(delay_s / dt_s)
    previous_droop = False
    previous_bias = 0.0
    raw_changes = latched_changes = 0
    previous_raw = previous_indicator = 0
    for i,t in enumerate(times):
        measured = signal[max(0,i-delay_steps)]
        delta = measured-base_hz
        raw = 1 if delta > .5+1e-12 else -1 if delta < -.5-1e-12 else 0
        old_indicator, old_expiry = indicator, expiry
        indicator, expiry = latch_frequency(t,measured,indicator,expiry,5,base_hz,.5)
        # Independent timing oracle, not another call to the latch function.
        expected_indicator = old_indicator if old_indicator and t < old_expiry else raw
        expected_expiry = old_expiry if old_indicator and t < old_expiry else t+(5 if raw else 0)
        if indicator != expected_indicator or abs(expiry-expected_expiry)>1e-9:
            failures.add("latch")
        state, ps, pd, command, held = control_step(
            measured,soc,droop_rate,ess_power_mw,held,indicator,base_hz,.5)
        states.add(state)
        expected_state = (2 if soc>HIGH_SOC else 1) if indicator==1 else (
            (8 if soc<=LOW_SOC else 9) if indicator==-1 else
            7 if soc>HIGH_SOC else 6 if soc>MEDIUM_HIGH_SOC else
            5 if soc>MEDIUM_LOW_SOC else 4 if soc>LOW_SOC else 3)
        if state != expected_state:
            failures.add("state")
        active = state in (1,9)
        fraction = -.15 if soc<=LOW_SOC else -.10 if soc<=MEDIUM_LOW_SOC else (
            0 if soc<=MEDIUM_HIGH_SOC else .10 if soc<=HIGH_SOC else .15)
        expected_bias = previous_bias if active and previous_droop else fraction*ess_power_mw
        if abs(ps-expected_bias)>1e-9:
            failures.add("SOC bias")
        excess = max(0,delta-.5) if state==1 else min(0,delta+.5) if state==9 else 0
        expected_droop = -612*excess/(base_hz*droop_rate)
        if abs(pd-expected_droop)>1e-8:
            failures.add("droop")
        expected_command = max(-ess_power_mw,min(ess_power_mw,expected_bias+expected_droop))
        if (soc==0 and expected_command>0) or (soc==1 and expected_command<0):
            expected_command=0
        if abs(command-expected_command)>1e-8:
            failures.add("power")
        step = times[i+1]-t if i+1<len(times) else 0
        actual = command
        if step:
            actual = max(-(1-soc)*ess_energy_mwh*3600/step,
                         min(command,soc*ess_energy_mwh*3600/step))
        rows.append((t,measured,soc,state,ps,pd,actual,indicator,signal[i]))
        if step:
            next_soc = update_soc(soc,actual,step,ess_energy_mwh)
            expected_soc = soc-actual*step/(3600*ess_energy_mwh)
            if abs(next_soc-expected_soc)>1e-10 or not 0<=next_soc<=1:
                failures.add("energy")
            soc=next_soc
        raw_changes += raw != previous_raw
        latched_changes += indicator != previous_indicator
        previous_raw, previous_indicator = raw, indicator
        previous_bias, previous_droop = ps, active
    summary = dict(initial_soc=initial_soc, status="FAIL" if failures else "PASS",
                   failed_checks="; ".join(sorted(failures)), states=" ".join(map(str,sorted(states))),
                   min_soc=min(r[2] for r in rows), final_soc=rows[-1][2],
                   min_power_mw=min(r[6] for r in rows), max_power_mw=max(r[6] for r in rows),
                   raw_changes=raw_changes, latched_changes=latched_changes)
    return summary, rows


def save_figures(times, signals, matrix, traces, base_hz, output_dir):
    """Only PNG figures; numerical test inputs and matrix are separate CSVs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(4,4,figsize=(16,11),sharex=True,constrained_layout=True)
    for ax,(name,description) in zip(axes.flat,PROFILES):
        ax.plot(times,signals[name],linewidth=.5)
        ax.axhline(base_hz+.5,color="gray",linestyle="--",linewidth=.7)
        ax.axhline(base_hz-.5,color="gray",linestyle="--",linewidth=.7)
        ax.set_ylim(min(base_hz-.5,min(signals[name]))-.12,
                    max(base_hz+.5,max(signals[name]))+.12)
        ax.set_title(name,fontsize=10)
        ax.grid(alpha=.2)
        ax.ticklabel_format(axis="y",useOffset=False)
    fig.suptitle(f"Artificial frequency inputs: {base_hz} Hz, thresholds +/-0.5 Hz, seed 100")
    fig.supxlabel("Time [s]")
    fig.supylabel("Frequency [Hz]")
    fig.savefig(output_dir/"frequency_signals.png",dpi=160)
    plt.close(fig)

    socs=sorted(set(row["initial_soc"] for row in matrix))
    statuses={(row["profile"],row["initial_soc"]):row["status"] for row in matrix}
    values=[[statuses[name,soc]=="PASS" for soc in socs] for name,_ in PROFILES]
    fig,ax=plt.subplots(figsize=(10,8),constrained_layout=True)
    from matplotlib.colors import ListedColormap
    ax.imshow(values,cmap=ListedColormap(["#f9d5d3","#d5eddd"]),vmin=0,vmax=1,aspect="auto")
    ax.set_xticks(range(len(socs)),[f"{soc:.2%}" for soc in socs])
    ax.set_yticks(range(len(PROFILES)),[name for name,_ in PROFILES])
    ax.set_xticks([x-.5 for x in range(len(socs)+1)],minor=True)
    ax.set_yticks([y-.5 for y in range(len(PROFILES)+1)],minor=True)
    ax.grid(which="minor",color="white",linewidth=2)
    ax.tick_params(which="minor",length=0)
    for y,(name,_) in enumerate(PROFILES):
        for x,soc in enumerate(socs):
            ax.text(x,y,statuses[name,soc],ha="center",va="center",fontsize=9)
    ax.set_xlabel("Initial SOC")
    ax.set_title("Test matrix: rule checks over every sample (not grid performance validation)")
    fig.savefig(output_dir/"test_matrix.png",dpi=170)
    plt.close(fig)

    # Focused examples show sub-five-second behavior hidden on the full 6000 s axis.
    for name in ("short_high","reversal","sensor_delay","held_bias"):
        rows=traces[name]
        if name in ("short_high","reversal","sensor_delay"):
            rows=[r for r in rows if 995<=r[0]<=1020]
        t,f,soc,state,ps,pd,p,indicator,raw=zip(*rows)
        fig,axes=plt.subplots(4,1,figsize=(10,8),sharex=True,constrained_layout=True)
        axes[0].plot(t,raw,label="Physical frequency",linewidth=.8)
        axes[0].plot(t,f,label="Measured frequency",linestyle="--",linewidth=.8)
        axes[0].axhline(base_hz+.5,color="gray",linestyle=":")
        axes[0].axhline(base_hz-.5,color="gray",linestyle=":")
        axes[0].set_ylabel("Frequency [Hz]")
        axes[0].ticklabel_format(axis="y",useOffset=False)
        axes[1].step(t,indicator,where="post",label="Latched indicator")
        axes[1].set_yticks([-1,0,1],["Low","Normal","High"])
        axes[1].set_ylabel("Activation")
        axes[2].plot(t,[100*v for v in soc],label="SOC")
        axes[2].set_ylabel("SOC [%]")
        axes[3].plot(t,p,label="P_ESS")
        axes[3].plot(t,ps,"--",label="P_SOC")
        axes[3].plot(t,pd,":",label="P_droop")
        axes[3].set_ylabel("Power [MW]")
        axes[3].set_xlabel("Time [s]")
        for ax in axes:
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
        fig.suptitle(f"{name}: initial SOC {soc[0]:.1%} at displayed window start")
        fig.savefig(output_dir/f"{name}.png",dpi=160)
        plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-hz",type=int,choices=[50,60],default=60)
    parser.add_argument("--dt",type=float,default=.1)
    parser.add_argument("--noise-std-hz",type=float,default=.03)
    parser.add_argument("--initial-soc",type=float,default=.65)
    parser.add_argument("--droop-rate",type=float,default=.05)
    parser.add_argument("--ess-power-mw",type=float,default=25)
    parser.add_argument("--ess-energy-mwh",type=float,default=6.25)
    parser.add_argument("--output-dir",default="results/frequency_tests")
    args=parser.parse_args()
    numbers=[args.dt,args.noise_std_hz,args.initial_soc,args.droop_rate,args.ess_power_mw,args.ess_energy_mwh]
    if not all(math.isfinite(x) for x in numbers) or not 0<args.dt<=.1 or args.noise_std_hz<0 or not 0<=args.initial_soc<=1 or min(numbers[3:])<=0:
        parser.error("Use dt in (0,0.1], nonnegative noise std, SOC in [0,1], and positive ratings/droop")
    if abs(DURATION_S/args.dt-round(DURATION_S/args.dt))>1e-6:
        parser.error("dt must divide 6000 s exactly")
    if any(abs(t/args.dt-round(t/args.dt))>1e-6 for t in [2,4.9,5,5.1]):
        parser.error("dt must also divide 2, 4.9, 5 and 5.1 s to preserve pulse/delay timing")
    output=Path(args.output_dir)
    output.mkdir(parents=True,exist_ok=True)
    times,signals=generate_signals(args.base_hz,args.dt,args.noise_std_hz)
    with (output/"frequency_inputs.csv").open("w",newline="",encoding="utf-8") as file:
        writer=csv.writer(file)
        writer.writerow(["time_s"]+list(signals))
        writer.writerows(zip(times,*signals.values()))
    matrix,traces=[],{}
    socs=sorted(set([.1,.4,.65,.7,.9,args.initial_soc]))
    for name,description in PROFILES:
        for soc in socs:
            summary,rows=evaluate_case(times,signals[name],soc,args.base_hz,args.droop_rate,
                                       args.ess_power_mw,args.ess_energy_mwh,
                                       delay_s=2 if name=="sensor_delay" else 0)
            summary=dict(profile=name,description=description,base_hz=args.base_hz,threshold_hz=.5,
                         seed=100,noise_std_hz=0 if name.endswith("edge") else args.noise_std_hz,
                         dt_s=args.dt,duration_s=6000,hold_seconds=5,
                         droop_rate=args.droop_rate,ess_power_mw=args.ess_power_mw,
                         ess_energy_mwh=args.ess_energy_mwh,sensor_delay_s=2 if name=="sensor_delay" else 0,
                         **summary)
            matrix.append(summary)
            if soc==(.7 if name=="held_bias" else args.initial_soc):
                traces[name]=rows
        print(f"Evaluated: {name}",flush=True)
    with (output/"test_matrix.csv").open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=list(matrix[0]))
        writer.writeheader()
        writer.writerows(matrix)
    covered=set(int(s) for row in matrix for s in row["states"].split())
    failures=sum(row["status"]!="PASS" for row in matrix)
    print(f"{len(matrix)} cases: {failures} failures. States covered: {sorted(covered)}")
    try:
        save_figures(times,signals,matrix,traces,args.base_hz,output)
    except ImportError:
        parser.exit(2,"Install Matplotlib: py -m pip install -r requirements-plot.txt\n")
    print(f"Outputs: {output.resolve()}")
    raise SystemExit(1 if failures or covered!=set(range(1,10)) else 0)


if __name__=="__main__":
    main()
