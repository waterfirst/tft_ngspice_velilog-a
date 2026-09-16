"""Step 4: grade the pipeline against the answer key.
 truth     : ptft_true with true aging (answer key = 'measured' anode current)
 cards     : ptft_fit aged model-card library extracted from measured I-V (time points incl. 3000h measured)
 law       : ptft_fit + stretched-exp aging law fitted on <=1000h (3000h is a blind prediction)
 sens_Tk   : truth circuit, only Tk aged (others fresh) -> per-TFT contribution"""
import json
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
from pixel import *

TP = json.load(open(ROOT / "data" / "truth_params.json"))
AC = json.load(open(ROOT / "cards" / "aged_cards.json"))
LAW = json.load(open(ROOT / "cards" / "aging_law.json"))
TIMES = FIT_TIMES + [BLIND_TIME]
VDATA = {"고계조": 3.0, "중계조": 3.6, "저계조": 4.1}

def truth_card(k, t): return {kk: v for kk, v in TP[k].items() if kk.isupper()} | {"TSTRESS": t}
def law_card(k, t):
    l = LAW[k]; return dict(l["base"]) | {x: l[x] for x in ("AVT", "TAUV", "BETAV", "AMU", "TAUM", "BETAM")} | {"TSTRESS": t}

jobs = []
for g, vd in VDATA.items():
    for t in TIMES:
        jobs.append(("truth", g, vd, t, None, "ptft_true", {k: truth_card(k, t) for k in TFTS}))
        jobs.append(("cards", g, vd, t, None, "ptft_fit", {k: dict(AC[f"{k}@{t}"]) for k in TFTS}))
        jobs.append(("law", g, vd, t, None, "ptft_fit", {k: law_card(k, t) for k in TFTS}))
        for only in TFTS:
            jobs.append(("sens", g, vd, t, only, "ptft_true", {k: truth_card(k, t if k == only else 0) for k in TFTS}))

def work(j):
    kind, g, vd, t, only, mod, cards = j
    wd = ROOT / "runs" / "pix" / f"{kind}_{only or 'all'}_{vd}_{t}"
    done = wd / "result.json"
    if done.exists():
        return json.load(open(done))
    try:
        i, vg = run_pixel(mod, cards, vd, wd)
    except Exception as e:
        print("FAIL", wd.name, str(e)[:200], flush=True)
        return None
    row = dict(kind=kind, gray=g, vdata=vd, t_h=t, only=only or "", i_nA=i * 1e9, vg=vg)
    json.dump(row, open(done, "w"))
    return row

if __name__ == "__main__":
    with ProcessPoolExecutor(WORKERS) as ex:
        res = [x for x in ex.map(work, jobs) if x]
    df = pd.DataFrame(res); df.to_csv(ROOT / "data" / "pixel_results.csv", index=False)
    print("runs", len(df), "/", len(jobs))
