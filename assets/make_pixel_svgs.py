"""Draw comparable 6T1C / 7T1C / 8T1C LTPO pixel schematics (public-literature topology, SDC-style numbering).
Same layout for all three so the added TFT is the only visual difference."""
from pathlib import Path

LTPS, OXIDE, NEW = "#2a78d6", "#eb6834", "#16a34a"
INK, MUTE, WIRE = "#1b1a17", "#7a776d", "#46443d"
OUT = Path(__file__).parent


def svg(n):
    e = []  # elements
    def line(x1, y1, x2, y2, c=WIRE, w=2.2, dash=""):
        e.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{w}" {dash}/>')
    def dot(x, y):
        e.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{WIRE}"/>')
    def text(x, y, s, size=15, c=INK, anchor="middle", weight=500):
        e.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}" font-weight="{weight}">{s}</text>')
    def tft(cx, cy, name, role, kind, gate, new=False, w=92, h=50, side=False):
        col = LTPS if kind == "p" else OXIDE
        stroke = NEW if new else col
        dash = 'stroke-dasharray="7 4"' if new else ""
        fill = "#effaf3" if new else ("#eef4fc" if kind == "p" else "#fdf0e8")
        e.append(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="{3 if new else 2.2}" {dash}/>')
        text(cx, cy - 3, name, 17, INK, weight=800)
        text(cx, cy + 15, gate, 12, MUTE)
        if side:
            text(cx + w / 2 + 10, cy + 5, role, 12.5, stroke if new else col, 'start', 700)
        else:
            text(cx, cy + h / 2 + 17, role, 12.5, stroke if new else col, weight=700)

    W, H = 900, 640
    # rails
    line(120, 70, 800, 70, INK, 3); text(810, 76, "ELVDD", 15, INK, "start", 700)
    line(120, 600, 800, 600, INK, 3); text(810, 606, "ELVSS", 15, INK, "start", 700)
    X1 = 520                          # drive column
    N1, N3, AN = 250, 380, 500        # T1 source, T1 drain, anode
    # T5 (VDD -> N1)
    line(X1, 70, X1, 125); tft(X1, 150, "T5", "발광", "p", "EM", side=True); line(X1, 175, X1, N1)
    dot(X1, N1)
    # T1 drive
    line(X1, N1, X1, 290); tft(X1, 315, "T1", "구동 TFT", "p", "gate=N2", w=110, h=56, side=True); line(X1, 343, X1, N3)
    dot(X1, N3)
    # T2 data: DATA -> N1
    line(X1, N1, 610, N1); tft(660, N1, "T2", "데이터", "p", "Scan1"); line(706, N1, 820, N1)
    line(820, 110, 820, N1, WIRE); text(820, 100, "DATA", 15, INK, weight=700)
    # gate node N2 and Cst
    NX2, NY2 = 400, 315
    line(NX2, NY2, X1 - 55, NY2); dot(NX2, NY2); text(NX2 + 18, NY2 - 10, "N2", 13, MUTE)
    line(NX2, NY2, NX2, 170); line(NX2 - 22, 170, NX2 + 22, 170, INK, 3); line(NX2 - 22, 160, NX2 + 22, 160, INK, 3)
    line(NX2, 160, NX2, 70); dot(NX2, 70); text(NX2 - 32, 170, "Cst", 14, INK, "end", 700)
    # T3 compensation: N2 <-> N3 (oxide)
    line(NX2, NY2, NX2, 355); tft(NX2, 380, "T3", "Vth 보상", "n", "Scan2")
    line(NX2 + 46, 380, X1, 380)
    # T4 gate init: N2 -> VINT (oxide)
    line(NX2, 250, 300, 250); dot(NX2, 250); tft(254, 250, "T4", "게이트 초기화", "n", "Scan3")
    line(208, 250, 150, 250); text(140, 256, "VINT", 14, INK, "end", 700)
    # T6 emission: N3 -> anode
    line(X1, N3, X1, 420); tft(X1, 445, "T6", "발광 스위치", "p", "EM", side=True); line(X1, 470, X1, AN)
    dot(X1, AN)
    # OLED
    line(X1, AN, X1, 535)
    e.append(f'<polygon points="{X1-18},535 {X1+18},535 {X1},565" fill="#fde68a" stroke="{INK}" stroke-width="2"/>')
    line(X1 - 18, 565, X1 + 18, 565, INK, 2.5); line(X1, 565, X1, 600); text(X1 + 30, 558, "OLED", 14, INK, "start", 700)
    if n >= 7:
        line(X1, AN, 640, AN); tft(690, AN, "T7", "애노드 초기화", "p", "Scan4", new=(n == 7))
        line(736, AN, 780, AN); text(790, AN + 5, "VAINT", 14, INK, "start", 700)
    if n >= 8:
        # T8 on-bias: VOBS -> N1
        line(X1, 212, 640, 212); dot(X1, 212); line(640, 212, 640, 150); line(640, 150, 655, 150)
        tft(702, 150, "T8", "On-bias (OBS)", "p", "Scan4", new=True, w=94, h=46)
        line(749, 150, 770, 150); text(776, 155, "VOBS", 14, INK, "start", 700)
    title = {6: "6T1C — 내부 Vth 보상 기본형", 7: "7T1C — + T7 애노드 초기화 (모바일 표준형)", 8: "8T1C — + T8 On-bias (저주파·히스테리시스 대책)"}[n]
    text(40, 36, title, 20, INK, "start", 800)
    legend = (f'<rect x="40" y="612" width="14" height="14" rx="3" fill="#eef4fc" stroke="{LTPS}" stroke-width="2"/>'
              f'<text x="60" y="624" font-size="12.5" fill="{MUTE}">LTPS PMOS</text>'
              f'<rect x="150" y="612" width="14" height="14" rx="3" fill="#fdf0e8" stroke="{OXIDE}" stroke-width="2"/>'
              f'<text x="170" y="624" font-size="12.5" fill="{MUTE}">산화물 NMOS (LTPO)</text>'
              + (f'<rect x="300" y="612" width="14" height="14" rx="3" fill="#effaf3" stroke="{NEW}" stroke-width="2.5" stroke-dasharray="4 2"/>'
                 f'<text x="320" y="624" font-size="12.5" fill="{MUTE}">이번 단계에서 추가</text>' if n > 6 else ""))
    body = "\n".join(e)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H+10}" font-family="Noto Sans KR, NanumSquare_ac, sans-serif">'
            f'<rect width="100%" height="100%" fill="#ffffff"/>{body}{legend}</svg>')


for n in (6, 7, 8):
    (OUT / f"pixel_{n}t1c_ltpo.svg").write_text(svg(n), encoding="utf-8")
print("ok")
