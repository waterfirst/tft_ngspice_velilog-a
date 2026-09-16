"""Extension exercise: grow the 6T1C pixel into an illustrative 8T1C and rerun the truth circuit.
T7 = anode reset (anode -> VINIT during init), T8 = on-bias switch (T1 source -> VOBS during init).
This is ONE public-literature-style variant chosen for teaching. Real 8T1C panels differ by vendor:
map your own schematic's labels to functions before reusing any number here.
Run from this folder after 02_pipeline steps 1-3:  python pixel_8t1c.py"""
import json, math, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "02_pipeline"))
import pixel
from common import *

HERE = Path(__file__).resolve().parent
TP = json.load(open(ROOT / "data" / "truth_params.json"))
EXTRA = {"T7": dict(name="애노드 리셋", duty=0.012, vgs=10.0),
         "T8": dict(name="온바이어스(OBS) 스위치", duty=0.012, vgs=10.0)}
TFTS8 = TFTS + list(EXTRA)

def extra_truth(seed=8):
    """Same recipe as common.truth_params, LTPS PMOS, W/L = 4/4 um."""
    import numpy as np
    rng, b, out = np.random.default_rng(seed), TECH["LTPS_P"], {}
    for k, r in EXTRA.items():
        s = r["duty"] * (r["vgs"] / 5.0) ** 2
        dvt, dmu = 2.5 * s / (1 + s), 0.10 * s / (1 + s)
        out[k] = dict(W=4e-6, L=4e-6, VT0=b["VT0"] + rng.normal(0, 0.05), U0=b["U0"] * (1 + rng.normal(0, 0.03)),
                      SS=b["SS"] * (1 + rng.normal(0, 0.05)), GAMMA=b["GAMMA"], LAMBDA=b["LAMBDA"], GOFF=b["GOFF"],
                      SIGMA=b["SIGMA"], THETA=b["THETA"], POL=1.0,
                      AVT=dvt / math.log(1 + (1000 / 200) ** 0.5), TAUV=200, BETAV=0.5,
                      AMU=dmu / (1 - math.exp(-1000 / 800)), TAUM=800)
    return out

TP8 = {**TP, **extra_truth()}

def netlist8(cards, vdata, vobs=5.0):
    """6T1C netlist from pixel.py plus T7/T8 lines, inserted before the storage capacitor."""
    six = {k: v for k, v in cards.items() if k in TFTS}
    lines = pixel.netlist("ptft_true", six, vdata).splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("Cst"))
    add = [model_line("mT7", "ptft_true", {k: v for k, v in cards["T7"].items() if k != "TSTRESS"}, tstress=cards["T7"]["TSTRESS"]),
           model_line("mT8", "ptft_true", {k: v for k, v in cards["T8"].items() if k != "TSTRESS"}, tstress=cards["T8"]["TSTRESS"]),
           f"Vobs vobs 0 {vobs}",
           "NT7 vinit s1 nan mT7",      # PMOS on while s1 is low (init phase)
           "NT8 ns s1 vobs mT8"]        # PMOS on while s1 is low: T1 source held at VOBS
    return "\n".join(lines[:i] + add + lines[i:]) + "\n"

def card(k, t): return {kk: v for kk, v in TP8[k].items() if kk.isupper()} | {"TSTRESS": t}

def run8(cards, vdata, wd):
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "run.cir").write_text(netlist8(cards, vdata))
    import subprocess, re, os
    r = subprocess.run([NGSPICE, "-b", "run.cir"], cwd=wd, capture_output=True, text=True, timeout=120,
                       env={**os.environ, "OMP_NUM_THREADS": "1"})
    got = dict(re.findall(r"^(iavg|vg_hold)\s*=\s*([-+0-9.eE]+)", r.stdout + r.stderr, re.M))
    if "iavg" not in got:
        raise RuntimeError(f"8T1C sim failed in {wd}")
    return float(got["iavg"])

VDATA = {"고계조": 3.0, "중계조": 3.6, "저계조": 4.1}
TIMES = [0, 100, 1000, 3000]

def work(j):
    circ, g, t, only = j
    wd = HERE / "runs" / f"{circ}_{only or 'all'}_{g}_{t}"
    if circ == "6T1C":
        i, _ = pixel.run_pixel("ptft_true", {k: card(k, t) for k in TFTS}, VDATA[g], wd)
    else:
        i = run8({k: card(k, t if only in (None, k) else 0) for k in TFTS8}, VDATA[g], wd)
    return dict(circuit=circ, gray=g, t_h=t, only=only or "", i_nA=i * 1e9)

if __name__ == "__main__":
    jobs = [(c, g, t, None) for c in ("6T1C", "8T1C") for g in VDATA for t in TIMES]
    jobs += [("8T1C", "중계조", 3000, k) for k in TFTS8]
    with ProcessPoolExecutor(WORKERS) as ex:
        df = pd.DataFrame(list(ex.map(work, jobs)))
    df.to_csv(HERE / "results_8t1c.csv", index=False)
    full = df[df.only == ""].pivot_table(index=["gray", "t_h"], columns="circuit", values="i_nA")
    for c in ("6T1C", "8T1C"):
        full[f"{c} 유지율%"] = full[c] / full[c].groupby(level=0).transform("first") * 100
    print(full.round(1).to_string())
    base = df[(df.circuit == "8T1C") & (df.only == "") & (df.gray == "중계조") & (df.t_h == 0)].i_nA.iloc[0]
    print("\n8T1C 중계조, 그 TFT만 3000h 열화했을 때 전류 변화 (%)")
    for _, r in df[df.only != ""].iterrows():
        print(f"  {r.only}: {(r.i_nA / base - 1) * 100:+.2f}")
