"""Step 7c: figure for conventional vs AI flows (figs/ml_compare.png)."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import numpy as np
from common import ROOT

for f in fm.findSystemFonts():
    if "NanumGothic.ttf" in f:
        fm.fontManager.addfont(f); plt.rcParams["font.family"] = "NanumGothic"; break
plt.rcParams["axes.unicode_minus"] = False

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
R = json.load(open(ROOT / "data" / "ml_results.json"))
METHODS = ["기존(추출+SPICE)", "AI-GBM", "AI-MLP", "Hybrid"]
COL = dict(zip(METHODS, ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]))   # slots 1,2,3,7 (yellow skipped: low contrast on white)
SPLITS = list(R["metrics"][METHODS[0]])

fig, ax = plt.subplots(1, 3, figsize=(17, 5.4))
for a in ax:
    a.grid(color=GRID, lw=0.8); a.tick_params(colors=INK2)
    for s in a.spines.values(): s.set_color(GRID)

# (1) dot plot: MAPE per test condition, log axis
a = ax[0]
for j, sp in enumerate(SPLITS):
    y0 = len(SPLITS) - 1 - j
    for k, m in enumerate(METHODS):
        v = R["metrics"][m][sp]["mape"]; y = y0 + (1.5 - k) * 0.17
        a.plot([v], [y], "o", color=COL[m], ms=9, mec="white", mew=1.5, label=m if j == 0 else None)
        a.text(v * 1.12, y, f"{v:.1f}%", va="center", fontsize=8.5, color=INK)
a.set_xscale("log"); a.set_xlim(0.6, 400)
a.set_xticks([1, 2, 5, 10, 20, 50, 100]); a.set_xticklabels(["1", "2", "5", "10", "20", "50", "100"])
a.set_yticks(range(len(SPLITS))); a.set_yticklabels(SPLITS[::-1])
a.set_xlabel("OLED 전류 평균 절대오차 MAPE (%, 로그)", color=INK2)
a.set_title("① 조건별 정확도", color=INK, loc="left")
a.legend(frameon=False, fontsize=9, loc="upper right", bbox_to_anchor=(1.0, 1.0))
a.set_ylim(-0.5, len(SPLITS) - 0.2)

# (2) learning curve
a = ax[1]
c = R["curve"]
for m in ("기존(추출+SPICE)", "AI-GBM", "Hybrid"):
    a.plot(c["sizes"], c[m], "-" if m != METHODS[0] else "--", marker="o" if m != METHODS[0] else None,
           color=COL[m], lw=2, ms=7, label=m)
    a.text(c["sizes"][-1] * 1.08, c[m][-1], f"{c[m][-1]:.1f}%", va="center", fontsize=9, color=INK)
a.set_xscale("log"); a.set_xlim(80, 3200); a.set_ylim(0, 5.6)
a.set_xticks(c["sizes"]); a.set_xticklabels([str(s) for s in c["sizes"]])
a.set_xlabel("학습 화소 수", color=INK2); a.set_ylabel("MAPE (%) — 기본 조건 500화소", color=INK2)
a.set_title("② 학습 데이터 양에 따른 오차", color=INK, loc="left")
a.legend(frameon=False, fontsize=9, loc="upper right")

# (3) scatter on unseen low gray
a = ax[2]
sp = SPLITS[2]
lo, hi = 40, 420
a.plot([lo, hi], [lo, hi], color=INK2, lw=1)
for m in ("AI-GBM", "기존(추출+SPICE)", "Hybrid"):
    s = R["scatter"][m][sp]
    a.scatter(s["true"], s["pred"], s=14, color=COL[m], alpha=0.75, edgecolors="none", label=m)
a.set_xscale("log"); a.set_yscale("log"); a.set_xlim(lo, 180); a.set_ylim(lo, hi)
for axis in (a.xaxis, a.yaxis):
    axis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%g")); axis.set_minor_formatter(matplotlib.ticker.NullFormatter())
a.set_xticks([50, 100, 150]); a.set_yticks([50, 100, 200, 400])
a.set_xlabel("정답 OLED 전류 (nA)", color=INK2); a.set_ylabel("예측 (nA)", color=INK2)
a.set_title("③ 학습에 없던 저계조 (Vdata 3.9–4.2V)", color=INK, loc="left")
a.legend(frameon=False, fontsize=9, loc="upper left", markerscale=1.6)

fig.suptitle("7단계 — 같은 3300화소 합성 모집단에서 기존 흐름 vs AI 흐름 (학습 2000 / 시험 500·400·400)", color=INK, fontsize=12)
fig.tight_layout()
fig.savefig(ROOT / "figs" / "ml_compare.png", dpi=130)
print("saved figs/ml_compare.png")
