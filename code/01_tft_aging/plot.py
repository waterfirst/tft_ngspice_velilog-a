import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from pathlib import Path
here = Path(__file__).parent
for f in fm.findSystemFonts():
    if "NanumGothic.ttf" in f:
        fm.fontManager.addfont(f); plt.rcParams["font.family"] = "NanumGothic"; break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["mathtext.fontset"] = "dejavusans"

hours = [0, 10, 100, 1000]
colors = ["#1b4965", "#5fa8d3", "#e09f3e", "#9e2a2b"]
fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))

# (a) transfer curves
d = np.loadtxt(here / "transfer.txt", skiprows=1)
for j, h in enumerate(hours):
    ax[0].semilogy(d[:, 0], np.clip(-d[:, j + 1], 1e-13, None), color=colors[j], lw=2, label=f"{h} h")
ax[0].set(xlabel="Vgs (V)", ylabel="Id (A)", title="① 스트레스 시간별 transfer 곡선 (Vds=10V)")
ax[0].legend(title="stress"); ax[0].grid(alpha=.3, which="both")

# (b) Vth shift model
t = np.logspace(-1, 4, 200)
dv = 3.0 * (1 - np.exp(-(t / 500) ** 0.4))
ax[1].semilogx(t, dv, color="#333", lw=2, label="dVth = 3(1-exp(-(t/500)^0.4))")
for j, h in enumerate(hours[1:], 1):
    ax[1].plot(h, 3.0 * (1 - np.exp(-(h / 500) ** 0.4)), "o", color=colors[j], ms=9)
ax[1].set(xlabel="stress time (h)", ylabel="ΔVth (V)", title="② Verilog-A에 넣은 열화식 (stretched exp.)")
ax[1].legend(loc="upper left", fontsize=9); ax[1].grid(alpha=.3, which="both")

# (c) pixel current retention vs gray level
for vd, c in zip((8, 11, 14), ("#9e2a2b", "#e09f3e", "#1b4965")):
    p = np.loadtxt(here / f"pixel_vdata_{vd}", skiprows=1)
    k = np.argmin(abs(p[:, 0] - 15e-3)); I = p[k, 1:5]
    ax[2].plot([0.3] + hours[1:], I / I[0] * 100, "o-", color=c, lw=2,
               label=f"Vdata {vd}V (초기 {I[0]*1e6:.1f} uA)")
ax[2].set_xscale("log")
ax[2].set_xticks([0.3, 10, 100, 1000]); ax[2].set_xticklabels(["0", "10", "100", "1000"])
ax[2].set(xlabel="drive TFT stress time (h)", ylabel="OLED 전류 유지율 (%)", ylim=(0, 105),
          title="③ 2T1C 화소: 같은 열화, 계조별 전류 감소")
ax[2].legend(fontsize=9); ax[2].grid(alpha=.3, which="both")

# plain-text log tick labels: mathtext minus glyph is missing with the Korean font
from matplotlib.ticker import FuncFormatter
plain = FuncFormatter(lambda v, _: f"{v:.0e}".replace("e-0", "e-").replace("e+0", "e") if v < 1 else f"{v:g}")
ax[0].yaxis.set_major_formatter(plain)
ax[1].xaxis.set_major_formatter(plain)
fig.suptitle("학습용 예제 — ngspice 45.2 + OpenVAF Verilog-A (교과서 파라미터, 실측 아님)", fontsize=12)
fig.tight_layout()
fig.savefig(here / "tft_aging_study.png", dpi=150)
print("saved", here / "tft_aging_study.png")
