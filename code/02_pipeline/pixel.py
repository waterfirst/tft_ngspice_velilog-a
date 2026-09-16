"""6T1C pixel (public textbook topology, internal Vth compensation). Devices in common.IGZO are NMOS on active-high scans.
T1 drive | T2 data switch | T3 diode-connect (compensation) | T4 gate init | T5 ELVDD emission switch | T6 OLED emission switch."""
import os, re, subprocess
from common import *

FRAME = 16.667e-3
def scan(k, line): return line + "n" if k in IGZO else line
def netlist(module, cards, vdata, frames=2, probe=False):
    """cards: dict TFT -> parameter dict (may include TSTRESS)."""
    osdi = MODELS / f"{module}.osdi"
    L = ["* 6T1C pixel", OPTIONS]
    for k in TFTS:
        p = dict(cards[k]); t = p.pop("TSTRESS", None)
        L.append(model_line(f"m{k}", module, p, tstress=t))
    L += [".model oled D(IS=6e-26 N=3 RS=10k CJO=0.3p)",
          "Velvdd elvdd 0 4.6", "Velvss elvss 0 -3.0", "Vinit vinit 0 -3.5", f"Vdata data 0 {vdata}",
          # scan/emission waveforms (VGH=7, VGL=-7). init 0.5-0.7 ms, program 0.8-1.0 ms, emission off 0.3-1.2 ms
          f"Vs1 s1 0 PULSE(7 -7 0.5m 10u 10u 0.2m {FRAME})",
          f"Vs2 s2 0 PULSE(7 -7 0.8m 10u 10u 0.2m {FRAME})",
          f"Vem em 0 PULSE(-7 7 0.3m 10u 10u 0.9m {FRAME})",
          # active-high copies of the scan lines for NMOS (IGZO) switches
          f"Vs1n s1n 0 PULSE(-7 7 0.5m 10u 10u 0.2m {FRAME})",
          f"Vs2n s2n 0 PULSE(-7 7 0.8m 10u 10u 0.2m {FRAME})",
          "NT1 nd1 ng ns mT1",
          f"NT2 ns {scan('T2', 's2')} data mT2",
          f"NT3 nd1 {scan('T3', 's2')} ng mT3",
          f"NT4 vinit {scan('T4', 's1')} ng mT4",
          "NT5 ns em elvdd mT5",
          "NT6 nan em nd1 mT6",
          "Cst elvdd ng 0.3p",
          "Vsense nan no 0", "Doled no elvss oled",
          ".control", "set num_threads=1", f"pre_osdi {osdi}",
          f"tran 5u {frames * FRAME:.6g} 0 5u",
          f"meas tran iavg AVG i(Vsense) from={FRAME * (frames - 1) + 1.5e-3:.6g} to={frames * FRAME - 0.2e-3:.6g}",
          f"meas tran vg_hold AVG v(ng) from={FRAME * (frames - 1) + 1.5e-3:.6g} to={frames * FRAME - 0.2e-3:.6g}"]
    if probe:
        L += ["set wr_singlescale", "set wr_vecnames", "wrdata probe.txt v(ng) v(ns) v(nan) i(Vsense) v(s1) v(s2) v(em)"]
    L += [".endc", ".end"]
    return "\n".join(L) + "\n"

def run_pixel(module, cards, vdata, workdir, probe=False):
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "run.cir").write_text(netlist(module, cards, vdata, probe=probe))
    env = {**os.environ, "OMP_NUM_THREADS": "1"}   # parallel pool: avoid thread oversubscription
    r = subprocess.run([NGSPICE, "-b", "run.cir"], cwd=workdir, capture_output=True, text=True, timeout=120, env=env)
    txt = r.stdout + r.stderr
    got = dict(re.findall(r"^(iavg|vg_hold)\s*=\s*([-+0-9.eE]+)", txt, re.M))
    if "iavg" not in got:
        raise RuntimeError(f"pixel sim failed {workdir}: " + " | ".join(l for l in txt.splitlines() if "rror" in l or "fail" in l.lower())[:400])
    return float(got["iavg"]), float(got["vg_hold"])
