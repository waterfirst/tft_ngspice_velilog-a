"""Step 1: synthetic 'measurements' from the truth model (transfer + output I-V per TFT per time)."""
import json
import numpy as np, pandas as pd
from common import *

TP = truth_params()
VSG_OUT = [2, 3, 4, 6]

def netlist_for(t):
    L = [f"* truth I-V at {t} h"]
    L.append(OPTIONS)
    for k in TFTS:
        L.append(model_line(f"m{k}", "ptft_true", TP[k], tstress=t))
    # sweeps are written for PMOS; NMOS (IGZO) devices see the mirrored gate/drain via E sources
    L += ["Vg g 0 0", "Vdo dout 0 0", "Egn gn 0 g 0 -1", "Edn doutn 0 dout 0 -1"]
    for k in TFTS:
        s = -pol(k)
        gate, dout = ("g", "dout") if s < 0 else ("gn", "doutn")
        L += [f"VdL_{k} dl_{k} 0 {0.1 * s:g}", f"VdS_{k} ds_{k} 0 {5 * s:g}",
              f"NL_{k} dl_{k} {gate} 0 m{k}", f"NS_{k} ds_{k} {gate} 0 m{k}"]
        for v in VSG_OUT:
            L += [f"VgO{v}_{k} go{v}_{k} 0 {v * s:g}", f"Vm{v}_{k} {dout} do{v}_{k} 0", f"NO{v}_{k} do{v}_{k} go{v}_{k} 0 m{k}"]
    tr = " ".join(f"i(VdL_{k}) i(VdS_{k})" for k in TFTS)
    ou = " ".join(f"i(Vm{v}_{k})" for k in TFTS for v in VSG_OUT)
    L += [".control", f"pre_osdi {MODELS}/ptft_true.osdi", "set wr_singlescale", "set wr_vecnames",
          "dc Vg 2 -8 -0.05", f"wrdata transfer.txt {tr}",
          "dc Vdo 0 -6 -0.05", f"wrdata output.txt {ou}", ".endc", ".end"]
    return "\n".join(L) + "\n"

rng = np.random.default_rng(11)
rows = []
for t in FIT_TIMES + [BLIND_TIME]:
    res = run_ngspice(netlist_for(t), ["transfer.txt", "output.txt"], ROOT / "runs" / f"meas_{t}h")
    h, d = res["transfer.txt"]; vsg = -d[:, 0]
    for k in TFTS:
        for vsd, col in ((0.1, f"i(vdl_{k.lower()})"), (5.0, f"i(vds_{k.lower()})")):
            i = np.abs(d[:, h.index(col)])
            rows += [dict(tft=k, t_h=t, kind="tr", vsg=a, vsd=vsd, id=b) for a, b in zip(vsg, i)]
    h, d = res["output.txt"]; vsd = -d[:, 0]
    for k in TFTS:
        for v in VSG_OUT:
            i = np.abs(d[:, h.index(f"i(vm{v}_{k.lower()})")])
            rows += [dict(tft=k, t_h=t, kind="out", vsg=float(v), vsd=a, id=b) for a, b in zip(vsd, i)]

df = pd.DataFrame(rows)
# measurement noise: 3 % multiplicative + 5 fA instrument noise (parameter-analyzer class, long integration)
df["id_meas"] = np.abs(df["id"] * np.exp(rng.normal(0, 0.03, len(df))) + rng.normal(0, NOISE_A, len(df))) + 1e-15
df["split"] = np.where(df.t_h == BLIND_TIME, "blind", "fit")
df.to_csv(ROOT / "data" / "measured_iv.csv", index=False)
json.dump(TP, open(ROOT / "data" / "truth_params.json", "w"), indent=1, ensure_ascii=False)
print("rows", len(df), "times", sorted(df.t_h.unique()))
print(f"{'TFT':4s} {'기술':6s} {'역할':16s} {'스트레스':>7s} {'|Vth|이동@1000h':>14s} {'이동도감소@1000h':>15s}")
for k in TFTS:
    p = TP[k]; print(f"{k:4s} {tech(k)[:4]:6s} {ROLES[k]['name']:16s} {p['stress']:7.3f} {p['dvt_1000']:13.3f}V {p['dmu_1000']*100:14.1f}%")
