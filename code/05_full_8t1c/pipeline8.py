"""Full 8T1C pipeline: the same steps chapters 3-6 ran for 6T1C, now for the illustrative 8T1C.

  probe    T7/T8 on-state bias read from the 60 Hz waveform -> truth aging inputs (no assumed duty/Vgs)
  measure  synthetic transfer/output I-V for T7, T8 at every stress time (T1-T6 reuse 02_pipeline data)
  extract  T7/T8 model cards per time + stretched-exp aging law (T1-T6 reuse 02_pipeline cards)
  pixels   8T1C anode current: truth / extracted cards / aging law x 3 grays x 7 times + 8 single-TFT runs
  dataset  3300-pixel 8T1C population: truth vs conventional (extract 8 TFTs + SPICE)
  ml       conventional vs AI-GBM vs AI-MLP vs Hybrid on that population
  figs     figs/f12_8t1c_grade.svg, figs/f13_8t1c_ml.svg + results/summary.md

Gates (results/gates.csv) stop the run if the 8T1C wrapper or the reused 6T1C steps drift.
Synthetic teaching example; the 8T1C is one public-literature-style variant, not a manufacturer circuit.
Run:  python pipeline8.py all      (or one stage name)
"""
import json
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit, least_squares

HERE = Path(__file__).resolve().parent
P02, P03 = HERE.parent / "02_pipeline", HERE.parent / "03_extension_8t1c"
sys.path.insert(0, str(P02))
sys.path.insert(0, str(P03))
import common                                          # noqa: E402
from common import (BLIND_TIME, FIT_TIMES, FLOOR_A, MODELS, NGSPICE, NOISE_A, OPTIONS, ROLES, TECH,  # noqa: E402
                    TFTS, WORKERS, model_line, pol, run_ngspice, tech)
import pixel                                           # noqa: E402
import pixel_8t1c                                      # noqa: E402
import gen_dataset as gd                               # noqa: E402
from fitmodel import id_fit, id_true                   # noqa: E402

EXTRA = {"T7": dict(name="애노드 리셋", W=4e-6, L=4e-6), "T8": dict(name="온바이어스(OBS) 스위치", W=4e-6, L=4e-6)}
for _k, _r in EXTRA.items():                           # gen_dataset.extract reads W/L from ROLES
    ROLES.setdefault(_k, dict(_r, duty=0.0, vgs=0.0))
TFTS8 = TFTS + list(EXTRA)
DATA, CARDS, FIGS, RES, RUNS = (HERE / d for d in ("data", "cards", "figs", "results", "runs"))
VDATA = {"고계조": 3.0, "중계조": 3.6, "저계조": 4.1}
TIMES = FIT_TIMES + [BLIND_TIME]
VOBS = 5.0
LABEL = "합성 예제 · 특정 제조사 회로 아님"
SE_KEYS = ("AVT", "TAUV", "BETAV", "AMU", "TAUM", "BETAM")


# ---------------------------------------------------------------- circuit
def netlist8(module, cards, vdata, probe=False):
    """pixel.netlist (6T1C) + T7/T8 lines before Cst, for any model module. Same text as pixel_8t1c.netlist8."""
    six = {k: v for k, v in cards.items() if k in TFTS}
    lines = pixel.netlist(module, six, vdata, probe=probe).splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("Cst"))
    add = []
    for k in EXTRA:
        p = dict(cards[k]); t = p.pop("TSTRESS", None)
        add.append(model_line(f"m{k}", module, p, tstress=t))
    add += [f"Vobs vobs 0 {VOBS}", "NT7 vinit s1 nan mT7", "NT8 ns s1 vobs mT8"]
    return "\n".join(lines[:i] + add + lines[i:]) + "\n"


def run8(module, cards, vdata, wd, probe=False):
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "run.cir").write_text(netlist8(module, cards, vdata, probe=probe))
    r = subprocess.run([NGSPICE, "-b", "run.cir"], cwd=wd, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "OMP_NUM_THREADS": "1"})
    got = dict(re.findall(r"^(iavg|vg_hold)\s*=\s*([-+0-9.eE]+)", r.stdout + r.stderr, re.M))
    if "iavg" not in got:
        raise RuntimeError(f"8T1C sim failed in {wd}")
    return float(got["iavg"]), float(got["vg_hold"])


def upper(p):
    return {k: v for k, v in p.items() if k.isupper()}


def law_card(law, k, t):
    l = law[k]
    return dict(l["base"]) | {x: l[x] for x in SE_KEYS} | {"TSTRESS": t}


def gate(rows, name, case, expected, measured, limit):
    err = abs(measured - expected) / max(abs(expected), 1e-30)
    rows.append(dict(gate=name, case=case, expected=expected, measured=measured, error=err, limit=limit, pass_=err <= limit))


def write_gates(rows, stage):
    f = RES / "gates.csv"
    old = pd.read_csv(f) if f.exists() else pd.DataFrame()
    if len(old):
        old = old[old.stage != stage]
    new = pd.DataFrame(rows).assign(stage=stage)
    allg = pd.concat([old, new], ignore_index=True).sort_values(["stage", "gate", "case"])
    allg.to_csv(f, index=False, float_format="%.6g")
    if not new.pass_.all():
        raise SystemExit("gate failure:\n" + new[~new.pass_].to_string(index=False))


# ---------------------------------------------------------------- probe
def stage_probe():
    """Read T7/T8 bias from the truth 8T1C waveform (2nd frame, time-weighted) and build their truth params."""
    cards = {k: upper(pixel_8t1c.TP8[k]) | {"TSTRESS": 0} for k in TFTS8}
    wd = RUNS / "probe"
    run8("ptft_true", cards, VDATA["중계조"], wd, probe=True)
    with open(wd / "probe.txt") as fh:
        head = fh.readline().split()
    a = np.loadtxt(wd / "probe.txt", skiprows=1)
    col = {h.lower(): i for i, h in enumerate(head)}
    t = a[:, 0]
    F = pixel.FRAME
    m = (t >= F) & (t <= 2 * F)
    t, s1, nan = t[m], a[m, col["v(s1)"]], a[m, col["v(nan)"]]
    on = (s1 < 0).astype(float)
    t_on = np.trapezoid(on, t)
    duty = float(t_on / (t[-1] - t[0]))
    vsg = {"T7": nan - s1, "T8": VOBS - s1}              # PMOS source: T7 = anode node, T8 = VOBS
    rng, b = np.random.default_rng(8), TECH["LTPS_P"]    # same draw order as pixel_8t1c.extra_truth
    truth, rows = {}, []
    for k in EXTRA:
        vgs = float(np.trapezoid(on * np.abs(vsg[k]), t) / t_on)
        s = duty * (vgs / 5.0) ** 2
        dvt, dmu = 2.5 * s / (1 + s), 0.10 * s / (1 + s)
        truth[k] = dict(W=4e-6, L=4e-6, VT0=b["VT0"] + rng.normal(0, 0.05), U0=b["U0"] * (1 + rng.normal(0, 0.03)),
                        SS=b["SS"] * (1 + rng.normal(0, 0.05)), GAMMA=b["GAMMA"], LAMBDA=b["LAMBDA"], GOFF=b["GOFF"],
                        SIGMA=b["SIGMA"], THETA=b["THETA"], POL=1.0,
                        AVT=dvt / math.log(1 + (1000 / 200) ** 0.5), TAUV=200, BETAV=0.5,
                        AMU=dmu / (1 - math.exp(-1000 / 800)), TAUM=800,
                        stress=s, dvt_1000=dvt, dmu_1000=dmu)
        rows.append(dict(TFT=k, assumed_duty=0.012, assumed_vgs_V=10.0, probed_duty=duty, probed_vgs_V=vgs,
                         stress_assumed=0.012 * (10 / 5) ** 2, stress_probed=s, dvt_1000_V=dvt, dmu_1000_pct=dmu * 100))
    tp6 = json.load(open(P02 / "data" / "truth_params.json"))
    json.dump(tp6 | truth, open(DATA / "truth_params_8t1c.json", "w"), indent=1, ensure_ascii=False)
    pd.DataFrame(rows).to_csv(RES / "stress_probe.csv", index=False, float_format="%.6g")
    g = []
    # S1 = PULSE(7 -7 ... 10u 10u 0.2m): below 0 V for 200 us plus half of each 10 us edge
    gate(g, "P1", "duty_vs_S1_pulse_width", (0.2e-3 + 10e-6) / F, duty, 0.02)
    write_gates(g, "probe")
    print(pd.DataFrame(rows).round(4).to_string(index=False))


# ---------------------------------------------------------------- measure (T7, T8)
def stage_measure():
    TP = json.load(open(DATA / "truth_params_8t1c.json"))
    VSG_OUT = [2, 3, 4, 6]
    rng, rows = np.random.default_rng(12), []
    for t in TIMES:
        L = [f"* truth I-V T7 T8 at {t} h", OPTIONS]
        for k in EXTRA:
            L.append(model_line(f"m{k}", "ptft_true", upper(TP[k]), tstress=t))
        L += ["Vg g 0 0", "Vdo dout 0 0"]
        for k in EXTRA:                                   # both PMOS: same sweep polarity as gen_meas
            L += [f"VdL_{k} dl_{k} 0 -0.1", f"VdS_{k} ds_{k} 0 -5", f"NL_{k} dl_{k} g 0 m{k}", f"NS_{k} ds_{k} g 0 m{k}"]
            for v in VSG_OUT:
                L += [f"VgO{v}_{k} go{v}_{k} 0 {-v}", f"Vm{v}_{k} dout do{v}_{k} 0", f"NO{v}_{k} do{v}_{k} go{v}_{k} 0 m{k}"]
        tr = " ".join(f"i(VdL_{k}) i(VdS_{k})" for k in EXTRA)
        ou = " ".join(f"i(Vm{v}_{k})" for k in EXTRA for v in VSG_OUT)
        L += [".control", f"pre_osdi {MODELS}/ptft_true.osdi", "set wr_singlescale", "set wr_vecnames",
              "dc Vg 2 -8 -0.05", f"wrdata transfer.txt {tr}", "dc Vdo 0 -6 -0.05", f"wrdata output.txt {ou}", ".endc", ".end"]
        res = run_ngspice("\n".join(L) + "\n", ["transfer.txt", "output.txt"], RUNS / f"meas_{t}h")
        h, d = res["transfer.txt"]; vsg = -d[:, 0]
        for k in EXTRA:
            for vsd, c in ((0.1, f"i(vdl_{k.lower()})"), (5.0, f"i(vds_{k.lower()})")):
                rows += [dict(tft=k, t_h=t, kind="tr", vsg=x, vsd=vsd, id=y) for x, y in zip(vsg, np.abs(d[:, h.index(c)]))]
        h, d = res["output.txt"]; vsd = -d[:, 0]
        for k in EXTRA:
            for v in VSG_OUT:
                rows += [dict(tft=k, t_h=t, kind="out", vsg=float(v), vsd=x, id=y)
                         for x, y in zip(vsd, np.abs(d[:, h.index(f"i(vm{v}_{k.lower()})")]))]
    df = pd.DataFrame(rows)
    df["id_meas"] = np.abs(df["id"] * np.exp(rng.normal(0, 0.03, len(df))) + rng.normal(0, NOISE_A, len(df))) + 1e-15
    df["split"] = np.where(df.t_h == BLIND_TIME, "blind", "fit")
    df.to_csv(DATA / "measured_iv_t78.csv", index=False, float_format="%.9g")
    print("rows", len(df))


# ---------------------------------------------------------------- extract (same recipe as extract.py / aging.py)
LB, UB = [-1.0, 1, 0.0, 0.05, 0.0, -18], [5.0, 300, 0.6, 1.5, 0.2, -10]


def fit_card(sub, W, L, x0):
    vsg, vsd, y = sub.vsg.values, sub.vsd.values, np.log10(sub.id_meas.values)
    cen = sub.id_meas.values < FLOOR_A
    def res(x):
        I = np.log10(np.maximum(id_fit(vsg, vsd, W, L, x[0], x[1], x[2], x[3], x[4], 10 ** x[5]), 1e-20))
        return np.where(cen, np.maximum(I - np.log10(FLOOR_A), 0), I - y)
    return least_squares(res, x0, bounds=(LB, UB), x_scale=[0.5, 20, 0.1, 0.1, 0.01, 1], max_nfev=4000).x


def se(t, A, tau, b):
    return A * (1 - np.exp(-(np.asarray(t, float) / tau) ** b))


def stage_extract():
    TP = json.load(open(DATA / "truth_params_8t1c.json"))
    df = pd.read_csv(DATA / "measured_iv_t78.csv")
    full = json.load(open(P02 / "cards" / "extracted_cards.json"))
    aged = json.load(open(P02 / "cards" / "aged_cards.json"))
    law = json.load(open(P02 / "cards" / "aging_law.json"))
    rows, g = [], []
    # gate: this extractor reproduces 02_pipeline's T1 cards from the same 02 measurements
    m02 = pd.read_csv(P02 / "data" / "measured_iv.csv")
    x = fit_card(m02[(m02.tft == "T1") & (m02.t_h == 0)], ROLES["T1"]["W"], ROLES["T1"]["L"], [1.2, 60, 0.1, 0.3, 0.02, -13])
    for i, n in enumerate(("VT0", "U0")):
        gate(g, "E1", f"T1@0_{n}_vs_02", full["T1@0"][n], float(x[i]), 1e-6)
    for k in EXTRA:
        W, L, x0 = EXTRA[k]["W"], EXTRA[k]["L"], [1.2, 60, 0.1, 0.3, 0.02, -13]
        for t in TIMES:
            x0 = fit_card(df[(df.tft == k) & (df.t_h == t)], W, L, x0)
            full[f"{k}@{t}"] = dict(W=W, L=L, POL=1.0, VT0=x0[0], U0=x0[1], GAMMA=x0[2], SS=x0[3], LAMBDA=x0[4], GOFF=10 ** x0[5])
        base = full[f"{k}@0"]
        vt, u = {}, {}
        for t in TIMES:
            sub = df[(df.tft == k) & (df.t_h == t) & (df.id_meas > 5e-12)]
            def res(x):
                I = id_fit(sub.vsg.values, sub.vsd.values, **{**base, "VT0": x[0], "U0": x[1]})
                return np.log10(np.maximum(I, 1e-20)) - np.log10(sub.id_meas.values)
            r = least_squares(res, [base["VT0"], base["U0"]], bounds=([0, 1], [6, 300]), x_scale=[0.5, 20])
            vt[t], u[t] = r.x
            aged[f"{k}@{t}"] = {**base, "VT0": r.x[0], "U0": r.x[1]}
        tf = np.array(FIT_TIMES, float)
        dv = np.array([vt[int(t)] - vt[0] for t in tf]); dm = np.array([1 - u[int(t)] / u[0] for t in tf])
        try:
            pv, _ = curve_fit(se, tf, dv, p0=[max(dv[-1], 1e-3) * 1.3, 200, 0.5], bounds=([0, 1, 0.1], [10, 1e6, 1]), maxfev=20000)
        except RuntimeError:
            pv = [0.0, 100.0, 0.5]
        try:
            pm, _ = curve_fit(se, tf, dm, p0=[max(dm[-1], 1e-4) * 1.3, 300, 0.7], bounds=([0, 1, 0.1], [0.9, 1e6, 1]), maxfev=20000)
        except RuntimeError:
            pm = [0.0, 100.0, 0.5]
        law[k] = dict(base=base, AVT=pv[0], TAUV=pv[1], BETAV=pv[2], AMU=pm[0], TAUM=pm[1], BETAM=pm[2])
        p = TP[k]
        for t in TIMES:
            rows.append(dict(tft=k, t_h=t, split="blind" if t == BLIND_TIME else "fit",
                             dVth_truth=p["AVT"] * math.log(1 + (t / p["TAUV"]) ** p["BETAV"]),
                             dVth_extracted=vt[t] - vt[0], dVth_law=float(se(t, *pv)),
                             mu_loss_truth_pct=p["AMU"] * (1 - math.exp(-t / p["TAUM"])) * 100,
                             mu_loss_extracted_pct=(1 - u[t] / u[0]) * 100, mu_loss_law_pct=float(se(t, *pm)) * 100))
    json.dump(full, open(CARDS / "extracted_cards_8t1c.json", "w"), indent=1)
    json.dump(aged, open(CARDS / "aged_cards_8t1c.json", "w"), indent=1)
    json.dump(law, open(CARDS / "aging_law_8t1c.json", "w"), indent=1)
    pd.DataFrame(rows).to_csv(RES / "aging_t78.csv", index=False, float_format="%.6g")
    write_gates(g, "extract")
    print(pd.DataFrame(rows).round(4).to_string(index=False))


# ---------------------------------------------------------------- pixels
def _pix(job):
    kind, g, vd, t, only, mod, cards = job
    wd = RUNS / "pix" / f"{kind}_{only or 'all'}_{vd}_{t}"
    i, vg = run8(mod, cards, vd, wd)
    return dict(kind=kind, gray=g, vdata=vd, t_h=t, only=only or "", i_nA=i * 1e9, vg=vg)


def stage_pixels():
    TP = json.load(open(DATA / "truth_params_8t1c.json"))
    AC = json.load(open(CARDS / "aged_cards_8t1c.json"))
    LAW = json.load(open(CARDS / "aging_law_8t1c.json"))
    tc = lambda k, t: upper(TP[k]) | {"TSTRESS": t}
    g = []
    # gate: this wrapper writes exactly the netlist chapter 7 used
    c7 = {k: pixel_8t1c.card(k, 0) for k in TFTS8}
    same = netlist8("ptft_true", c7, 3.6) == pixel_8t1c.netlist8(c7, 3.6)
    gate(g, "N1", "netlist8_text_equals_ch07", 1.0, 1.0 if same else 0.0, 0.0)
    jobs = []
    for gr, vd in VDATA.items():
        for t in TIMES:
            jobs.append(("truth", gr, vd, t, None, "ptft_true", {k: tc(k, t) for k in TFTS8}))
            jobs.append(("cards", gr, vd, t, None, "ptft_fit", {k: dict(AC[f"{k}@{t}"]) for k in TFTS8}))
            jobs.append(("law", gr, vd, t, None, "ptft_fit", {k: law_card(LAW, k, t) for k in TFTS8}))
        for only in TFTS8:
            jobs.append(("sens", gr, vd, BLIND_TIME, only, "ptft_true", {k: tc(k, BLIND_TIME if k == only else 0) for k in TFTS8}))
    with ProcessPoolExecutor(WORKERS) as ex:
        df = pd.DataFrame(list(ex.map(_pix, jobs)))
    df = df.sort_values(["kind", "vdata", "t_h", "only"])
    df.to_csv(RES / "pixel_8t1c.csv", index=False, float_format="%.9g")
    # gate: truth at 0 h equals chapter 7 (T7/T8 aging inputs only matter for t > 0)
    c07 = pd.read_csv(P03 / "results_8t1c.csv")
    for gr in VDATA:
        ref = float(c07[(c07.circuit == "8T1C") & (c07.gray == gr) & (c07.t_h == 0) & c07.only.isna()].i_nA.iloc[0])
        got = float(df[(df.kind == "truth") & (df.gray == gr) & (df.t_h == 0)].i_nA.iloc[0])
        gate(g, "N2", f"truth_0h_{gr}_vs_ch07", ref, got, 1e-4)
    write_gates(g, "pixels")
    grade(df)


def grade(df):
    p6 = pd.read_csv(P02 / "data" / "pixel_results.csv")
    rows = []
    for circ, d in (("6T1C", p6), ("8T1C", df)):
        for gr, vd in VDATA.items():
            q = d[(d.kind != "sens") & (d.vdata == vd)].pivot_table(index="t_h", columns="kind", values="i_nA")
            rows.append(dict(circuit=circ, gray=gr, I0_nA=q.loc[0, "truth"], I1000_nA=q.loc[1000, "truth"], I3000_nA=q.loc[3000, "truth"],
                             retention_3000_pct=q.loc[3000, "truth"] / q.loc[0, "truth"] * 100,
                             cards_err_0h_pct=(q.loc[0, "cards"] / q.loc[0, "truth"] - 1) * 100,
                             cards_err_3000h_pct=(q.loc[3000, "cards"] / q.loc[3000, "truth"] - 1) * 100,
                             law_err_0h_pct=(q.loc[0, "law"] / q.loc[0, "truth"] - 1) * 100,
                             law_err_3000h_pct=(q.loc[3000, "law"] / q.loc[3000, "truth"] - 1) * 100))
    out = pd.DataFrame(rows)
    out.to_csv(RES / "grade_6t1c_vs_8t1c.csv", index=False, float_format="%.4f")
    base = df[(df.kind == "truth") & (df.t_h == 0)].set_index("vdata").i_nA
    s = df[df.kind == "sens"].copy()
    s["change_pct"] = (s.i_nA / s.vdata.map(base) - 1) * 100
    s.pivot_table(index="only", columns="gray", values="change_pct").reindex(TFTS8).to_csv(
        RES / "sensitivity_8t1c.csv", float_format="%.4f")
    print(out.round(2).to_string(index=False))
    print(pd.read_csv(RES / "sensitivity_8t1c.csv").round(2).to_string(index=False))


# ---------------------------------------------------------------- dataset
TP8G = None


def sample8(rng, split):
    t = 0.0 if rng.random() < 0.15 else float(10 ** rng.uniform(0, 3))
    vd = rng.uniform(2.9, 3.7)
    if split == "blind_time":
        t = float(rng.uniform(2000, 4000))
    elif split == "unseen_gray":
        vd = rng.uniform(3.9, 4.2)
    usage = math.exp(rng.normal(0, 0.35))
    cards = {}
    for k in TFTS8:
        b, sp = TECH[tech(k)], gd.SPREAD[tech(k)]
        p = upper(TP8G[k])
        p["VT0"] = b["VT0"] + rng.normal(0, sp["VT0"])
        p["U0"] = b["U0"] * (1 + rng.normal(0, sp["U0"]))
        p["SS"] = b["SS"] * (1 + rng.normal(0, sp["SS"]))
        p["GOFF"] = b["GOFF"] * math.exp(rng.normal(0, 0.5))
        f = usage * math.exp(rng.normal(0, 0.15))
        p["AVT"] *= f; p["AMU"] = min(p["AMU"] * f, 0.5)
        p["TSTRESS"] = t
        cards[k] = p
    return dict(t=t, vdata=vd, usage=usage, cards=cards, split=split)


def measure8(s, rng):
    curves, feat = {}, []
    for k in TFTS8:
        vsg = np.concatenate([gd.VSG, gd.VSG]); vsd = np.repeat(gd.VDS, gd.VSG.size)
        i = id_true(vsg, vsd, **s["cards"][k])
        i = np.abs(i * np.exp(rng.normal(0, 0.03, i.size)) + rng.normal(0, NOISE_A, i.size)) + 1e-15
        curves[k] = (vsg, vsd, i)
        feat.extend(np.log10(i))
    return curves, feat


def _ds(args):
    import shutil
    idx, s, curves = args
    wd = RUNS / "ds" / str(idx)
    try:
        i_true, _ = run8("ptft_true", s["cards"], s["vdata"], wd / "t")
        conv = {k: gd.extract(k, *curves[k]) for k in TFTS8}
        i_conv, _ = run8("ptft_fit", conv, s["vdata"], wd / "c")
    except Exception as e:                                   # a failed pixel is dropped, and counted below
        print("FAIL", idx, str(e)[:160], flush=True)
        i_true = i_conv = float("nan")
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    return idx, i_true, i_conv


def stage_dataset():
    global TP8G
    TP8G = json.load(open(DATA / "truth_params_8t1c.json"))
    rng, mrng = np.random.default_rng(2027), np.random.default_rng(100)
    plan = [("main", 2500), ("blind_time", 400), ("unseen_gray", 400)]
    S = [sample8(rng, sp) for sp, n in plan for _ in range(n)]
    M = [measure8(s, mrng) for s in S]
    with ProcessPoolExecutor(WORKERS) as ex:
        out = {i: (a, b) for i, a, b in ex.map(_ds, [(i, s, M[i][0]) for i, s in enumerate(S)], chunksize=8)}
    y = np.array([out[i][0] for i in range(len(S))]); yc = np.array([out[i][1] for i in range(len(S))])
    np.savez_compressed(DATA / "dataset_8t1c.npz", X=np.array([m[1] for m in M]), vdata=np.array([s["vdata"] for s in S]),
                        t=np.array([s["t"] for s in S]), split=np.array([s["split"] for s in S]), y=y, y_conv=yc)
    g = []
    gate(g, "D1", "failed_pixels_fraction", 0.0, float(np.mean(~(np.isfinite(y) & np.isfinite(yc)))), 0.01)
    write_gates(g, "dataset")
    for sp, n in plan:
        m = np.array([s["split"] == sp for s in S]) & np.isfinite(y) & np.isfinite(yc)
        e = np.abs(yc[m] / y[m] - 1) * 100
        print(f"{sp:12s} n={m.sum():4d} conv MAPE {e.mean():5.2f}%  P95 {np.percentile(e, 95):5.2f}%")


# ---------------------------------------------------------------- ml (same models and splits as ml_compare.py)
def stage_ml():
    from sklearn.compose import TransformedTargetRegressor
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    D = np.load(DATA / "dataset_8t1c.npz")
    ok = np.isfinite(D["y"]) & np.isfinite(D["y_conv"])
    X = np.column_stack([D["X"], D["vdata"]])[ok]
    ly, lc, split = np.log10(D["y"][ok]), np.log10(D["y_conv"][ok]), D["split"][ok]
    rng = np.random.default_rng(0)
    main = np.flatnonzero(split == "main"); rng.shuffle(main)
    tests = {"in_range": main[2000:], "time_extrap": np.flatnonzero(split == "blind_time"),
             "gray_extrap": np.flatnonzero(split == "unseen_gray")}
    gbm = lambda: HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, l2_regularization=1.0, random_state=0)
    mlp = lambda: TransformedTargetRegressor(make_pipeline(StandardScaler(), MLPRegressor(
        hidden_layer_sizes=(128, 64), alpha=1e-2, max_iter=3000, early_stopping=True, random_state=0)), transformer=StandardScaler())

    def fit_all(tr, with_mlp=True):
        Xh = np.column_stack([X, lc])
        m = {"AI-GBM": gbm().fit(X[tr], ly[tr]), "Hybrid": gbm().fit(Xh[tr], ly[tr] - lc[tr])}
        if with_mlp:
            m["AI-MLP"] = mlp().fit(X[tr], ly[tr])
        f = {"conventional": lambda i: lc[i], "AI-GBM": lambda i: m["AI-GBM"].predict(X[i]),
             "Hybrid": lambda i: lc[i] + m["Hybrid"].predict(Xh[i])}
        if with_mlp:
            f["AI-MLP"] = lambda i: m["AI-MLP"].predict(X[i])
        return f

    err = lambda pred, i: np.abs(10 ** (pred - ly[i]) - 1) * 100
    P = fit_all(main[:2000])
    rows = []
    for name in ("conventional", "AI-GBM", "AI-MLP", "Hybrid"):
        for sp, i in tests.items():
            e = err(P[name](i), i)
            rows.append(dict(method=name, test=sp, n=int(i.size), mape_pct=float(e.mean()), p95_pct=float(np.percentile(e, 95))))
    for n in (100, 250, 500, 1000, 2000):
        Pn = fit_all(main[:n], with_mlp=False)
        for name in ("AI-GBM", "Hybrid"):
            rows.append(dict(method=name, test=f"learning_n{n}", n=int(tests["in_range"].size),
                             mape_pct=float(err(Pn[name](tests["in_range"]), tests["in_range"]).mean()), p95_pct=np.nan))
    out = pd.DataFrame(rows)
    out.to_csv(RES / "ml_8t1c.csv", index=False, float_format="%.4f")
    print(out.round(2).to_string(index=False))


# ---------------------------------------------------------------- figures + summary
def stage_figs():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": ["Noto Sans CJK KR", "DejaVu Sans"], "axes.unicode_minus": False,
                         "svg.hashsalt": "tft-8t1c", "axes.spines.top": False, "axes.spines.right": False})
    ink, gray, orange, blue = "#1b1a17", "#b9b6ac", "#eb6834", "#2a78d6"
    grd = pd.read_csv(RES / "grade_6t1c_vs_8t1c.csv")
    sens = pd.read_csv(RES / "sensitivity_8t1c.csv").set_index("only")
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4.3), gridspec_kw={"width_ratios": [1, 1.1]})
    grays = list(VDATA)
    x = np.arange(len(grays)); w = 0.36
    for j, (circ, c) in enumerate((("6T1C", blue), ("8T1C", orange))):
        v = grd[grd.circuit == circ].set_index("gray").loc[grays]
        bars = a.bar(x + (j - 0.5) * w, v.retention_3000_pct, w * 0.94, color=c, label=circ)
        for r, val in zip(bars, v.retention_3000_pct):
            a.text(r.get_x() + r.get_width() / 2, val + 0.4, f"{val:.1f}", ha="center", fontsize=9, color=ink)
    a.set_xticks(x, grays); a.set_ylim(70, 95); a.set_ylabel("3000 h 전류 유지율 (%)")
    a.set_title("(a) 수명: 6T1C vs 8T1C", loc="left"); a.legend(frameon=False, fontsize=9)
    col = "중계조"
    vals = sens[col].reindex(TFTS8).where(lambda v: v.abs() >= 0.005, 0.0)   # no "-0.00%" labels
    ys = np.arange(len(TFTS8))[::-1]
    b.barh(ys, vals, 0.62, color=[orange if k == "T1" else gray for k in TFTS8])
    for yy, v in zip(ys, vals):
        b.text(v - 0.25 if v < -1 else 0.25, yy, f"{v:+.2f}%", va="center", ha="right" if v < -1 else "left", fontsize=9, color=ink)
    b.set_yticks(ys, [f"{k} {ROLES[k]['name']}" for k in TFTS8]); b.set_xlim(vals.min() * 1.3, 3)
    b.axvline(0, color=ink, lw=0.8); b.set_xlabel("그 TFT만 3000 h 열화 → 중계조 전류 변화 (%)")
    b.set_title("(b) 8T1C TFT별 민감도", loc="left")
    fig.text(0.5, 0.01, LABEL, ha="center", fontsize=8.5, color="#7a776d")
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(FIGS / "f12_8t1c_grade.svg", metadata={"Date": None}); plt.close(fig)

    ml = pd.read_csv(RES / "ml_8t1c.csv")
    tests = [("in_range", "학습 범위 안"), ("time_extrap", "3000 h 부근"), ("gray_extrap", "저계조 (처음 보는 조건)")]
    methods = [("conventional", "기존 물리", "#5f5e58"), ("AI-GBM", "AI-GBM", blue), ("AI-MLP", "AI-MLP", "#9ec5f4"), ("Hybrid", "Hybrid", orange)]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.6))
    for ax, (tk, tl) in zip(axs, tests):
        v = [float(ml[(ml.method == m) & (ml.test == tk)].mape_pct.iloc[0]) for m, _, _ in methods]
        yy = np.arange(len(methods))[::-1]
        ax.barh(yy, v, 0.62, color=[c for _, _, c in methods])
        for y0, val in zip(yy, v):
            ax.text(val + max(v) * 0.02, y0, f"{val:.1f}%", va="center", fontsize=9, color=ink)
        ax.set_yticks(yy, [l for _, l, _ in methods] if tk == "in_range" else [""] * len(methods))
        ax.set_xlim(0, max(v) * 1.25); ax.set_title(tl, loc="left", fontsize=11)
    axs[1].set_xlabel("평균 절대 백분율 오차 (%) — 패널마다 축 범위 다름")
    fig.suptitle("8T1C 합성 화소 3300개: 기존 물리 vs AI vs Hybrid", x=0.01, ha="left", fontsize=12)
    fig.text(0.5, 0.01, LABEL, ha="center", fontsize=8.5, color="#7a776d")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95)); fig.savefig(FIGS / "f13_8t1c_ml.svg", metadata={"Date": None}); plt.close(fig)

    gates = pd.read_csv(RES / "gates.csv")
    stress = pd.read_csv(RES / "stress_probe.csv")
    mlp = ml[~ml.test.str.startswith("learning")].pivot_table(index="method", columns="test", values="mape_pct")
    txt = (f"# 8T1C full pipeline summary (synthetic, not a manufacturer circuit)\n\n"
           f"Gates: {int(gates.pass_.sum())}/{len(gates)} PASS (`gates.csv`).\n\n"
           f"## Grade (`grade_6t1c_vs_8t1c.csv`)\n{grd.round(2).to_string(index=False)}\n\n"
           f"## Single-TFT 3000 h sensitivity, % (`sensitivity_8t1c.csv`)\n{sens.round(2).to_string()}\n\n"
           f"## ML MAPE, % (`ml_8t1c.csv`)\n{mlp.round(2).to_string()}\n\n"
           f"## T7/T8 stress from the 60 Hz waveform (`stress_probe.csv`)\n{stress.round(4).to_string(index=False)}\n")
    (RES / "summary.md").write_text(txt)
    print(txt)


STAGES = {"probe": stage_probe, "measure": stage_measure, "extract": stage_extract, "pixels": stage_pixels,
          "dataset": stage_dataset, "ml": stage_ml, "figs": stage_figs}

if __name__ == "__main__":
    for d in (DATA, CARDS, FIGS, RES, RUNS):
        d.mkdir(parents=True, exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name in (STAGES if which == "all" else [which]):
        print(f"== {name}", flush=True)
        STAGES[name]()
