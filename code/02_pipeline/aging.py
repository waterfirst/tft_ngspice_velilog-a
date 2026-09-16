"""Step 3: aging extraction (shape params frozen at 0 h) -> aging-law fit -> Verilog-A time model params.
3000 h is never used for fitting: it is the blind check."""
import json, math
import numpy as np, pandas as pd
from scipy.optimize import least_squares, curve_fit
from common import *
from fitmodel import id_fit

df = pd.read_csv(ROOT / "data" / "measured_iv.csv")
full = json.load(open(ROOT / "cards" / "extracted_cards.json"))
TP = json.load(open(ROOT / "data" / "truth_params.json"))

def truth_dvt(k, t):  return TP[k]["AVT"] * math.log(1 + (t / TP[k]["TAUV"]) ** TP[k]["BETAV"])
def truth_mu(k, t):   return 1 - TP[k]["AMU"] * (1 - math.exp(-t / TP[k]["TAUM"]))
def se(t, A, tau, b): return A * (1 - np.exp(-(np.asarray(t, float) / tau) ** b))

aged_cards, law, rows = {}, {}, []
for k in TFTS:
    base = full[f"{k}@0"]
    vt, u = {}, {}
    for t in sorted(df.t_h.unique()):
        sub = df[(df.tft == k) & (df.t_h == t) & (df.id_meas > 5e-12)]
        def res(x):
            I = id_fit(sub.vsg.values, sub.vsd.values, **{**base, "VT0": x[0], "U0": x[1]})
            return np.log10(np.maximum(I, 1e-20)) - np.log10(sub.id_meas.values)
        r = least_squares(res, [base["VT0"], base["U0"]], bounds=([0, 1], [6, 300]), x_scale=[0.5, 20])
        vt[int(t)], u[int(t)] = r.x
        aged_cards[f"{k}@{int(t)}"] = {**base, "VT0": r.x[0], "U0": r.x[1]}
    tf = np.array(FIT_TIMES, float)
    dv = np.array([vt[int(t)] - vt[0] for t in tf])
    dm = np.array([1 - u[int(t)] / u[0] for t in tf])
    pv, _ = curve_fit(se, tf, dv, p0=[max(dv[-1], 1e-3) * 1.3, 200, 0.5], bounds=([0, 1, 0.1], [10, 1e6, 1]), maxfev=20000)
    try:
        pm, _ = curve_fit(se, tf, dm, p0=[max(dm[-1], 1e-4) * 1.3, 300, 0.7], bounds=([0, 1, 0.1], [0.9, 1e6, 1]), maxfev=20000)
    except RuntimeError:
        pm = [0.0, 100.0, 0.5]
    law[k] = dict(base=base, AVT=pv[0], TAUV=pv[1], BETAV=pv[2], AMU=pm[0], TAUM=pm[1], BETAM=pm[2])
    for t in FIT_TIMES + [BLIND_TIME]:
        rows.append(dict(tft=k, t_h=t, split="blind" if t == BLIND_TIME else "fit",
                         dVth_truth=truth_dvt(k, t), dVth_extracted=vt[t] - vt[0], dVth_law=float(se(t, *pv)),
                         mu_loss_truth_pct=(1 - truth_mu(k, t)) * 100,
                         mu_loss_extracted_pct=(1 - u[t] / u[0]) * 100,
                         mu_loss_law_pct=float(se(t, *pm)) * 100))

json.dump(aged_cards, open(ROOT / "cards" / "aged_cards.json", "w"), indent=1)
json.dump(law, open(ROOT / "cards" / "aging_law.json", "w"), indent=1)
out = pd.DataFrame(rows); out.to_csv(ROOT / "cards" / "aging_summary.csv", index=False)
pd.set_option("display.width", 180)
print(out.round(3).to_string(index=False))
print("\n열화식 파라미터 (Verilog-A TSTRESS 모델용)")
for k in TFTS:
    l = law[k]; print(f"{k}: AVT={l['AVT']:.3f}V TAUV={l['TAUV']:.0f}h BETAV={l['BETAV']:.2f} | AMU={l['AMU']:.3f} TAUM={l['TAUM']:.0f}h BETAM={l['BETAM']:.2f}")
