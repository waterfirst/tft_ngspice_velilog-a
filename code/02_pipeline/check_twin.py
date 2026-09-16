"""Verify numpy twin == ngspice for random parameter sets (incl. aging terms)."""
import numpy as np
from common import *
from fitmodel import id_fit
rng = np.random.default_rng(3)
worst = 0
for trial in range(4):
    p = dict(W=4e-6, L=float(rng.choice([4e-6, 30e-6])), VT0=rng.uniform(0.8, 2.5), U0=rng.uniform(30, 120),
             GAMMA=rng.uniform(0, 0.3), SS=rng.uniform(0.15, 0.6), LAMBDA=rng.uniform(0, 0.05), GOFF=10**rng.uniform(-15, -12),
             AVT=rng.uniform(0, 2), TAUV=rng.uniform(50, 500), BETAV=rng.uniform(0.3, 0.9),
             AMU=rng.uniform(0, 0.2), TAUM=rng.uniform(100, 900), BETAM=rng.uniform(0.3, 0.9))
    t = float(rng.choice([0, 37, 1234]))
    net = ["* twin check", OPTIONS, model_line("mm", "ptft_fit", p, tstress=t), "Vg g 0 0",
           "VdL dl 0 -0.1", "VdS ds 0 -5", "N1 dl g 0 mm", "N2 ds g 0 mm",
           ".control", f"pre_osdi {MODELS}/ptft_fit.osdi", "set wr_singlescale", "set wr_vecnames",
           "dc Vg 3 -10 -0.1", "wrdata tw.txt i(VdL) i(VdS)", ".endc", ".end"]
    h, d = run_ngspice("\n".join(net) + "\n", ["tw.txt"], ROOT / "runs" / f"twin{trial}")["tw.txt"]
    vsg = -d[:, 0]
    for col, vsd in (("i(vdl)", 0.1), ("i(vds)", 5.0)):
        sp = np.abs(d[:, h.index(col)])
        py = id_fit(vsg, vsd, TSTRESS=t, **p)
        m = sp > 1e-13
        rel = np.max(np.abs(py[m] / sp[m] - 1))
        worst = max(worst, rel)
        print(f"trial{trial} t={t:6g}h Vsd={vsd}: max rel err {rel:.2e} over {m.sum()} pts")
# criterion 1e-3: residual ~1e-4 is ngspice Newton-iteration noise, 300x below the 3 % measurement noise
print("WORST", f"{worst:.2e}", "PASS" if worst < 1e-3 else "FAIL")
