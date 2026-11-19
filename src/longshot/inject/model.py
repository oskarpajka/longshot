"""Transit models for injection-recovery tests (batman, quadratic limb darkening)."""

from __future__ import annotations

import batman
import numpy as np

G = 6.674e-11
RSUN = 6.957e8
MSUN = 1.989e30
REARTH = 6.371e6


def a_over_rs(period_d: float, mstar: float, rstar: float) -> float:
    p = period_d * 86400.0
    a = (G * mstar * MSUN * p**2 / (4 * np.pi**2)) ** (1 / 3)
    return a / (rstar * RSUN)


def total_duration_d(period_d: float, aors: float, k: float, b: float) -> float:
    """T14 for a circular orbit (Winn 2010 eq. 14)."""
    inc = np.arccos(b / aors)
    arg = np.sqrt((1 + k) ** 2 - b**2) / (aors * np.sin(inc))
    return period_d / np.pi * np.arcsin(np.clip(arg, 0, 1))


def transit_flux(
    time: np.ndarray, t0: float, period_d: float, k: float, aors: float, b: float,
    u: tuple[float, float] = (0.25, 0.35), supersample: int = 1, exp_time_d: float = 0.0,
) -> np.ndarray:
    params = batman.TransitParams()
    params.t0 = t0
    params.per = period_d
    params.rp = k
    params.a = aors
    params.inc = float(np.degrees(np.arccos(b / aors)))
    params.ecc = 0.0
    params.w = 90.0
    params.limb_dark = "quadratic"
    params.u = list(u)
    kw = {}
    if supersample > 1 and exp_time_d > 0:
        kw = {"supersample_factor": supersample, "exp_time": exp_time_d}
    m = batman.TransitModel(params, np.asarray(time, float), **kw)
    return m.light_curve(params)
