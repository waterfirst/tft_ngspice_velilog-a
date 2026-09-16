"""Step 7b: conventional (extraction + SPICE) vs AI flows on the same pixel population.
  AI-GBM    : gradient boosting, raw log I-V curves + Vdata -> log I_anode
  AI-MLP    : neural net, same inputs
  Hybrid    : conventional SPICE result + GBM learning only the residual log(I_true / I_conv)
Train on 2000 'main' pixels; test on 500 held-out main, blind_time (2000-4000 h), unseen_gray (Vdata 3.9-4.2)."""
import json
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from common import ROOT

D = np.load(ROOT / "data" / "dataset.npz")
ok = np.isfinite(D["y"]) & np.isfinite(D["y_conv"])
X = np.column_stack([D["X"], D["vdata"]])[ok]
ly, lc, split = np.log10(D["y"][ok]), np.log10(D["y_conv"][ok]), D["split"][ok]
rng = np.random.default_rng(0)
main = np.flatnonzero(split == "main"); rng.shuffle(main)
TRAIN, TEST = main[:2000], {"기본 (학습 범위 안)": main[2000:],
                            "3000h 부근 (시간 외삽)": np.flatnonzero(split == "blind_time"),
                            "저계조 (전압 외삽)": np.flatnonzero(split == "unseen_gray")}

def gbm(): return HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, l2_regularization=1.0, random_state=0)
def mlp(): return TransformedTargetRegressor(make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(128, 64), alpha=1e-2, max_iter=3000, early_stopping=True, random_state=0)), transformer=StandardScaler())

def fit_all(tr, with_mlp=True):
    Xh = np.column_stack([X, lc])
    m = {"AI-GBM": gbm().fit(X[tr], ly[tr]), "Hybrid": gbm().fit(Xh[tr], ly[tr] - lc[tr])}
    if with_mlp:
        m["AI-MLP"] = mlp().fit(X[tr], ly[tr])
    return {"기존(추출+SPICE)": lambda i: lc[i],
            "AI-GBM": lambda i: m["AI-GBM"].predict(X[i]),
            "AI-MLP": lambda i: m["AI-MLP"].predict(X[i]),
            "Hybrid": lambda i: lc[i] + m["Hybrid"].predict(Xh[i])}

def err(pred, i): return np.abs(10 ** (pred - ly[i]) - 1) * 100

P = fit_all(TRAIN)
metrics, scatter = {}, {}
for name, f in P.items():
    metrics[name] = {}
    for sp, i in TEST.items():
        e = err(f(i), i)
        metrics[name][sp] = dict(mape=float(e.mean()), p95=float(np.percentile(e, 95)))
    scatter[name] = {sp: dict(true=(10 ** ly[i] * 1e9).tolist(), pred=(10 ** f(i) * 1e9).tolist()) for sp, i in TEST.items()}

# learning curve on held-out main
curve = {"sizes": [100, 250, 500, 1000, 2000]}
for n in curve["sizes"]:
    Pn = fit_all(TRAIN[:n], with_mlp=False)
    for name in ("AI-GBM", "Hybrid"):
        curve.setdefault(name, []).append(float(err(Pn[name](TEST["기본 (학습 범위 안)"]), TEST["기본 (학습 범위 안)"]).mean()))
curve["기존(추출+SPICE)"] = [metrics["기존(추출+SPICE)"]["기본 (학습 범위 안)"]["mape"]] * len(curve["sizes"])

# population spread (산포): std/mean of anode current across held-out main pixels, t=0 only
i0 = TEST["기본 (학습 범위 안)"][D["t"][ok][TEST["기본 (학습 범위 안)"]] == 0]
spread = {"정답": float(np.std(10 ** ly[i0]) / np.mean(10 ** ly[i0]) * 100)}
for name, f in P.items():
    v = 10 ** f(i0); spread[name] = float(np.std(v) / np.mean(v) * 100)

json.dump(dict(metrics=metrics, curve=curve, spread=spread, n_spread=int(i0.size), scatter=scatter),
          open(ROOT / "data" / "ml_results.json", "w"), ensure_ascii=False)
for name, m in metrics.items():
    print(f"{name:16s} " + " | ".join(f"{sp[:6]} MAPE {v['mape']:6.2f}% P95 {v['p95']:6.2f}%" for sp, v in m.items()))
print("learning curve", json.dumps({k: [round(x, 2) for x in v] if k != 'sizes' else v for k, v in curve.items()}, ensure_ascii=False))
print(f"spread (std/mean %, n={i0.size})", {k: round(v, 2) for k, v in spread.items()})
