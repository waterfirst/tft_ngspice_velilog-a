"""Step 7a: pixel population dataset for comparing the conventional flow with an AI flow.
Each sample = one LTPO pixel (own device variation, usage factor, stress time, gray level).
  inputs    : noisy transfer curves of its 6 TFTs (Vds 0.1 / 5 V, |Vgs| 0-8 V) + Vdata
  truth     : 6T1C circuit with ptft_true (answer key)
  conv      : same curves -> ptft_fit card extraction per TFT -> 6T1C circuit (conventional flow)
Splits: main (t<=1000 h, Vdata 2.9-3.7), blind_time (2000-4000 h), unseen_gray (Vdata 3.9-4.2)."""
import json, math, shutil
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy.optimize import least_squares
from common import *
from fitmodel import id_true, id_fit
from pixel import run_pixel

TP = json.load(open(ROOT / "data" / "truth_params.json"))
VSG = np.round(np.arange(0, 8.01, 0.4), 2)                 # 21 gate points
VDS = (0.1, 5.0)
SPREAD = {"LTPS_P": dict(VT0=0.08, U0=0.06, SS=0.08), "IGZO_N": dict(VT0=0.05, U0=0.05, SS=0.06)}
X0 = {"LTPS_P": [1.2, 60, 0.1, 0.3, 0.02, -13], "IGZO_N": [0.8, 10, 0.2, 0.15, 0.01, -15]}
LB, UB = [-1.0, 1, 0.0, 0.05, 0.0, -18], [5.0, 300, 0.6, 1.5, 0.2, -10]

def sample(rng, split):
    t = 0.0 if rng.random() < 0.15 else float(10 ** rng.uniform(0, 3))
    vd = rng.uniform(2.9, 3.7)
    if split == "blind_time":
        t = float(rng.uniform(2000, 4000))
    elif split == "unseen_gray":
        vd = rng.uniform(3.9, 4.2)
    usage = math.exp(rng.normal(0, 0.35))                   # pixel-level usage / temperature factor
    cards = {}
    for k in TFTS:
        b, sp = TECH[tech(k)], SPREAD[tech(k)]
        p = {kk: v for kk, v in TP[k].items() if kk.isupper()}
        p["VT0"] = b["VT0"] + rng.normal(0, sp["VT0"])
        p["U0"] = b["U0"] * (1 + rng.normal(0, sp["U0"]))
        p["SS"] = b["SS"] * (1 + rng.normal(0, sp["SS"]))
        p["GOFF"] = b["GOFF"] * math.exp(rng.normal(0, 0.5))
        f = usage * math.exp(rng.normal(0, 0.15))
        p["AVT"] *= f; p["AMU"] = min(p["AMU"] * f, 0.5)
        p["TSTRESS"] = t
        cards[k] = p
    return dict(t=t, vdata=vd, usage=usage, cards=cards, split=split)

def measure(s, rng):
    """noisy transfer curves: dict k -> (vsg, vsd, id_meas) and the flat log-current feature vector"""
    curves, feat = {}, []
    for k in TFTS:
        vsg = np.concatenate([VSG, VSG]); vsd = np.repeat(VDS, VSG.size)
        i = id_true(vsg, vsd, **s["cards"][k])
        i = np.abs(i * np.exp(rng.normal(0, 0.03, i.size)) + rng.normal(0, NOISE_A, i.size)) + 1e-15
        curves[k] = (vsg, vsd, i)
        feat.extend(np.log10(i))
    return curves, feat

def extract(k, vsg, vsd, i):
    W, L = ROLES[k]["W"], ROLES[k]["L"]
    y = np.log10(i); cen = i < FLOOR_A
    def res(x):
        I = np.log10(np.maximum(id_fit(vsg, vsd, W, L, x[0], x[1], x[2], x[3], x[4], 10 ** x[5]), 1e-20))
        return np.where(cen, np.maximum(I - np.log10(FLOOR_A), 0), I - y)
    x = least_squares(res, X0[tech(k)], bounds=(LB, UB), x_scale=[0.5, 20, 0.1, 0.1, 0.01, 1], max_nfev=2000).x
    return dict(W=W, L=L, POL=pol(k), VT0=x[0], U0=x[1], GAMMA=x[2], SS=x[3], LAMBDA=x[4], GOFF=10 ** x[5])

def work(args):
    idx, s, curves = args
    wd = ROOT / "runs" / "ds" / str(idx)
    try:
        i_true, _ = run_pixel("ptft_true", s["cards"], s["vdata"], wd / "t")
        conv = {k: extract(k, *curves[k]) for k in TFTS}
        i_conv, _ = run_pixel("ptft_fit", conv, s["vdata"], wd / "c")
    except Exception as e:
        print("FAIL", idx, str(e)[:160], flush=True)
        i_true = i_conv = float("nan")
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    return idx, i_true, i_conv

if __name__ == "__main__":
    rng, mrng = np.random.default_rng(2026), np.random.default_rng(99)
    plan = [("main", 2500), ("blind_time", 400), ("unseen_gray", 400)]
    S = [sample(rng, sp) for sp, n in plan for _ in range(n)]
    M = [measure(s, mrng) for s in S]
    with ProcessPoolExecutor(WORKERS) as ex:
        out = {i: (a, b) for i, a, b in ex.map(work, [(i, s, M[i][0]) for i, s in enumerate(S)], chunksize=8)}
    y = np.array([out[i][0] for i in range(len(S))]); yc = np.array([out[i][1] for i in range(len(S))])
    np.savez_compressed(ROOT / "data" / "dataset.npz",
        X=np.array([m[1] for m in M]), vdata=np.array([s["vdata"] for s in S]), t=np.array([s["t"] for s in S]),
        usage=np.array([s["usage"] for s in S]), split=np.array([s["split"] for s in S]), y=y, y_conv=yc,
        t1_vt0=np.array([s["cards"]["T1"]["VT0"] for s in S]))
    for sp, n in plan:
        m = np.array([s["split"] == sp for s in S]) & np.isfinite(y) & np.isfinite(yc)
        e = np.abs(yc[m] / y[m] - 1) * 100
        print(f"{sp:12s} n={m.sum():4d}  I {y[m].min()*1e9:6.1f}~{y[m].max()*1e9:6.1f} nA  conv MAPE {e.mean():5.2f}%  P95 {np.percentile(e, 95):5.2f}%")
