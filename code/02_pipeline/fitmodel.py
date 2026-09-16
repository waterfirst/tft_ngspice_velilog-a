"""numpy twin of models/ptft_fit.va (must match ngspice to ~1e-6 relative).
Works on magnitudes (|Vgs|, |Vds|), so POL is accepted but unused."""
import numpy as np
# OpenVAF constants.vams values (P_K, P_Q) -> $vt(300.15)
VT = 1.3806503e-23 * 300.15 / 1.602176462e-19

def id_fit(vsg, vsd, W, L, VT0, U0, GAMMA, SS, LAMBDA, GOFF, CI=3.45e-4, POL=1.0,
           TSTRESS=0.0, AVT=0.0, TAUV=100.0, BETAV=0.5, AMU=0.0, TAUM=100.0, BETAM=0.5):
    vsg = np.asarray(vsg, float); vsd = np.asarray(vsd, float)
    n = SS / (VT * np.log(10.0))
    vth = VT0 + AVT * (1 - np.exp(-(TSTRESS / TAUV) ** BETAV))
    x = (vsg - vth) / (n * VT)
    veff = np.where(x > 30, vsg - vth, n * VT * np.log1p(np.exp(np.minimum(x, 30))))
    mu = U0 * 1e-4 * (1 - AMU * (1 - np.exp(-(TSTRESS / TAUM) ** BETAM))) * veff ** GAMMA
    vsde = vsd / (1 + (vsd / (veff + 1e-12)) ** 4) ** 0.25
    return CI * W / L * mu * (veff * vsde - 0.5 * vsde ** 2) * (1 + LAMBDA * vsd) + GOFF * vsd

def id_true(vsg, vsd, W, L, VT0, U0, GAMMA, SS, LAMBDA, GOFF, SIGMA, THETA, CI=3.45e-4,
            TSTRESS=0.0, AVT=0.0, TAUV=200.0, BETAV=0.5, AMU=0.0, TAUM=800.0, **_):
    """numpy twin of models/ptft_true.va (synthetic measurement generator)."""
    vsg = np.asarray(vsg, float); vsd = np.asarray(vsd, float)
    n = SS / (VT * np.log(10.0))
    vth = VT0 + AVT * np.log1p((TSTRESS / TAUV) ** BETAV) - SIGMA * vsd
    x = (vsg - vth) / (n * VT)
    veff = np.where(x > 30, vsg - vth, n * VT * np.log1p(np.exp(np.minimum(x, 30))))
    mu = U0 * 1e-4 * (1 - AMU * (1 - np.exp(-TSTRESS / TAUM))) * veff ** GAMMA / (1 + THETA * veff)
    vsde = vsd / (1 + (vsd / (veff + 1e-12)) ** 2.5) ** 0.4
    return CI * W / L * mu * (veff * vsde - 0.5 * vsde ** 2) * (1 + LAMBDA * vsd) + GOFF * vsd * (1 + 0.1 * vsd)

def id_true(vsg, vsd, W, L, VT0, U0, GAMMA, SS, LAMBDA, GOFF, SIGMA, THETA, CI=3.45e-4, POL=1.0,
            TSTRESS=0.0, AVT=0.0, TAUV=200.0, BETAV=0.5, AMU=0.0, TAUM=800.0):
    """numpy twin of models/ptft_true.va (magnitudes)."""
    vsg = np.asarray(vsg, float); vsd = np.asarray(vsd, float)
    n = SS / (VT * np.log(10.0))
    vth = VT0 + AVT * np.log(1 + (TSTRESS / TAUV) ** BETAV) - SIGMA * vsd
    x = (vsg - vth) / (n * VT)
    veff = np.where(x > 30, vsg - vth, n * VT * np.log1p(np.exp(np.minimum(x, 30))))
    mu = U0 * 1e-4 * (1 - AMU * (1 - np.exp(-TSTRESS / TAUM))) * veff ** GAMMA / (1 + THETA * veff)
    vsde = vsd / (1 + (vsd / (veff + 1e-12)) ** 2.5) ** 0.4
    return CI * W / L * mu * (veff * vsde - 0.5 * vsde ** 2) * (1 + LAMBDA * vsd) + GOFF * vsd * (1 + 0.1 * vsd)
