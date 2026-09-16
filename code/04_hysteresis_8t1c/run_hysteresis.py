"""Synthetic 6T1C/8T1C frame-response experiment.

Metrics (the same definitions are used in textbook/ch09_hysteresis_8t1c.md):
E1 = |I1_from_black - I1_from_white| / I_ss.
N_settle = first post-transition frame whose current is within +/-1% of I_ss.
R_ss = I_ss(t_age) / I_ss(0 h).

The reduced matrix holds KH=0.05, TAUH=1e-3 s, age=0 h, VOBS=5 V and
real timing fixed, then sweeps one listed axis at a time. This avoids tuning a
large Cartesian product toward an expected result.
"""
from __future__ import annotations

import csv
import importlib.util
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "02_pipeline"
EXT = HERE.parent / "03_extension_8t1c"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXT))
import common
import pixel
import pixel_8t1c

MODEL = HERE / "models" / "ptft_hyst.osdi"
RESULTS = HERE / "results"
FIGS = HERE / "figs"
RUNS = HERE / "runs"
LABEL = "합성 예제 · 특정 제조사 회로 아님"

TIMINGS = {
    "real_60Hz": dict(frame_s=16.667e-3, init_start=50e-6, init_width=100e-6,
                      program_start=200e-6, program_width=100e-6,
                      emission_off_start=30e-6, emission_off_width=320e-6, step=20e-6),
    # same waveform, 10x finer max step: used only by gate G3 (timestep convergence)
    "real_60Hz_fine": dict(frame_s=16.667e-3, init_start=50e-6, init_width=100e-6,
                           program_start=200e-6, program_width=100e-6,
                           emission_off_start=30e-6, emission_off_width=320e-6, step=2e-6),
    "accelerated_1ms": dict(frame_s=1e-3, init_start=30e-6, init_width=200e-6,
                            program_start=300e-6, program_width=200e-6,
                            emission_off_start=20e-6, emission_off_width=580e-6, step=2e-6),
}
CIRCUITS = ("6T1C", "8T1C", "8T1C_no_T8", "8T1C_no_T7")
START_DATA = {"black": 4.1, "white": 3.0}
MID_DATA = 3.6
PRE_FRAMES = 4
POST_FRAMES = 8


def card(k: str, age_h: int, kh: float, tauh: float, extra: dict) -> dict:
    # T7/T8 cards come from the circuit-probed stress (adjusted_extra), everything else from TP8
    src = extra[k] if k in extra else pixel_8t1c.TP8[k]
    p = {q: v for q, v in src.items() if q.isupper()}
    p.update(TSTRESS=age_h, KH=kh, TAUH=tauh, VREFH=0.0)
    return p


def _pulse(high: float, low: float, start: float, width: float, frame: float) -> str:
    return f"PULSE({high:g} {low:g} {start:.12g} 1u 1u {width:.12g} {frame:.12g})"


def netlist(circuit: str, start: str, timing: str, kh: float, tauh: float,
            age_h: int, vobs: float, extra: dict, probe: bool = False) -> str:
    """Build a new timed wrapper around the public 6T1C topology."""
    tm = TIMINGS[timing]
    f = tm["frame_s"]
    total = (PRE_FRAMES + POST_FRAMES) * f
    change = PRE_FRAMES * f
    devices = list(common.TFTS)
    if circuit != "6T1C":
        if circuit != "8T1C_no_T7": devices.append("T7")
        if circuit != "8T1C_no_T8": devices.append("T8")
    lines = ["* synthetic frame response", common.OPTIONS]
    for k in devices:
        p = card(k, age_h, kh, tauh, extra)
        lines.append(common.model_line(f"m{k}", "ptft_hyst", p, tstress=p.pop("TSTRESS")))
    lines += [
        ".model oled D(IS=6e-26 N=3 RS=10k CJO=0.3p)",
        "Velvdd elvdd 0 4.6", "Velvss elvss 0 -3.0", "Vinit vinit 0 -3.5",
        f"Vdata data 0 PWL(0 {START_DATA[start]} {change - 1e-9:.12g} {START_DATA[start]} {change:.12g} {MID_DATA} {total:.12g} {MID_DATA})",
        f"Vs1 s1 0 {_pulse(7, -7, tm['init_start'], tm['init_width'], f)}",
        f"Vs2 s2 0 {_pulse(7, -7, tm['program_start'], tm['program_width'], f)}",
        f"Vem em 0 {_pulse(-7, 7, tm['emission_off_start'], tm['emission_off_width'], f)}",
        f"Vs1n s1n 0 {_pulse(-7, 7, tm['init_start'], tm['init_width'], f)}",
        f"Vs2n s2n 0 {_pulse(-7, 7, tm['program_start'], tm['program_width'], f)}",
        "NT1 nd1 ng ns mT1", "NT2 ns s2 data mT2", "NT3 nd1 s2n ng mT3",
        "NT4 vinit s1n ng mT4", "NT5 ns em elvdd mT5", "NT6 nan em nd1 mT6",
    ]
    if circuit != "6T1C":
        lines.append(f"Vobs vobs 0 {vobs:g}")
        if circuit != "8T1C_no_T7": lines.append("NT7 vinit s1 nan mT7")
        if circuit != "8T1C_no_T8": lines.append("NT8 ns s1 vobs mT8")
    lines += ["Cst elvdd ng 0.3p", "Vsense nan no 0", "Doled no elvss oled",
              ".control", "set num_threads=1", f"pre_osdi {MODEL}",
              f"tran {tm['step']:.12g} {total:.12g} 0 {tm['step']:.12g}",
              "set wr_singlescale", "set wr_vecnames", "wrdata current.txt i(Vsense)"]
    if probe:
        lines += ["wrdata s1.txt v(s1)", "wrdata nan.txt v(nan)", "wrdata vobs.txt v(vobs)",
                  "wrdata ns.txt v(ns)"]
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n"


def run_one(job: tuple) -> list[dict]:
    circuit, start, timing, kh, tauh, age_h, vobs, extra = job
    tag = f"{circuit}_{start}_{timing}_k{kh:g}_t{tauh:g}_a{age_h}_v{vobs:g}".replace(".", "p")
    wd = RUNS / tag
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "run.cir").write_text(netlist(circuit, start, timing, kh, tauh, age_h, vobs, extra))
    env = {**os.environ, "OMP_NUM_THREADS": "1"}
    r = subprocess.run([common.NGSPICE, "-b", "run.cir"], cwd=wd, capture_output=True,
                       text=True, timeout=180, env=env)
    if r.returncode or not (wd / "current.txt").exists():
        raise RuntimeError(f"ngspice failed {tag}: {(r.stdout + r.stderr)[-600:]}")
    a = np.loadtxt(wd / "current.txt", skiprows=1, ndmin=2)
    t, current = a[:, 0], a[:, 1]
    tm, f = TIMINGS[timing], TIMINGS[timing]["frame_s"]
    emit = tm["emission_off_start"] + tm["emission_off_width"] + 20e-6
    rows = []
    for n in range(1, POST_FRAMES + 1):
        fs = (PRE_FRAMES + n - 1) * f
        lo, hi = fs + emit, fs + f - max(20e-6, 2 * tm["step"])
        m = (t >= lo) & (t <= hi)
        if np.count_nonzero(m) < 2: raise RuntimeError(f"empty frame window {tag} frame {n}")
        # ngspice time points are not uniform: time-weighted mean, not a sample mean
        i_mean = np.trapezoid(current[m], t[m]) / (t[m][-1] - t[m][0])
        rows.append(dict(circuit=circuit, start=start, timing=timing, KH=kh, TAUH_s=tauh,
                         age_h=age_h, VOBS_V=vobs, frame=n, i_nA=float(i_mean * 1e9)))
    return rows


def adjusted_extra() -> tuple[dict, pd.DataFrame]:
    """Probe one real frame, then derive T7/T8 stress parameters from measured bias."""
    extra = {k: dict(v) for k, v in pixel_8t1c.TP8.items() if k in ("T7", "T8")}
    wd = RUNS / "stress_probe"
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "run.cir").write_text(netlist("8T1C", "black", "real_60Hz", 0, 1e-3, 0, 5, extra, True))
    env = {**os.environ, "OMP_NUM_THREADS": "1"}
    r = subprocess.run([common.NGSPICE, "-b", "run.cir"], cwd=wd, capture_output=True, text=True, timeout=180, env=env)
    if r.returncode: raise RuntimeError("stress probe failed: " + (r.stdout + r.stderr)[-500:])
    def load(name):
        x = np.loadtxt(wd / f"{name}.txt", skiprows=1, ndmin=2); return x[:, 0], x[:, 1]
    t, s1 = load("s1"); _, nan = load("nan"); _, vobs = load("vobs"); _, ns = load("ns")
    f = TIMINGS["real_60Hz"]["frame_s"]
    one = (t >= 3 * f) & (t <= 4 * f)
    tt = t[one]
    on = (s1[one] < 0).astype(float)          # PMOS T7/T8 gates are S1: on while S1 is low
    t_on = np.trapezoid(on, tt)
    out = []
    for k, source in (("T7", nan), ("T8", vobs)):
        # time-weighted: ngspice packs points around edges, so sample counts overstate duty
        duty = float(t_on / (tt[-1] - tt[0]))
        vgs = float(np.trapezoid(on * np.abs(s1[one] - source[one]), tt) / t_on)
        stress = duty * (vgs / 5.0) ** 2
        dvt = 2.5 * stress / (1 + stress)
        dmu = 0.10 * stress / (1 + stress)
        extra[k]["AVT"] = dvt / math.log(1 + (1000 / 200) ** 0.5)
        extra[k]["AMU"] = dmu / (1 - math.exp(-1000 / 800))
        out.append(dict(TFT=k, assumed_duty=0.012, assumed_Vgs_V=10.0,
                        probed_duty=duty, probed_Vgs_V=vgs, stress_index=stress,
                        dVth_1000_V=dvt, dmu_1000_frac=dmu))
    return extra, pd.DataFrame(out)


def g1(extra: dict) -> list[dict]:
    base = pd.read_csv(EXT / "results_8t1c.csv")
    out = []
    for circuit in ("6T1C", "8T1C"):
        for age in (0, 3000):
            ref = float(base[(base.circuit == circuit) & (base.gray == "중계조") &
                             (base.t_h == age) & (base.only.fillna("") == "")].i_nA.iloc[0])
            cards = {k: pixel_8t1c.card(k, age) for k in pixel_8t1c.TFTS8}
            raw = (pixel.netlist("ptft_true", {k: cards[k] for k in common.TFTS}, MID_DATA)
                   if circuit == "6T1C" else pixel_8t1c.netlist8(cards, MID_DATA))
            raw = raw.replace("ptft_true", "ptft_hyst").replace(str(ROOT / "models" / "ptft_hyst.osdi"), str(MODEL))
            wd = RUNS / f"g1_{circuit}_{age}"; wd.mkdir(parents=True, exist_ok=True)
            (wd / "run.cir").write_text(raw)
            r = subprocess.run([common.NGSPICE, "-b", "run.cir"], cwd=wd, capture_output=True, text=True,
                               timeout=180, env={**os.environ, "OMP_NUM_THREADS": "1"})
            m = re.search(r"^iavg\s*=\s*([-+0-9.eE]+)", r.stdout + r.stderr, re.M)
            if not m: raise RuntimeError("G1 failed: " + (r.stdout + r.stderr)[-500:])
            got = float(m.group(1)) * 1e9
            rel = abs(got - ref) / abs(ref)
            out.append(dict(gate="G1", case=f"{circuit}_{age}h", expected=ref, measured=got,
                            error=rel, limit=1e-4, pass_=rel <= 1e-4))
    return out


def g2() -> dict:
    wd = RUNS / "g2"; wd.mkdir(parents=True, exist_ok=True)
    cir = f"""* first-order trap gate
Vg g 0 PULSE(0 -1 1m 1n 1n 10m 20m)
Vs s 0 0
Vd d 0 0
.model mh ptft_hyst KH=0.05 TAUH=1m PROBE=1u
N1 d g s mh
.control
set num_threads=1
pre_osdi {MODEL}
tran 1u 2.01m
set wr_singlescale
set wr_vecnames
wrdata gate_i.txt i(Vg)
.endc
.end
"""
    (wd / "run.cir").write_text(cir)
    subprocess.run([common.NGSPICE, "-b", "run.cir"], cwd=wd, check=True, capture_output=True,
                   env={**os.environ, "OMP_NUM_THREADS": "1"})
    a = np.loadtxt(wd / "gate_i.txt", skiprows=1, ndmin=2)
    mem = abs(float(a[np.argmin(abs(a[:, 0] - 2e-3)), 1])) / 1e-6
    frac = mem / 1.0
    err = abs(frac - (1 - math.exp(-1)))
    return dict(gate="G2", case="Vmem_at_1tau", expected=1-math.exp(-1), measured=frac,
                error=err, limit=0.02, pass_=err <= 0.02)


def g3(extra: dict) -> list[dict]:
    """Timestep convergence at the representative point: max step 20 us vs 2 us."""
    out = []
    for c in ("6T1C", "8T1C"):
        res = {}
        for tm in ("real_60Hz", "real_60Hz_fine"):
            rows = []
            for s in START_DATA:
                rows += run_one((c, s, tm, 0.05, 1e-3, 0, 5.0, extra))
            p = pd.DataFrame(rows).pivot(index="frame", columns="start", values="i_nA")
            iss = float(p.loc[7:8].to_numpy().mean())
            res[tm] = (iss, abs(float(p.loc[1, "black"] - p.loc[1, "white"])) / abs(iss))
        (i0, e0), (i1, e1) = res["real_60Hz"], res["real_60Hz_fine"]
        for name, a, b, lim in (("I_ss", i0, i1, 0.005), ("E1", e0, e1, 0.05)):
            err = abs(a - b) / abs(b)
            out.append(dict(gate="G3", case=f"{c}_{name}_step20u_vs_2u", expected=b, measured=a,
                            error=err, limit=lim, pass_=err <= lim))
    return out


def matrix(extra: dict) -> list[tuple]:
    base = dict(timing="real_60Hz", kh=0.05, tauh=1e-3, age=0, vobs=5.0)
    conditions = set()
    for c in CIRCUITS:
        for kh in (0.0, 0.02, 0.05, 0.1): conditions.add((c, base["timing"], kh, base["tauh"], 0, 5.0))
        for tau in (1e-4, 1e-3, 1e-2): conditions.add((c, base["timing"], base["kh"], tau, 0, 5.0))
        for age in (0, 1000, 3000): conditions.add((c, base["timing"], base["kh"], base["tauh"], age, 5.0))
    for vobs in (4.0, 5.0, 6.0): conditions.add(("8T1C", base["timing"], base["kh"], base["tauh"], 0, vobs))
    for c in ("6T1C", "8T1C"):
        conditions.add((c, "accelerated_1ms", base["kh"], base["tauh"], 0, 5.0))
    return [(c, s, tm, kh, tau, age, vo, extra) for c, tm, kh, tau, age, vo in sorted(conditions) for s in START_DATA]


def make_metrics(frames: pd.DataFrame) -> pd.DataFrame:
    keys = ["circuit", "timing", "KH", "TAUH_s", "age_h", "VOBS_V"]
    rows = []
    for key, g in frames.groupby(keys, sort=True):
        p = g.pivot(index="frame", columns="start", values="i_nA")
        iss = float(p.loc[7:8].to_numpy().mean())
        e1 = abs(float(p.loc[1, "black"] - p.loc[1, "white"])) / abs(iss)
        settle = {}
        for start in START_DATA:
            ok = np.abs(p[start] - iss) <= 0.01 * abs(iss)
            settle[start] = int(ok[ok].index[0]) if ok.any() else 9
        rows.append(dict(zip(keys, key)) | dict(I_ss_nA=iss, E1=e1,
                    N_settle_black=settle["black"], N_settle_white=settle["white"]))
    m = pd.DataFrame(rows)
    zero = m[m.age_h == 0][keys[:-2] + ["VOBS_V", "I_ss_nA"]].rename(columns={"I_ss_nA": "I0"})
    # Match age rows to their zero-age point at the same circuit/timing/KH/TAUH/VOBS.
    join = ["circuit", "timing", "KH", "TAUH_s", "VOBS_V"]
    m = m.merge(zero[join + ["I0"]].drop_duplicates(join), on=join, how="left")
    m["R_ss"] = m.I_ss_nA / m.I0
    return m.drop(columns="I0")


def figures(frames: pd.DataFrame, metrics: pd.DataFrame) -> None:
    """f09 plots only. The 8T1C schematic/timing figure is hand-drawn: textbook/figs/f10_8t1c_timing.svg."""
    plt.rcParams.update({"font.family": ["Noto Sans CJK KR", "DejaVu Sans"],
                         "axes.unicode_minus": False, "svg.hashsalt": "tft-hyst"})
    colors = {"6T1C": "#1d4ed8", "8T1C": "#ea580c", "8T1C_no_T8": "#64748b", "8T1C_no_T7": "#15803d"}
    names = {"6T1C": "6T1C", "8T1C": "8T1C", "8T1C_no_T8": "8T1C − T8", "8T1C_no_T7": "8T1C − T7"}
    rep = frames[(frames.timing == "real_60Hz") & (frames.KH == 0.05) &
                 (frames.TAUH_s == 1e-3) & (frames.age_h == 0) &
                 (frames.VOBS_V == 5) & frames.circuit.isin(["6T1C", "8T1C"])]
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    for (c, s), g in rep.groupby(["circuit", "start"]):
        ax.plot(g.frame, g.i_nA, marker="o" if s == "black" else "s", color=colors[c],
                ls="-" if s == "black" else "--", label=f"{c} · {'저계조' if s == 'black' else '고계조'}에서 전환")
    ax.set(xlabel="중계조로 전환한 뒤 프레임 번호", ylabel="프레임 평균 애노드 전류 (nA)", xticks=range(1, 9),
           title="첫 프레임 히스테리시스 오차 (60 Hz, KH=0.05 V/V, τ=1 ms, 0 h)")
    ax.grid(alpha=.25); ax.legend(ncol=2, fontsize=8.5); fig.text(.5, .01, LABEL, ha="center", fontsize=8.5, color="#64748b")
    fig.tight_layout(rect=(0, .04, 1, 1)); fig.savefig(FIGS / "f09_frame_response.svg", metadata={"Date": None}); plt.close(fig)

    g = metrics[(metrics.timing == "real_60Hz") & (metrics.age_h == 0) & (metrics.VOBS_V == 5)]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.6, 4.2))
    for c in ("6T1C", "8T1C_no_T7", "8T1C_no_T8", "8T1C"):
        q = g[(g.circuit == c) & (g.TAUH_s == 1e-3)].sort_values("KH")
        a.plot(q.KH, q.E1 * 100, marker="o", color=colors[c], label=names[c], lw=2 if c in ("6T1C", "8T1C") else 1.2,
               ls="-" if c in ("6T1C", "8T1C") else ":")
        q = g[(g.circuit == c) & (g.KH == 0.05)].sort_values("TAUH_s")
        b.plot(q.TAUH_s * 1e3, q.E1 * 100, marker="o", color=colors[c], label=names[c], lw=2 if c in ("6T1C", "8T1C") else 1.2,
               ls="-" if c in ("6T1C", "8T1C") else ":")
    a.set(xlabel="KH (V/V)", ylabel="E1 (%)", xticks=[0, .02, .05, .1], title="(a) 트랩 세기  (τ = 1 ms)")
    b.set(xlabel="트랩 시정수 τ (ms)", ylabel="E1 (%)", xscale="log", title="(b) 트랩 시정수  (KH = 0.05)")
    b.axvline(0.1, color="#d97706", lw=1, ls="--"); b.text(0.115, 2.2, "← OBS 펄스 100 µs", color="#b45309", fontsize=9)
    for x in (a, b): x.grid(alpha=.25)
    a.legend(fontsize=8.5); fig.text(.5, .01, LABEL, ha="center", fontsize=8.5, color="#64748b")
    fig.tight_layout(rect=(0, .04, 1, 1)); fig.savefig(FIGS / "f09_kh_e1.svg", metadata={"Date": None}); plt.close(fig)


def summary(metrics: pd.DataFrame, stress: pd.DataFrame, gates: pd.DataFrame, elapsed: float) -> None:
    """Short, traceable summary: every number below is a row of metrics.csv / gates.csv / stress_probe.csv."""
    r = metrics[(metrics.timing == "real_60Hz") & (metrics.VOBS_V == 5)]
    def piv(cond, idx, val="E1", scale=100):
        return (r[cond].pivot_table(index=idx, columns="circuit", values=val) * scale).round(2).to_string()
    kh = piv((r.TAUH_s == 1e-3) & (r.age_h == 0), "KH")
    tau = piv((r.KH == 0.05) & (r.age_h == 0), "TAUH_s")
    rss = piv((r.KH == 0.05) & (r.TAUH_s == 1e-3), "age_h", "R_ss")
    acc = metrics[metrics.timing == "accelerated_1ms"].set_index("circuit").E1 * 100
    rep = r[(r.KH == 0.05) & (r.TAUH_s == 1e-3) & (r.age_h == 0)].set_index("circuit")
    e6, e8 = rep.E1["6T1C"] * 100, rep.E1["8T1C"] * 100
    txt = f"""# 8T1C hysteresis summary (synthetic example, not a manufacturer circuit)

Gates: {int(gates.pass_.sum())}/{len(gates)} PASS (`gates.csv`: G1 KH=0 reproduces ch07, G2 trap tau, G3 step 20 us vs 2 us).
E1 = |I1(from low gray) - I1(from high gray)| / I_ss, in %. Real 60 Hz unless noted. Runtime: `runtime.txt`.

Representative (KH=0.05 V/V, tau=1 ms, 0 h, VOBS=5 V): 6T1C E1={e6:.2f}%, 8T1C E1={e8:.2f}%
(-{(1 - e8 / e6) * 100:.1f}% relative). I_ss 6T1C={rep.I_ss_nA['6T1C']:.1f} nA, 8T1C={rep.I_ss_nA['8T1C']:.1f} nA.

E1 vs KH (tau=1 ms, 0 h)
{kh}

E1 vs tau [s] (KH=0.05, 0 h)
{tau}

R_ss = I_ss(t)/I_ss(0) (KH=0.05, tau=1 ms), in %
{rss}

Accelerated 1 ms frame (KH=0.05, tau=1 ms): 6T1C E1={acc['6T1C']:.2f}%, 8T1C E1={acc['8T1C']:.2f}%.
T7/T8 probed stress (`stress_probe.csv`): duty={stress.probed_duty.iloc[0]:.4f} (assumed 0.012),
|Vgs| T7={stress.probed_Vgs_V.iloc[0]:.2f} V, T8={stress.probed_Vgs_V.iloc[1]:.2f} V (assumed 10 V).
"""
    (RESULTS / "summary.md").write_text(txt)


def main() -> None:
    started = time.monotonic()
    RESULTS.mkdir(parents=True, exist_ok=True); FIGS.mkdir(parents=True, exist_ok=True); RUNS.mkdir(parents=True, exist_ok=True)
    subprocess.run(["openvaf", "ptft_hyst.va"], cwd=HERE / "models", check=True)
    extra, stress = adjusted_extra(); stress.to_csv(RESULTS / "stress_probe.csv", index=False, float_format="%.9g")
    gates = pd.DataFrame(g1(extra) + [g2()] + g3(extra)); gates.to_csv(RESULTS / "gates.csv", index=False, float_format="%.12g")
    if not gates.pass_.all(): raise RuntimeError("gate failure:\n" + gates.to_string(index=False))
    jobs = matrix(extra)
    pd.DataFrame([{k: v for k, v in zip(("circuit", "start", "timing", "KH", "TAUH_s", "age_h", "VOBS_V"), j[:7])}
                  for j in jobs]).to_csv(RESULTS / "sweep_design.csv", index=False, float_format="%.9g")
    rows = []
    with ProcessPoolExecutor(common.WORKERS) as ex:
        for part in ex.map(run_one, jobs): rows.extend(part)
    frames = pd.DataFrame(rows).sort_values(["circuit", "timing", "KH", "TAUH_s", "age_h", "VOBS_V", "start", "frame"])
    frames.to_csv(RESULTS / "frame_currents.csv", index=False, float_format="%.9g")
    metrics = make_metrics(frames)
    metrics.to_csv(RESULTS / "metrics.csv", index=False, float_format="%.9g")
    figures(frames, metrics)
    elapsed = time.monotonic() - started
    (RESULTS / "runtime.txt").write_text(f"{elapsed:.1f} s\n")
    summary(metrics, stress, gates, elapsed)
    print(gates.to_string(index=False))
    print(f"jobs={len(jobs)} runtime={elapsed:.1f}s")


if __name__ == "__main__": main()
