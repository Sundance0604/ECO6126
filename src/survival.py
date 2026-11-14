"""Survival-analysis toolkit for Task B (NumPy only, no statsmodels).

Implements from first principles:
  * Kaplan-Meier product-limit estimator, Greenwood variance, log-log bands;
  * restricted mean survival time (RMST) on an integer time grid;
  * Mantel-Cox log-rank test, optionally stratified and window-restricted;
  * Cox partial likelihood (Breslow/Efron ties, strata, start-stop input),
    Newton-Raphson fit with cluster-robust sandwich variance;
  * Firth (Jeffreys-prior) penalised Cox for monotone-likelihood settings,
    with profile penalised-likelihood confidence intervals;
  * discrete-time person-period logit hazard model (IRLS);
  * chi-square tail probabilities via the regularised incomplete gamma.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# --------------------------------------------------------------------------
# distribution helpers
# --------------------------------------------------------------------------


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def chi2_sf(x: float, df: int) -> float:
    """P(chi2_df > x)."""
    if x <= 0 or not np.isfinite(x):
        return 1.0 if x <= 0 else 0.0
    if df == 1:
        return math.erfc(math.sqrt(x / 2.0))
    if df == 2:
        return math.exp(-x / 2.0)
    a, z = df / 2.0, x / 2.0
    if z < a + 1.0:
        ap, s, delta = a, 1.0 / a, 1.0 / a
        for _ in range(10000):
            ap += 1.0
            delta *= z / ap
            s += delta
            if abs(delta) < abs(s) * 1e-15:
                break
        p = s * math.exp(-z + a * math.log(z) - math.lgamma(a))
        return max(0.0, min(1.0, 1.0 - p))
    b = z + 1.0 - a
    c = 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    q = math.exp(-z + a * math.log(z) - math.lgamma(a)) * h
    return max(0.0, min(1.0, q))


# --------------------------------------------------------------------------
# Kaplan-Meier
# --------------------------------------------------------------------------


@dataclass
class KM:
    times: np.ndarray
    survival: np.ndarray
    at_risk: np.ndarray
    n_event: np.ndarray
    n_censor: np.ndarray
    se: np.ndarray
    ci_low: np.ndarray
    ci_high: np.ndarray
    n: int
    events: int
    tmax: int

    def rmst(self, tau: Optional[int] = None) -> float:
        t = self.tmax if tau is None else int(tau)
        return float(self.survival[: t + 1].sum() - self.survival[t])

    def median(self) -> Optional[float]:
        idx = np.where(self.survival <= 0.5)[0]
        return None if len(idx) == 0 else float(self.times[idx[0]])

    def at(self, t: int) -> float:
        return float(self.survival[min(int(t), self.tmax)])


def kaplan_meier(duration: Sequence[float], event: Sequence[int], tmax: int,
                 alpha: float = 0.05) -> KM:
    d = np.asarray(duration, dtype=float)
    e = np.asarray(event, dtype=int)
    if d.shape != e.shape:
        raise ValueError("duration and event must have equal length")
    if len(d) == 0:
        raise ValueError("empty sample")

    t = np.arange(tmax + 1)
    at_risk = (d[:, None] >= t[None, :]).sum(axis=0)
    deaths = ((d[:, None] == t[None, :]) & (e[:, None] == 1)).sum(axis=0)
    cens = ((d[:, None] == t[None, :]) & (e[:, None] == 0)).sum(axis=0)

    surv = np.ones(tmax + 1)
    gw = np.zeros(tmax + 1)
    for k in range(1, tmax + 1):
        n_k, d_k = at_risk[k], deaths[k]
        if n_k > 0 and d_k > 0:
            surv[k] = surv[k - 1] * (1.0 - d_k / n_k)
            gw[k] = gw[k - 1] + (d_k / (n_k * (n_k - d_k)) if n_k > d_k else np.inf)
        else:
            surv[k] = surv[k - 1]
            gw[k] = gw[k - 1]

    with np.errstate(invalid="ignore"):
        se = np.where(surv > 0, surv * np.sqrt(gw), 0.0)
    se = np.nan_to_num(se, nan=0.0, posinf=np.inf)
    z = norm_ppf(1 - alpha / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        ll = np.log(-np.log(np.clip(surv, 1e-12, 1.0)))
        se_ll = np.where(surv > 1e-12, np.sqrt(gw) / np.abs(np.log(np.clip(surv, 1e-12, 1.0))), np.nan)
        lo = np.exp(-np.exp(ll + z * se_ll))
        hi = np.exp(-np.exp(ll - z * se_ll))
    flat = surv >= 1.0 - 1e-12
    lo[flat], hi[flat] = 1.0, 1.0
    # once the curve reaches zero the log-log band is undefined; report (0, 0)
    dead = surv <= 1e-12
    lo[dead], hi[dead] = 0.0, 0.0
    lo = np.clip(np.nan_to_num(lo, nan=0.0), 0.0, 1.0)
    hi = np.clip(np.nan_to_num(hi, nan=1.0), 0.0, 1.0)
    # a band cannot be wider than the identifying information allows: with a
    # single subject left at risk the Greenwood variance is infinite
    hi = np.where(np.isfinite(hi), hi, 1.0)

    return KM(times=t, survival=surv, at_risk=at_risk, n_event=deaths,
              n_censor=cens, se=se, ci_low=lo, ci_high=hi, n=int(len(d)),
              events=int(e.sum()), tmax=tmax)


# --------------------------------------------------------------------------
# log-rank
# --------------------------------------------------------------------------


@dataclass
class LogRank:
    chi2: float
    df: int
    p: float
    observed: float
    expected: float
    n: int
    events: int


def logrank(time: Sequence[float], event: Sequence[int], group: Sequence[int],
            strata: Optional[Sequence] = None,
            window: Optional[Tuple[float, float]] = None) -> LogRank:
    """Mantel-Cox log-rank test for two groups (0/1), summed over strata.

    ``window=(a, b)`` restricts attention to events occurring in (a, b];
    subjects alive at ``a`` enter the risk set at ``a`` (left truncation),
    which yields a valid test of the hazard difference within the window.
    """
    t = np.asarray(time, dtype=float)
    e = np.asarray(event, dtype=int)
    g = np.asarray(group, dtype=int)
    if set(np.unique(g)) - {0, 1}:
        raise ValueError("logrank supports exactly two groups coded 0/1")
    strata = np.zeros(len(t), dtype=int) if strata is None else np.asarray(strata)

    lo_w, hi_w = (0.0, np.inf) if window is None else window
    e_eff = np.where((t > lo_w) & (t <= hi_w), e, 0)
    t_eff = np.maximum(t, lo_w + 1e-9)

    o_sum = e_sum = v_sum = 0.0
    for s in np.unique(strata):
        m = strata == s
        if not m.any():
            continue
        for u in np.unique(t_eff[m & (e_eff == 1)]):
            risk = m & (t_eff >= u) & (t > lo_w)
            dead = m & (t_eff == u) & (e_eff == 1)
            n_u = risk.sum()
            n1 = (risk & (g == 1)).sum()
            d_u = dead.sum()
            d1 = (dead & (g == 1)).sum()
            if n_u < 2 or d_u == 0:
                continue
            o_sum += d1
            e_sum += d_u * n1 / n_u
            v_sum += d_u * (n1 / n_u) * (1 - n1 / n_u) * (n_u - d_u) / (n_u - 1)
    if v_sum <= 0:
        return LogRank(0.0, 1, 1.0, o_sum, e_sum, len(t), int(e_eff.sum()))
    chi2 = (o_sum - e_sum) ** 2 / v_sum
    return LogRank(float(chi2), 1, float(chi2_sf(chi2, 1)), float(o_sum),
                   float(e_sum), len(t), int(e_eff.sum()))


# --------------------------------------------------------------------------
# Cox partial likelihood
# --------------------------------------------------------------------------


class CoxProblem:
    """Holds the risk-set structure so the likelihood can be re-evaluated."""

    def __init__(self, time, event, X, names=None, strata=None,
                 start=None, ties="efron"):
        t = np.asarray(time, dtype=float)
        e = np.asarray(event, dtype=int)
        X = np.atleast_2d(np.asarray(X, dtype=float))
        if X.shape[0] != len(t):
            X = X.T
        self.X = X
        self.n, self.p = X.shape
        self.names = list(names) if names is not None else [f"x{j}" for j in range(self.p)]
        self.strata = np.zeros(self.n, dtype=int) if strata is None else np.asarray(strata)
        self.start = np.zeros(self.n) if start is None else np.asarray(start, float)
        self.stop = t
        self.event = e
        self.ties = ties
        if ties not in ("efron", "breslow"):
            raise ValueError("ties must be 'efron' or 'breslow'")
        self.sets = self._risk_sets()
        self.zero_event_strata = [
            float(s) for s in np.unique(self.strata)
            if e[self.strata == s].sum() == 0
        ]

    def _risk_sets(self):
        out = []
        for s in np.unique(self.strata):
            m = np.where(self.strata == s)[0]
            for u in np.unique(self.stop[m][self.event[m] == 1]):
                idx = m[(self.start[m] < u) & (self.stop[m] >= u)]
                dead = m[(self.stop[m] == u) & (self.event[m] == 1)]
                if len(idx) and len(dead):
                    out.append((float(u), idx, dead))
        return out

    def loglik(self, beta: np.ndarray, want_score: bool = False):
        X, eta = self.X, None
        beta = np.asarray(beta, dtype=float)
        eta = np.clip(X @ beta, -50.0, 50.0)
        w = np.exp(eta)
        ll, grad, hess = 0.0, np.zeros(self.p), np.zeros((self.p, self.p))
        score = np.zeros((self.n, self.p)) if want_score else None
        for _, R, D in self.sets:
            Xr, wr = X[R], w[R]
            Xd, wd = X[D], w[D]
            d = len(D)
            s0, s1 = wr.sum(), wr @ Xr
            s2 = (Xr * wr[:, None]).T @ Xr
            d0, d1 = wd.sum(), wd @ Xd
            d2 = (Xd * wd[:, None]).T @ Xd
            ll += eta[D].sum()
            grad += Xd.sum(axis=0)
            if want_score:
                score[D] += Xd
            if self.ties == "breslow":
                if s0 <= 0:
                    continue
                xbar = s1 / s0
                ll -= d * math.log(s0)
                grad -= d * xbar
                hess -= d * (s2 / s0 - np.outer(xbar, xbar))
                if want_score:
                    score[R] -= d * (wr[:, None] * (Xr - xbar)) / s0
            else:
                for r in range(d):
                    c = r / d
                    a0, a1, a2 = s0 - c * d0, s1 - c * d1, s2 - c * d2
                    if a0 <= 0:
                        continue
                    xbar = a1 / a0
                    ll -= math.log(a0)
                    grad -= xbar
                    hess -= a2 / a0 - np.outer(xbar, xbar)
                    if want_score:
                        score[R] -= (wr[:, None] * (Xr - xbar)) / a0
        if want_score:
            return ll, grad, hess, score
        return ll, grad, hess


@dataclass
class CoxResult:
    names: List[str]
    beta: np.ndarray
    se: np.ndarray
    se_model: np.ndarray
    loglik: float
    iters: int
    converged: bool
    separated: bool
    n: int
    events: int
    clusters: int
    ties: str
    problem: CoxProblem = field(repr=False, default=None)
    info_robust: np.ndarray = field(repr=False, default=None)

    @property
    def hr(self) -> np.ndarray:
        return np.exp(self.beta)

    def summary(self, alpha: float = 0.05) -> Dict[str, np.ndarray]:
        crit = norm_ppf(1 - alpha / 2)
        se = np.where(self.se > 0, self.se, np.nan)
        z = self.beta / se
        p = np.array([chi2_sf(float(v) ** 2, 1) for v in z])
        with np.errstate(over="ignore"):
            lo = np.exp(np.clip(self.beta - crit * se, -50, 50))
            hi = np.exp(np.clip(self.beta + crit * se, -50, 50))
        return {"term": np.array(self.names), "coef": self.beta, "hr": np.exp(self.beta),
                "se": self.se, "z": z, "p": p, "ci_low": lo, "ci_high": hi}

    def wald(self, idx: Sequence[int]) -> Tuple[float, int, float]:
        idx = list(idx)
        b = self.beta[idx]
        V = self.info_robust[np.ix_(idx, idx)]
        stat = float(b @ np.linalg.pinv(V) @ b)
        return stat, len(idx), float(chi2_sf(stat, len(idx)))


def cox_fit(time, event, X, names=None, strata=None, cluster=None,
            ties="efron", start=None, max_iter=80, tol=1e-9,
            separation_cut=8.0) -> CoxResult:
    prob = CoxProblem(time, event, X, names=names, strata=strata, start=start, ties=ties)
    n = prob.n
    cluster = np.arange(n) if cluster is None else np.asarray(cluster)
    beta = np.zeros(prob.p)
    converged, it = False, 0
    ll_prev = -np.inf
    ll = prob.loglik(beta)[0]
    for it in range(1, max_iter + 1):
        ll, grad, hess = prob.loglik(beta)
        try:
            step = np.linalg.solve(-hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(-hess, grad, rcond=None)[0]
        lr = 1.0
        while lr > 1e-6:
            cand = beta + lr * step
            ll_new = prob.loglik(cand)[0]
            if np.isfinite(ll_new) and ll_new >= ll - 1e-12:
                break
            lr *= 0.5
        beta = beta + lr * step
        if abs(ll_new - ll_prev) < tol and np.max(np.abs(step * lr)) < 1e-7:
            converged, ll_prev = True, ll_new
            beta = beta if np.all(np.isfinite(beta)) else np.zeros(prob.p)
            break
        ll_prev = ll_new

    ll, grad, hess, score = prob.loglik(beta, want_score=True)
    info = -hess
    with np.errstate(invalid="ignore"):
        try:
            se_model = np.sqrt(np.diag(np.linalg.pinv(info)))
        except np.linalg.LinAlgError:
            se_model = np.full(prob.p, np.nan)

    cl = np.unique(cluster)
    G = len(cl)
    order = np.argsort(cluster)
    cs = np.cumsum(np.vstack([np.zeros(prob.p), score[order]]), axis=0)
    left = np.searchsorted(cluster[order], cl, side="left")
    right = np.searchsorted(cluster[order], cl, side="right")
    meat = np.zeros((prob.p, prob.p))
    for lo_i, hi_i in zip(left, right):
        u = cs[hi_i] - cs[lo_i]
        meat += np.outer(u, u)
    if G > 1:
        meat *= G / (G - 1)
    try:
        inv = np.linalg.pinv(info)
        V = inv @ meat @ inv
        se = np.sqrt(np.clip(np.diag(V), 0, np.inf))
    except np.linalg.LinAlgError:
        V = np.full((prob.p, prob.p), np.nan)
        se = np.full(prob.p, np.nan)

    separated = bool(np.max(np.abs(beta)) > separation_cut) or not converged
    return CoxResult(names=prob.names, beta=beta, se=se, se_model=se_model,
                     loglik=ll, iters=it, converged=converged, separated=separated,
                     n=n, events=int(np.asarray(event).sum()), clusters=G,
                     ties=ties, problem=prob, info_robust=V)


@dataclass
class FirthResult:
    names: List[str]
    beta: np.ndarray
    se: np.ndarray
    ci_low: np.ndarray
    ci_high: np.ndarray
    loglik_pen: float
    n: int
    events: int
    note: str = ""

    @property
    def hr(self) -> np.ndarray:
        return np.exp(self.beta)

    def summary(self) -> Dict[str, np.ndarray]:
        z = self.beta / np.where(self.se > 0, self.se, np.nan)
        p = np.array([chi2_sf(float(v) ** 2, 1) for v in z])
        return {"term": np.array(self.names), "coef": self.beta, "hr": np.exp(self.beta),
                "se": self.se, "z": z, "p": p, "ci_low": np.exp(self.ci_low),
                "ci_high": np.exp(self.ci_high)}


def firth_cox(time, event, X, names=None, strata=None, ties="efron",
              alpha: float = 0.05) -> FirthResult:
    """Firth-penalised Cox: maximises l(beta) + 0.5 log|I(beta)|.

    The penalty keeps estimates finite under monotone likelihood (complete
    separation), which occurs here because expulsion shifts all collapse
    times past the window in low-rho markets.
    """
    prob = CoxProblem(time, event, X, names=names, strata=strata, ties=ties)
    p = prob.p

    def penalised(beta):
        ll, grad, hess = prob.loglik(beta)
        info = -hess
        sign, logdet = np.linalg.slogdet(info)
        if sign <= 0 or not np.isfinite(logdet):
            return -np.inf, None, None
        inv = np.linalg.inv(info)
        pen = ll + 0.5 * logdet
        # d/dbeta 0.5 log|I| = 0.5 tr(I^-1 dI/dbeta); compute numerically
        eps = 1e-5
        g_pen = grad.copy()
        for k in range(p):
            e_k = np.zeros(p)
            e_k[k] = eps
            hess_p = -prob.loglik(beta + e_k)[2]
            hess_m = -prob.loglik(beta - e_k)[2]
            dI = (hess_p - hess_m) / (2 * eps)
            g_pen[k] += 0.5 * np.trace(inv @ dI)
        return pen, g_pen, inv

    beta = np.zeros(p)
    converged = False
    for it in range(1, 60):
        pen, grad, inv = penalised(beta)
        if not np.isfinite(pen):
            beta = beta * 0.5
            continue
        # numerical Hessian of the penalised objective
        eps = 1e-4
        H = np.zeros((p, p))
        for k in range(p):
            e_k = np.zeros(p); e_k[k] = eps
            gp = penalised(beta + e_k)[1]
            gm = penalised(beta - e_k)[1]
            if gp is None or gm is None:
                return FirthResult(prob.names, np.full(p, np.nan), np.full(p, np.nan),
                                   np.full(p, np.nan), np.full(p, np.nan), np.nan,
                                   prob.n, int(np.asarray(event).sum()), "Hessian failure")
            H[:, k] = (gp - gm) / (2 * eps)
        try:
            step = np.linalg.solve(-H, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(-H, grad, rcond=None)[0]
        lr = 1.0
        while lr > 1e-6:
            if penalised(beta + lr * step)[0] >= pen - 1e-12:
                break
            lr *= 0.5
        beta = beta + lr * step
        if np.max(np.abs(step * lr)) < 1e-7:
            converged = True
            break

    pen_hat, _, inv = penalised(beta)
    se = np.sqrt(np.clip(np.diag(inv), 0, np.inf))

    # profile penalised-likelihood intervals (only meaningful for p == 1)
    lo = beta - norm_ppf(1 - alpha / 2) * se
    hi = beta + norm_ppf(1 - alpha / 2) * se
    if p == 1:
        crit = chi2_sf_inv(1 - alpha, 1)

        def f(x):
            v = penalised(np.array([float(x)]))[0]
            if not np.isfinite(v):
                return np.inf if v < 0 else -np.inf
            return 2 * (pen_hat - v) - crit

        lo = _scan_root(f, beta[0], -40.0, beta[0])
        hi = _scan_root(f, beta[0], beta[0], 40.0)
    note = "" if converged else "Newton did not fully converge"
    return FirthResult(prob.names, beta, se, np.array([lo]), np.array([hi]),
                       pen_hat, prob.n, int(np.asarray(event).sum()), note)


def chi2_sf_inv(p: float, df: int) -> float:
    lo, hi = 0.0, 200.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 1 - chi2_sf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _scan_root(f, start, lo, hi, step=0.05):
    """Walk from ``start`` towards ``lo`` (or ``hi``) and refine the first sign change."""
    direction = -1 if lo < start else 1
    end = lo if direction < 0 else hi
    x_prev, f_prev = start, f(start)
    x = start
    while (x - end) * direction < 0:
        x = x + direction * step
        fx = f(x)
        if not np.isfinite(fx):
            fx = np.inf if fx > 0 else -np.inf
        if np.isfinite(f_prev) and np.isfinite(fx) and f_prev * fx <= 0:
            return _bisect_root(f, min(x_prev, x), max(x_prev, x))
        x_prev, f_prev = x, fx
    return np.nan


def _bisect_root(f, lo, hi):
    flo, fhi = f(lo), f(hi)
    if not np.isfinite(flo) or not np.isfinite(fhi):
        return np.nan
    if flo * fhi > 0:
        return np.nan
    for _ in range(120):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if not np.isfinite(fm):
            hi = mid
            continue
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------
# discrete-time hazard
# --------------------------------------------------------------------------


@dataclass
class DiscreteHazard:
    names: List[str]
    beta: np.ndarray
    se: np.ndarray
    loglik: float
    iters: int
    converged: bool
    rows: int


def discrete_hazard(time, event, covariates, cov_names, interval_edges,
                    cluster=None, max_iter=80, tol=1e-8) -> DiscreteHazard:
    t = np.asarray(time, dtype=int)
    e = np.asarray(event, dtype=int)
    Z = np.atleast_2d(np.asarray(covariates, dtype=float))
    if Z.shape[0] != len(t):
        Z = Z.T
    edges = np.asarray(sorted(interval_edges), dtype=int)
    nb = len(edges) - 1

    n = len(t)
    counts = np.clip(t, 1, None).astype(int)
    total = int(counts.sum())
    subj = np.repeat(np.arange(n), counts)
    period = np.concatenate([np.arange(1, c + 1) for c in counts]) if n else np.array([], int)
    y = np.zeros(total)
    ends = np.cumsum(counts)
    for i in np.where(e == 1)[0]:
        if counts[i] > 0:
            y[ends[i] - 1] = 1.0
    b = np.clip(np.searchsorted(edges, period, side="right") - 1, 0, nb - 1)
    Xb = np.zeros((total, nb))
    Xb[np.arange(total), b] = 1.0
    X = np.hstack([Xb, Z[subj]])
    names = [f"hazard[{edges[k]}-{edges[k + 1] - 1}]" for k in range(nb)] + list(cov_names)

    p = X.shape[1]
    beta = np.zeros(p)
    base = min(max(y.mean(), 1e-3), 1 - 1e-3)
    beta[:nb] = math.log(base / (1 - base))
    converged, it, ll_prev = False, 0, -np.inf
    for it in range(1, max_iter + 1):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = mu * (1 - mu)
        grad = X.T @ (y - mu)
        hess = -(X * w[:, None]).T @ X
        try:
            step = np.linalg.solve(-hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(-hess, grad, rcond=None)[0]
        lr = 1.0
        ll = float(np.sum(y * eta - np.logaddexp(0, eta)))
        while lr > 1e-6:
            eta2 = np.clip(X @ (beta + lr * step), -30, 30)
            ll2 = float(np.sum(y * eta2 - np.logaddexp(0, eta2)))
            if np.isfinite(ll2) and ll2 >= ll - 1e-12:
                break
            lr *= 0.5
        beta = beta + lr * step
        if abs(ll2 - ll_prev) < tol and np.max(np.abs(step * lr)) < 1e-7:
            converged, ll_prev = True, ll2
            break
        ll_prev = ll2

    eta = np.clip(X @ beta, -30, 30)
    mu = 1.0 / (1.0 + np.exp(-eta))
    info = (X * (mu * (1 - mu))[:, None]).T @ X
    se = np.sqrt(np.clip(np.diag(np.linalg.pinv(info)), 0, np.inf))
    ll = float(np.sum(y * eta - np.logaddexp(0, eta)))
    return DiscreteHazard(names, beta, se, ll, it, converged, total)


# --------------------------------------------------------------------------
# bootstrap helpers
# --------------------------------------------------------------------------


class SeedBlockBootstrap:
    def __init__(self, seeds, n_boot: int, rng_seed: int):
        self.seeds = np.unique(np.asarray(seeds))
        self.n_boot = int(n_boot)
        self.rng = np.random.default_rng(rng_seed)

    def draws(self):
        for _ in range(self.n_boot):
            yield self.rng.choice(self.seeds, size=len(self.seeds), replace=True)


def percentile_ci(samples: Sequence[float], alpha: float = 0.05):
    a = np.asarray([s for s in samples if s is not None and np.isfinite(s)], dtype=float)
    if len(a) == 0:
        return (np.nan, np.nan, np.nan, 0)
    return (float(np.quantile(a, alpha / 2)), float(np.quantile(a, 1 - alpha / 2)),
            float(a.std(ddof=1)), len(a))
