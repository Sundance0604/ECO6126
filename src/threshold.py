"""Small econometrics toolkit for Task C (NumPy only).

  * OLS with cluster-robust (sandwich) covariance;
  * seed-block bootstrap of the coefficient vector;
  * Romano-Wolf step-down adjusted p-values for a family of coefficients;
  * quadratic fit with vertex and a bootstrap distribution of the grid argmax.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


def norm_ppf(p: float) -> float:
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 0.5 * (1.0 + math.erf(mid / math.sqrt(2.0))) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@dataclass
class OLS:
    names: list
    beta: np.ndarray
    se: np.ndarray
    se_iid: np.ndarray
    resid: np.ndarray
    n: int
    k: int
    clusters: int
    xtx_inv: np.ndarray

    def tstat(self) -> np.ndarray:
        return self.beta / np.where(self.se > 0, self.se, np.nan)

    def ci(self, alpha: float = 0.05):
        z = norm_ppf(1 - alpha / 2)
        return self.beta - z * self.se, self.beta + z * self.se

    def pvalues(self) -> np.ndarray:
        t = self.tstat()
        return np.array([math.erfc(abs(v) / math.sqrt(2.0)) for v in t])


def ols_cluster(y, X, cluster, names=None) -> OLS:
    """OLS with CR1 cluster-robust variance."""
    y = np.asarray(y, float)
    X = np.atleast_2d(np.asarray(X, float))
    if X.shape[0] != len(y):
        X = X.T
    n, k = X.shape
    names = list(names) if names else [f"x{j}" for j in range(k)]
    XtX = X.T @ X
    xtx_inv = np.linalg.pinv(XtX)
    beta = xtx_inv @ (X.T @ y)
    resid = y - X @ beta
    # iid variance for reference
    dof = max(1, n - k)
    s2 = float(resid @ resid) / dof
    se_iid = np.sqrt(np.clip(np.diag(xtx_inv) * s2, 0, np.inf))

    cl = np.asarray(cluster)
    groups = np.unique(cl)
    G = len(groups)
    meat = np.zeros((k, k))
    for g in groups:
        m = cl == g
        if not m.any():
            continue
        Xg = X[m]
        ug = resid[m]
        s = Xg.T @ ug
        meat += np.outer(s, s)
    if G > 1:
        meat *= G / (G - 1) * (n - 1) / max(1, n - k)
    V = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.clip(np.diag(V), 0, np.inf))
    return OLS(names, beta, se, se_iid, resid, n, k, G, xtx_inv)


def block_bootstrap(y, X, block, n_boot=1000, seed=20261111):
    """Resample whole blocks; returns (B, k) coefficient draws."""
    y = np.asarray(y, float)
    X = np.atleast_2d(np.asarray(X, float))
    if X.shape[0] != len(y):
        X = X.T
    block = np.asarray(block)
    blocks = np.unique(block)
    # row indices per block, stored contiguous for speed
    order = np.argsort(block, kind="stable")
    Xs, ys, bs = X[order], y[order], block[order]
    bounds = np.searchsorted(bs, blocks, side="left").tolist() + [len(bs)]
    rng = np.random.default_rng(seed)
    out = np.empty((n_boot, X.shape[1]))
    for b in range(n_boot):
        pick = rng.integers(0, len(blocks), size=len(blocks))
        idx = np.concatenate([np.arange(bounds[i], bounds[i + 1]) for i in pick])
        Xb, yb = Xs[idx], ys[idx]
        out[b] = np.linalg.pinv(Xb.T @ Xb) @ (Xb.T @ yb)
    return out


def romano_wolf(t_obs: Sequence[float], t_boot: np.ndarray, idx: Sequence[int]):
    """Step-down adjusted p-values (Romano-Wolf 2005).

    ``t_boot`` has shape (B, K) and holds bootstrap t-statistics centred on
    the observed estimates, i.e. (beta*_b - beta_hat)/se*_b. Only the
    hypotheses listed in ``idx`` enter the family.
    """
    idx = list(idx)
    t_obs = np.asarray(t_obs, float)[idx]
    tb = np.abs(np.asarray(t_boot, float)[:, idx])
    K = len(idx)
    order = np.argsort(-np.abs(t_obs))
    p_adj = np.zeros(K)
    running = 0.0
    for r, pos in enumerate(order):
        tail = order[r:]
        crit = abs(t_obs[pos])
        p = float(np.mean(np.max(tb[:, tail], axis=1) >= crit))
        running = max(running, p)
        p_adj[pos] = running
    return p_adj


def quad_fit(q, y):
    """Fit y = a + b q + c q^2; return vertex and curvature test inputs."""
    q = np.asarray(q, float)
    X = np.column_stack([np.ones_like(q), q, q ** 2])
    beta = np.linalg.pinv(X.T @ X) @ (X.T @ np.asarray(y, float))
    resid = y - X @ beta
    dof = max(1, len(y) - 3)
    s2 = float(resid @ resid) / dof
    V = np.linalg.pinv(X.T @ X) * s2
    se_c = math.sqrt(max(V[2, 2], 0))
    vertex = -beta[1] / (2 * beta[2]) if beta[2] != 0 else np.nan
    return beta, se_c, float(vertex)
