"""Step 2: extract a model card (ptft_fit) per TFT per time from measured I-V."""
import json, warnings
import numpy as np, pandas as pd
from scipy.optimize import least_squares
from common import *
from fitmodel import id_fit

df = pd.read_csv(ROOT / "data" / "measured_iv.csv")
NAMES = ["VT0", "U0", "GAMMA", "SS", "LAMBDA", "lgGOFF"]
X0 = {"LTPS_P": [1.2, 60, 0.1, 0.3, 0.02, -13], "IGZO_N": [0.8, 10, 0.2, 0.15, 0.01, -15]}
LB = [-1.0, 1, 0.0, 0.05, 0.0, -18]
UB = [5.0, 300, 0.6, 1.5, 0.2, -10]

def fit_one(sub, W, L, x0):
    # below-floor readings are censored: they only penalize a model that predicts more than the floor.
    # dropping them instead leaves GOFF unconstrained and it drifts to pA-level leakage.
    m = np.ones(len(sub), bool)
    vsg, vsd, y = sub.vsg.values, sub.vsd.values, np.log10(sub.id_meas.values)
    cen = sub.id_meas.values < FLOOR_A
    def res(x):
        I = np.log10(np.maximum(id_fit(vsg, vsd, W, L, x[0], x[1], x[2], x[3], x[4], 10 ** x[5]), 1e-20))
        return np.where(cen, np.maximum(I - np.log10(FLOOR_A), 0), I - y)
    r = least_squares(res, x0, bounds=(LB, UB), x_scale=[0.5, 20, 0.1, 0.1, 0.01, 1], max_nfev=4000)
    rms = np.sqrt(np.mean(r.fun ** 2))
    return r.x, rms, m.sum()

TP = json.load(open(ROOT / "data" / "truth_params.json"))
cards, rows = {}, []
for k in TFTS:
    W, L = ROLES[k]["W"], ROLES[k]["L"]
    x0 = X0[tech(k)]
    for t in sorted(df.t_h.unique()):
        sub = df[(df.tft == k) & (df.t_h == t)]
        x, rms, npt = fit_one(sub, W, L, x0)
        x0 = x                                           # warm start from previous time point
        card = dict(W=W, L=L, POL=pol(k), VT0=x[0], U0=x[1], GAMMA=x[2], SS=x[3], LAMBDA=x[4], GOFF=10 ** x[5])
        cards[f"{k}@{int(t)}"] = card
        # log-current error split by region (above / below 1 nA)
        m = sub.id_meas.values > 5e-12
        I = id_fit(sub.vsg.values[m], sub.vsd.values[m], **card)
        e = np.abs(np.log10(I) - np.log10(sub.id_meas.values[m]))
        hi = sub.id_meas.values[m] > 1e-9
        rows.append(dict(tft=k, tech=tech(k), t_h=int(t), split="blind" if t == BLIND_TIME else "fit", n=npt,
                         VT0=x[0], U0=x[1], GAMMA=x[2], SS=x[3], LAMBDA=x[4], GOFF=10 ** x[5],
                         GOFF_truth=TP[k]["GOFF"] if t == 0 else np.nan,
                         rms_dec=rms, err_on_pct=(10 ** np.mean(e[hi]) - 1) * 100,
                         err_sub_pct=(10 ** np.mean(e[~hi]) - 1) * 100))
json.dump(cards, open(ROOT / "cards" / "extracted_cards.json", "w"), indent=1)
out = pd.DataFrame(rows); out.to_csv(ROOT / "cards" / "extraction_summary.csv", index=False)
pd.set_option("display.width", 160)
print(out.round(4).to_string(index=False))
