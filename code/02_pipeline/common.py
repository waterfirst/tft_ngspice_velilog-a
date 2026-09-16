"""Shared config and ngspice runner for the synthetic 6T1C aging pipeline.
Everything here is synthetic/textbook. No company or university data."""
import math, subprocess, tempfile, os, shutil
from pathlib import Path
import numpy as np

ROOT = Path(__file__).parent
MODELS = ROOT / "models"
# set NGSPICE=/path/to/ngspice if it is not on PATH
NGSPICE = os.environ.get("NGSPICE") or shutil.which("ngspice") or "ngspice"
WORKERS = max(1, min(14, (os.cpu_count() or 2) - 1))
# default abstol (1 pA) makes sub-pA subthreshold currents inaccurate -> tighten for I-V work
OPTIONS = ".options abstol=1e-16 reltol=1e-6 vntol=1e-9"

# Public textbook 6T1C with LTPO option: gate-node switches (T3 compensation, T4 init) are IGZO NMOS,
# the rest LTPS PMOS. Change IGZO to move switches between technologies.
# duty / |Vgs| describe the on-state stress each TFT sees in one frame.
ROLES = {
    "T1": dict(name="구동 TFT",           W=4e-6, L=30e-6, duty=0.946, vgs=3.0),
    "T2": dict(name="데이터 스위치",       W=4e-6, L=4e-6,  duty=0.012, vgs=10.0),
    "T3": dict(name="문턱보상 스위치",     W=4e-6, L=4e-6,  duty=0.012, vgs=10.0),
    "T4": dict(name="게이트 초기화",       W=4e-6, L=4e-6,  duty=0.012, vgs=10.0),
    "T5": dict(name="발광 스위치(전원측)", W=4e-6, L=4e-6,  duty=0.946, vgs=11.6),
    "T6": dict(name="발광 스위치(OLED측)", W=4e-6, L=4e-6,  duty=0.946, vgs=11.0),
}
TFTS = list(ROLES)
IGZO = {"T3", "T4"}
def pol(k): return -1.0 if k in IGZO else 1.0

# Public-literature-level technology defaults (not measured data).
# Ioff targets at |Vds|=5 V: LTPS ~1.5 pA, IGZO ~1e-14 A.
TECH = {
    "LTPS_P": dict(VT0=1.2, U0=80, SS=0.30, GAMMA=0.15, LAMBDA=0.02, GOFF=2e-13, SIGMA=0.02, THETA=0.05),
    "IGZO_N": dict(VT0=0.8, U0=12, SS=0.15, GAMMA=0.25, LAMBDA=0.01, GOFF=1.3e-15, SIGMA=0.01, THETA=0.02),
}
def tech(k): return "IGZO_N" if k in IGZO else "LTPS_P"
NOISE_A = 5e-15                            # instrument current noise (1 sigma)
FLOOR_A = 3 * NOISE_A                      # below this a reading only bounds the current from above
FIT_TIMES = [0, 10, 30, 100, 300, 1000]   # hours used for extraction / aging-law fit
BLIND_TIME = 3000                          # never used for fitting

def truth_params(seed=7):
    """Per-TFT truth parameters: device-to-device variation + stress-driven aging."""
    rng = np.random.default_rng(seed)
    out = {}
    for k, r in ROLES.items():
        s = r["duty"] * (r["vgs"] / 5.0) ** 2           # stress index
        dvt_1000 = 2.5 * s / (1 + s)                     # |Vth| shift at 1000 h [V]
        dmu_1000 = 0.10 * s / (1 + s)                    # mobility loss fraction at 1000 h
        b = TECH[tech(k)]
        out[k] = dict(
            W=r["W"], L=r["L"],
            VT0=b["VT0"] + rng.normal(0, 0.05), U0=b["U0"] * (1 + rng.normal(0, 0.03)),
            SS=b["SS"] * (1 + rng.normal(0, 0.05)), GAMMA=b["GAMMA"], LAMBDA=b["LAMBDA"], GOFF=b["GOFF"],
            SIGMA=b["SIGMA"], THETA=b["THETA"], POL=pol(k),
            AVT=dvt_1000 / math.log(1 + (1000 / 200) ** 0.5), TAUV=200, BETAV=0.5,
            AMU=dmu_1000 / (1 - math.exp(-1000 / 800)), TAUM=800,
            stress=s, dvt_1000=dvt_1000, dmu_1000=dmu_1000)
    return out

def model_line(name, module, p, tstress=None):
    keys = [k for k in p if k.isupper()]
    s = " ".join(f"{k}={p[k]:.12g}" for k in keys)
    if tstress is not None:
        s += f" TSTRESS={tstress:g}"
    return f".model {name} {module} {s}"

def run_ngspice(netlist: str, outputs: list[str], workdir: Path):
    """Run ngspice in batch mode inside workdir; return dict of loaded wrdata tables."""
    workdir.mkdir(parents=True, exist_ok=True)
    cir = workdir / "run.cir"
    cir.write_text(netlist)
    r = subprocess.run([NGSPICE, "-b", str(cir)], cwd=workdir, capture_output=True, text=True, timeout=900)
    bad = [l for l in (r.stdout + r.stderr).splitlines()
           if l.lower().startswith("error") or "singular" in l.lower() or "timestep too small" in l.lower()]
    if bad or r.returncode != 0:
        raise RuntimeError(f"ngspice failed in {workdir}: {bad[:5]} rc={r.returncode}")
    res = {}
    for o in outputs:
        f = workdir / o
        with open(f) as fh:
            header = [c.lower() for c in fh.readline().split()]
        res[o] = (header, np.loadtxt(f, skiprows=1, ndmin=2))
    return res
