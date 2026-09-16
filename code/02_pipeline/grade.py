"""Steps 5-6: anode current vs stress time, graded against the answer key (truth circuit).
v1 = all-LTPS pixel with floor-dropped extraction (kept in v1_all_ltps/), v2 = LTPO (IGZO T3/T4) + censored extraction."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import pandas as pd
from common import *

for f in fm.findSystemFonts():
    if "NanumGothic.ttf" in f:
        fm.fontManager.addfont(f); plt.rcParams["font.family"] = "NanumGothic"; break
plt.rcParams["axes.unicode_minus"] = False

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
C = ["#2a78d6", "#eb6834", "#1baf7a"]                  # categorical slots 1-3 (fixed order)
GRAY = {3.0: "고계조 (Vdata 3.0V)", 3.6: "중계조 (3.6V)", 4.1: "저계조 (4.1V)"}

d = pd.read_csv(ROOT / "data" / "pixel_results.csv")
v1 = pd.read_csv(ROOT / "v1_all_ltps" / "data" / "pixel_results.csv")
piv = lambda df: df[df.kind != "sens"].pivot_table(index=["vdata", "t_h"], columns="kind", values="i_nA")
p2, p1 = piv(d), piv(v1)
TIMES = sorted(d.t_h.unique())
xt = [0.3 if t == 0 else t for t in TIMES]                 # 0 h placed at 0.3 on the log axis

fig, ax = plt.subplots(1, 3, figsize=(17, 5.2))
for a in ax:
    a.grid(color=GRID, lw=0.8); a.tick_params(colors=INK2)
    for s in a.spines.values(): s.set_color(GRID)

# (1) law-model prediction error vs time, blind 3000 h shaded
a = ax[0]
a.axvspan(1500, 5000, color="#f0efec", zorder=0)
a.text(2600, 0.6, "블라인드\n(피팅 안 씀)", color=INK2, fontsize=9, ha="center")
a.axhline(0, color=INK2, lw=1)
for c, vd in zip(C, GRAY):
    e = (p2.loc[vd, "law"] / p2.loc[vd, "truth"] - 1) * 100
    a.plot(xt, e.values, "-o", color=c, lw=2, ms=6, label=GRAY[vd])
a.set_xscale("log"); a.set_xlim(0.2, 5000)
a.set_xticks(xt); a.set_xticklabels(["0"] + [str(t) for t in TIMES[1:]])
a.set_xlabel("스트레스 시간 (h)", color=INK2); a.set_ylabel("OLED 전류 예측 오차 (%)", color=INK2)
a.set_title("① 열화식 모델 vs 정답 (LTPO)", color=INK, loc="left")
a.set_ylim(top=2.2)
a.legend(frameon=False, fontsize=9, loc="upper left", ncol=3, bbox_to_anchor=(0, 1.0))

# (2) v1 vs v2 error at 0 h
a = ax[1]
w = 0.38; xs = range(len(GRAY))
e1 = [(p1.loc[(vd, 0), "cards"] / p1.loc[(vd, 0), "truth"] - 1) * 100 for vd in GRAY]
e2 = [(p2.loc[(vd, 0), "cards"] / p2.loc[(vd, 0), "truth"] - 1) * 100 for vd in GRAY]
b1 = a.bar([x - w / 2 - 0.01 for x in xs], e1, w, color=C[0], label="v1: 전부 LTPS, 바닥 아래 점 버림")
b2 = a.bar([x + w / 2 + 0.01 for x in xs], e2, w, color=C[1], label="v2: T3·T4 IGZO, 바닥 아래 점 상한 처리")
for bars, vals in ((b1, e1), (b2, e2)):
    for r, v in zip(bars, vals):
        a.text(r.get_x() + r.get_width() / 2, v + (12 if v >= 0 else -30), f"{v:+.0f}%", ha="center", color=INK, fontsize=9)
a.axhline(0, color=INK2, lw=1)
a.set_xticks(list(xs)); a.set_xticklabels([g.split(" ")[0] for g in GRAY.values()])
a.set_ylabel("0h 화소 전류 오차 (추출 모델 / 정답 - 1, %)", color=INK2)
a.set_title("② 누설(GOFF) 처리에 따른 0h 오차", color=INK, loc="left")
a.legend(frameon=False, fontsize=9, loc="upper left")
a.set_ylim(min(min(e2), 0) - 40, max(e1) * 1.15)

# (3) per-TFT contribution at 3000 h, mid gray
a = ax[2]
vd, t = 3.6, BLIND_TIME
base = d[(d.kind == "truth") & (d.vdata == vd) & (d.t_h == 0)].i_nA.iloc[0]
s = d[(d.kind == "sens") & (d.vdata == vd) & (d.t_h == t)].set_index("only").i_nA
chg = [(s[k] / base - 1) * 100 for k in TFTS]
cols = [C[1] if k in IGZO else C[0] for k in TFTS]
ys = list(range(len(TFTS)))[::-1]
a.barh(ys, chg, 0.62, color=cols)
for y, v in zip(ys, chg):
    a.text(v - 0.3 if v < 0 else v + 0.3, y, f"{v:+.2f}%", va="center", ha="right" if v < 0 else "left", color=INK, fontsize=9)
a.axvline(0, color=INK2, lw=1)
a.set_yticks(ys); a.set_yticklabels([f"{k} {ROLES[k]['name']} ({'IGZO' if k in IGZO else 'LTPS'})" for k in TFTS])
a.set_xlim(min(chg) * 1.35, 3)
a.set_xlabel(f"그 TFT만 {t}h 열화했을 때 전류 변화 (%)", color=INK2)
a.set_title("③ TFT별 기여 (중계조, 정답 회로)", color=INK, loc="left")
from matplotlib.patches import Patch
a.legend(handles=[Patch(color=C[0], label="LTPS PMOS"), Patch(color=C[1], label="IGZO NMOS")], frameon=False, fontsize=9, loc="lower left")

fig.suptitle("학습용 합성 예제 — 6T1C LTPO 화소 열화 파이프라인 (공개 문헌 수준 파라미터, 실측·회사 데이터 아님)", color=INK, fontsize=12)
fig.tight_layout()
(ROOT / "figs").mkdir(exist_ok=True)
fig.savefig(ROOT / "figs" / "pipeline_grade.png", dpi=130)
print("saved figs/pipeline_grade.png")
