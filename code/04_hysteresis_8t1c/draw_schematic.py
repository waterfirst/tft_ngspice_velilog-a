"""Draw the teaching 8T1C schematic with MOSFET symbols as plain SVG (no extra dependency).

Every wire below comes from the netlist (02_pipeline/pixel.py + 03_extension_8t1c/pixel_8t1c.py),
instance order (d g s):
  NT1 nd1 ng ns      NT2 ns s2 data     NT3 nd1 s2n ng     NT4 vinit s1n ng
  NT5 ns em elvdd    NT6 nan em nd1     NT7 vinit s1 nan   NT8 ns s1 vobs
  Cst elvdd ng       Doled nan -> elvss
PMOS (gate bubble): T1 T2 T5 T6 T7 T8 (LTPS).  NMOS: T3 T4 (IGZO).
Run: python draw_schematic.py  ->  ../../textbook/figs/f11_8t1c_schematic.svg
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "textbook" / "figs" / "f11_8t1c_schematic.svg"
INK, IGZO, ADD, MUTE = "#0f172a", "#9a3412", "#d97706", "#475569"
svg = []


def xf(px, py, rot, mirror, x, y):
    """Local symbol point -> canvas point: mirror x, rotate (deg, SVG sense), translate."""
    x = -x if mirror else x
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return round(px + x * c - y * s, 2), round(py + x * s + y * c, 2)


def fet(px, py, kind, rot=0, mirror=False, color=INK, width=2.2):
    """Local frame: terminal A (0,0) top, B (0,60) bottom, gate lead ends at G (-50,30).
    Returns canvas (A, B, G)."""
    t = f'translate({px},{py}) rotate({rot}) scale({-1 if mirror else 1},1)'
    g = [f'<g transform="{t}" stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round">',
         '<path d="M0,0 V14 H-20 M0,60 V46 H-20"/>',
         '<path d="M-20,8 V52" stroke-width="3"/>',
         '<path d="M-28,12 V48" stroke-width="3"/>']
    if kind == "p":
        g += ['<circle cx="-33" cy="30" r="4.5" fill="#fff"/>', '<path d="M-37.5,30 H-50"/>']
    else:
        g += ['<path d="M-28,30 H-50"/>', '<path d="M-20,46 L-9,46 M-14,41 L-9,46 L-14,51" stroke-width="2"/>']
    g.append('</g>')
    svg.extend(g)
    return xf(px, py, rot, mirror, 0, 0), xf(px, py, rot, mirror, 0, 60), xf(px, py, rot, mirror, -50, 30)


def line(*pts, color=INK, w=2.2):
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    svg.append(f'<path d="{d}" stroke="{color}" stroke-width="{w}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')


def dot(x, y):
    svg.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{INK}"/>')


def text(x, y, s, size=15, color=INK, anchor="start", weight=400):
    svg.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def term(x, y, s, dx=10, dy=5, anchor="start", color=INK, weight=400):
    svg.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#fff" stroke="{color}" stroke-width="2"/>')
    text(x + dx, y + dy, s, color=color, anchor=anchor, weight=weight)


def main():
    X, C = 480, 300                                    # main column, NG/Cst column
    # ELVDD rail
    line((C, 90), (720, 90)); dot(C, 90); dot(X, 90); term(720, 90, "ELVDD 4.6 V")

    # T5: elvdd -> ns, gate EM (left)
    line((X, 90), (X, 120))
    a5, b5, g5 = fet(X, 120, "p")
    line(g5, (400, g5[1])); term(400, g5[1], "EM", dx=-12, anchor="end")
    text(496, 157, "T5", weight=700)

    # NS: T2 (DATA) and T8 (VOBS) branches
    line(b5, (X, 320)); dot(X, 220); dot(X, 270)
    text(492, 250, "NS", color=MUTE, weight=700)
    line((X, 220), (560, 220))
    a2, b2, g2 = fet(560, 220, "p", rot=-90, mirror=True)
    line(b2, (720, 220)); term(720, 220, "DATA")
    line(g2, (g2[0], 152)); term(g2[0], 152, "S2", dx=12, dy=5)
    text(648, 208, "T2", weight=700)
    line((X, 270), (560, 270), color=ADD)
    a8, b8, g8 = fet(560, 270, "p", rot=-90, color=ADD)
    line(b8, (720, 270), color=ADD); term(720, 270, "VOBS 5 V", color=ADD, weight=700)
    line(g8, (g8[0], 338), color=ADD); term(g8[0], 338, "S1", dx=12, dy=5, color=ADD)
    text(648, 300, "T8 · OBS", color=ADD, weight=700)

    # T1 drive: ns -> nd1, gate NG (left)
    a1, b1, g1 = fet(X, 320, "p", width=3.2)
    line(g1, (C, g1[1])); dot(C, g1[1])
    text(496, 357, "T1 구동", size=16, weight=700)
    text(C + 10, g1[1] - 10, "NG", color=MUTE, weight=700)

    # Cst between ELVDD and NG
    line((C, 90), (C, 196))
    svg.append(f'<path d="M{C-22},196 H{C+22} M{C-22},208 H{C+22}" stroke="{INK}" stroke-width="3"/>')
    line((C, 208), (C, g1[1]))
    text(C - 30, 207, "Cst 0.3 pF", anchor="end")

    # ND1 and T3 (NMOS, IGZO) back to NG
    line(b1, (X, 440)); dot(X, 440)
    text(492, 434, "ND1", color=MUTE, weight=700)
    line((X, 440), (420, 440), color=IGZO)
    a3, b3, g3 = fet(420, 440, "n", rot=90, mirror=True, color=IGZO)
    line(b3, (C, 440), color=IGZO); dot(C, 440)
    line(g3, (g3[0], 506), color=IGZO); term(g3[0], 506, "S2n", dx=12, dy=5, color=IGZO)
    text(390, 424, "T3", color=IGZO, weight=700, anchor="middle")

    # NG down to T4 (NMOS, IGZO) -> VINIT
    line((C, g1[1]), (C, 520))
    a4, b4, g4 = fet(C, 520, "n", color=IGZO)
    line(g4, (225, g4[1]), color=IGZO); term(225, g4[1], "S1n", dx=-12, anchor="end", color=IGZO)
    text(C + 14, 557, "T4", color=IGZO, weight=700)
    line(b4, (C, 620)); term(C, 620, "VINIT −3.5 V", dx=0, dy=26, anchor="middle")

    # T6: nd1 -> anode, gate EM (right)
    line((X, 440), (X, 470))
    a6, b6, g6 = fet(X, 470, "p", mirror=True)
    line(g6, (560, g6[1])); term(560, g6[1], "EM")
    text(466, 507, "T6", weight=700, anchor="end")

    # ANODE: T7 to VINIT, OLED to ELVSS
    line(b6, (X, 580)); dot(X, 580)
    text(468, 575, "ANODE", color=MUTE, weight=700, anchor="end")
    line((X, 580), (560, 580), color=ADD)
    a7, b7, g7 = fet(560, 580, "p", rot=-90, color=ADD)
    line(b7, (720, 580), color=ADD); term(720, 580, "VINIT −3.5 V", color=ADD, weight=700)
    line(g7, (g7[0], 648), color=ADD); term(g7[0], 648, "S1", dx=12, dy=5, color=ADD)
    text(648, 610, "T7 · 애노드 리셋", color=ADD, weight=700)

    line((X, 580), (X, 622))
    svg.append(f'<path d="M{X-18},622 H{X+18} L{X},652 Z" fill="#fde68a" stroke="{INK}" stroke-width="2.2"/>')
    svg.append(f'<path d="M{X-18},652 H{X+18}" stroke="{INK}" stroke-width="3"/>')
    line((X, 652), (X, 700)); term(X, 700, "ELVSS −3.0 V", dx=0, dy=28, anchor="middle")
    text(506, 644, "OLED")
    svg.append('<path d="M430,600 V668" stroke="#ea580c" stroke-width="3"/><path d="M422,658 L430,672 L438,658 Z" fill="#ea580c"/>')
    text(420, 640, "I_anode", color="#ea580c", weight=700, anchor="end")

    head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 820" '
            "font-family=\"'Noto Sans KR','Noto Sans CJK KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif\">"
            '<rect width="900" height="820" rx="14" fill="#ffffff"/>'
            '<text x="24" y="38" font-size="20" font-weight="700" fill="#0f172a">예시 8T1C 화소 회로 = 교재 6T1C + T7 + T8</text>'
            '<text x="24" y="62" font-size="14" fill="#64748b">합성 예제 · 특정 제조사 회로 아님 · 연결은 넷리스트 pixel_8t1c.py와 1:1</text>')
    legend = (f'<g font-size="14" fill="{INK}">'
              f'<circle cx="40" cy="772" r="5" fill="#fff" stroke="{INK}" stroke-width="2"/><text x="54" y="777">게이트 동그라미 = p형 LTPS</text>'
              f'<rect x="262" y="764" width="18" height="14" rx="3" fill="{IGZO}"/><text x="288" y="777">n형 IGZO (T3·T4, 화살표)</text>'
              f'<rect x="490" y="764" width="18" height="14" rx="3" fill="{ADD}"/><text x="516" y="777">8T1C에서 추가 (T7·T8), 게이트 S1</text>'
              '</g>')
    OUT.write_text(head + "".join(svg) + legend + "</svg>\n")
    print(OUT)


if __name__ == "__main__":
    main()
