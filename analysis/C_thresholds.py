"""Task C — expulsion-threshold response surface.

Input : data/q_grid_run_level.csv
        4,000 runs = 8 thresholds q x 5 rho x 100 seeds, with E = 1 and B = 1,
        produced by the group's own scripts/run_extensions.py from
        configs/experiments/C_thresholds.json (4,000 simulated markets).
Output: outputs/C/tables/*.csv, outputs/C/figures/Figure2.png,
        outputs/C/analysis_metadata.json

Estimand
--------
The object of interest is the *shape* of the response of market outcomes to the
expulsion threshold q, not a single "optimal q". q enters only through the
number of public reports needed to expel a cheater, so a smaller q is a
stricter rule. Following the proposal, the primary specification is a set of
threshold dummies with q = 1 as the reference, estimated with rho fixed
effects and standard errors clustered on the random seed; a quadratic is
reported only as a summary and is interpreted only if the curvature is
estimated precisely and the implied vertex lies inside the grid.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src import threshold as tl  # noqa: E402

DATA = os.path.join(ROOT, "data", "processed", "q_grid_run_level.csv")
TAB = os.path.join(ROOT, "outputs", "C", "tables")
FIG = os.path.join(ROOT, "outputs", "C", "figures")
QGRID = [1, 2, 3, 4, 5, 6, 8, 10]
RHOS = [0.05, 0.10, 0.20, 0.30, 0.40]
N_BOOT = 2000
BOOT_SEED = 20261111


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load():
    df = pd.read_csv(DATA)
    df["duration"] = df["rmst_T"].astype(float)
    df["event"] = df["collapse_event"].astype(int)
    return df


def validate(df):
    c = {}
    c["n_rows"] = int(len(df))
    c["n_thresholds"] = int(df.q.nunique())
    c["grid"] = sorted(int(v) for v in df.q.unique())
    c["n_rho"] = int(df.rho.nunique())
    c["n_seeds"] = int(df.seed.nunique())
    c["balanced"] = bool(df.groupby(["q", "rho"]).size().nunique() == 1
                         and len(df) == 8 * 5 * 100)
    c["single_institution"] = bool(df.E.nunique() == 1 and df.B.nunique() == 1
                                   and int(df.E.iloc[0]) == 1 and int(df.B.iloc[0]) == 1)
    c["duplicate_keys"] = int(df.duplicated(["q", "rho", "seed"]).sum())
    c["event_rate"] = float(df.event.mean())
    c["n_events"] = int(df.event.sum())
    c["n_censored"] = int((1 - df.event).sum())
    return c


def design(df, ref=1):
    """Intercept, threshold dummies (ref omitted), rho dummies."""
    qs = QGRID
    cols = [np.ones(len(df))]
    names = ["intercept"]
    for q in qs:
        if q == ref:
            continue
        cols.append((df.q == q).astype(float).to_numpy())
        names.append(f"q={q}")
    for r in RHOS[1:]:
        cols.append(np.isclose(df.rho.to_numpy(float), r).astype(float))
        names.append(f"rho={r:.2f}")
    return np.column_stack(cols), names


def cell_table(df):
    rows = []
    for q in QGRID:
        for r in RHOS:
            d = df[(df.q == q) & np.isclose(df.rho, r)]
            rows.append({"q": q, "rho": r, "n": len(d),
                         "rmst_mean": d.duration.mean(), "rmst_sd": d.duration.std(ddof=1),
                         "collapse_rate": d.event.mean(),
                         "welfare_mean": d.welfare_T.mean(),
                         "welfare_sd": d.welfare_T.std(ddof=1)})
    return pd.DataFrame(rows)


def threshold_regression(df, outcome, boot_draws=None):
    X, names = design(df)
    y = df[outcome].to_numpy(float)
    fit = tl.ols_cluster(y, X, df.seed.to_numpy(), names=names)
    lo, hi = fit.ci()
    rows = []
    for i, nm in enumerate(names):
        rows.append({"outcome": outcome, "term": nm, "estimate": fit.beta[i],
                     "cluster_se": fit.se[i], "ci_low": lo[i], "ci_high": hi[i],
                     "p": fit.pvalues()[i], "n": fit.n, "clusters": fit.clusters})
    out = pd.DataFrame(rows)

    # joint test that all thresholds equal q = 1 (cluster Wald)
    idx = [i for i, nm in enumerate(names) if nm.startswith("q=")]
    Xa = X[:, idx]
    resid = fit.resid
    seeds = df.seed.to_numpy()
    groups = np.unique(seeds)
    G, n, k = len(groups), *X.shape
    meat = np.zeros((len(idx), len(idx)))
    for g in groups:
        m = seeds == g
        u = Xa[m].T @ resid[m]
        meat += np.outer(u, u)
    meat *= G / (G - 1) * (n - 1) / max(1, n - k)
    XtX_full = np.linalg.pinv(X.T @ X)
    V_full = XtX_full @ np.zeros((k, k))
    # full sandwich restricted to the threshold block
    meat_full = np.zeros((k, k))
    for g in groups:
        m = seeds == g
        u = X[m].T @ resid[m]
        meat_full += np.outer(u, u)
    meat_full *= G / (G - 1) * (n - 1) / max(1, n - k)
    V_full = XtX_full @ meat_full @ XtX_full
    Vs = V_full[np.ix_(idx, idx)]
    b = fit.beta[idx]
    wald = float(b @ np.linalg.pinv(Vs) @ b)
    p_joint = float(chi2_sf(wald, len(idx)))
    return out, dict(wald=wald, df=len(idx), p=p_joint)


def chi2_sf(x, df):
    import math
    if df == 1:
        return math.erfc(math.sqrt(max(x, 0) / 2))
    a, z = df / 2.0, max(x, 0) / 2.0
    # regularised upper incomplete gamma via series/continued fraction
    if z < a + 1:
        ap, s, delta = a, 1.0 / a, 1.0 / a
        for _ in range(10000):
            ap += 1
            delta *= z / ap
            s += delta
            if abs(delta) < abs(s) * 1e-15:
                break
        p = s * math.exp(-z + a * math.log(z) - math.lgamma(a))
        return max(0.0, min(1.0, 1.0 - p))
    b = z + 1 - a
    c, d, h = 1e300, 1.0 / b, 1.0 / b
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return max(0.0, min(1.0, math.exp(-z + a * math.log(z) - math.lgamma(a)) * h))


def bootstrap_coefficients(df, outcome, n_boot=N_BOOT, seed=BOOT_SEED):
    """Seed-block bootstrap of the threshold-dummy coefficients."""
    X, names = design(df)
    keep = [i for i, nm in enumerate(names) if nm.startswith("q=") or nm == "intercept"]
    y = df[outcome].to_numpy(float)
    seeds = np.unique(df.seed.to_numpy())
    idx_by_seed = {s: np.where(df.seed.to_numpy() == s)[0] for s in seeds}
    rng = np.random.default_rng(seed)
    draws = np.empty((n_boot, len(keep)))
    for b in range(n_boot):
        pick = rng.choice(seeds, size=len(seeds), replace=True)
        rows = np.concatenate([idx_by_seed[s] for s in pick])
        Xb, yb = X[rows], y[rows]
        draws[b] = (np.linalg.pinv(Xb.T @ Xb) @ (Xb.T @ yb))[keep]
    return draws, [names[i] for i in keep]


def romano_wolf(df, outcome, draws, names_keep):
    X, names = design(df)
    y = df[outcome].to_numpy(float)
    fit = tl.ols_cluster(y, X, df.seed.to_numpy(), names=names)
    idx = [i for i, nm in enumerate(names) if nm.startswith("q=")]
    pos = [names_keep.index(nm) for nm in names if nm.startswith("q=")]
    t_obs = fit.beta[idx] / fit.se[idx]
    # centre the bootstrap draws and studentise with the cluster SE
    t_boot = (draws[:, pos] - fit.beta[idx]) / fit.se[idx]
    # step-down over the seven thresholds
    K = len(idx)
    order = np.argsort(-np.abs(t_obs))
    p_adj = np.zeros(K)
    running = 0.0
    for r, posi in enumerate(order):
        tail = order[r:]
        crit = abs(t_obs[posi])
        p = float(np.mean(np.max(np.abs(t_boot[:, tail]), axis=1) >= crit))
        running = max(running, p)
        p_adj[posi] = running
    return p_adj


def quadratic(df, outcome):
    q = df.q.to_numpy(float)
    y = df[outcome].to_numpy(float)
    X = np.column_stack([np.ones_like(q), q, q ** 2])
    fit = tl.ols_cluster(y, X, df.seed.to_numpy(), names=["a", "b1", "b2"])
    b1, b2 = fit.beta[1], fit.beta[2]
    vertex = -b1 / (2 * b2) if b2 != 0 else np.nan
    return {"outcome": outcome, "b1": b1, "b2": b2, "se_b2": fit.se[2],
            "p_b2": fit.pvalues()[2], "vertex": vertex,
            "vertex_in_grid": bool(1 <= vertex <= 10) if np.isfinite(vertex) else False}


def argmax_distribution(df, outcome, draws, names_keep):
    """Share of bootstrap draws in which each threshold is the best one."""
    pos = [names_keep.index(nm) for nm in names_keep if nm.startswith("q=")]
    qs = [nm for nm in names_keep if nm.startswith("q=")]
    # coefficients are relative to q = 1, whose value is the intercept
    inter = names_keep.index("intercept")
    coefs = np.column_stack([draws[:, inter][:, None], draws[:, inter][:, None] + draws[:, pos]])
    best = np.argmax(coefs, axis=1)
    labels = ["q=1"] + [nm.replace("q=", "q=") for nm in qs]
    share = {lab: float(np.mean(best == i)) for i, lab in enumerate(labels)}
    return share



def per_rho_regression(df, outcome):
    """Threshold dummies estimated inside each market type (ref q = 1)."""
    rows = []
    for r in RHOS:
        d = df[np.isclose(df.rho, r)]
        cols = [np.ones(len(d))]
        names = ["intercept"]
        for q in QGRID:
            if q == 1:
                continue
            cols.append((d.q == q).astype(float).to_numpy())
            names.append(f"q={q}")
        X = np.column_stack(cols)
        fit = tl.ols_cluster(d[outcome].to_numpy(float), X, d.seed.to_numpy(), names=names)
        lo, hi = fit.ci()
        for i, nm in enumerate(names):
            if nm == "intercept":
                continue
            rows.append({"outcome": outcome, "rho": r, "term": nm,
                         "estimate": fit.beta[i], "cluster_se": fit.se[i],
                         "ci_low": lo[i], "ci_high": hi[i], "p": fit.pvalues()[i],
                         "n": fit.n, "clusters": fit.clusters})
    return pd.DataFrame(rows)


def make_figure(df, cells, coefs_rmst, coefs_w, argmax_share):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.6,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.linewidth": 0.7, "figure.dpi": 220})

    fig = plt.figure(figsize=(9.6, 5.6))
    gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.28)

    ax = fig.add_subplot(gs[0, 0])
    cmap = plt.get_cmap("viridis")
    for k, r in enumerate(RHOS):
        d = cells[cells.rho == r].sort_values("q")
        ax.plot(d.q, d.rmst_mean, marker="o", ms=3, lw=1.1,
                color=cmap(k / (len(RHOS) - 1)), label=f"$\\rho$={r:.2f}")
    ax.set_xscale("log")
    ax.set_xticks(QGRID)
    ax.set_xticklabels([str(q) for q in QGRID], fontsize=6)
    ax.set_xlabel("Expulsion threshold $q$ (smaller = stricter)")
    ax.set_ylabel("RMST(200), periods")
    ax.set_title("(a) Survival response to the threshold", fontsize=8)
    ax.legend(frameon=False, fontsize=5.8, ncol=2)

    ax = fig.add_subplot(gs[0, 1])
    for k, r in enumerate(RHOS):
        d = cells[cells.rho == r].sort_values("q")
        ax.plot(d.q, d.welfare_mean, marker="o", ms=3, lw=1.1,
                color=cmap(k / (len(RHOS) - 1)))
    ax.axhline(0, color="#888888", lw=0.7, ls=":")
    ax.set_xscale("log")
    ax.set_xticks(QGRID)
    ax.set_xticklabels([str(q) for q in QGRID], fontsize=6)
    ax.set_xlabel("Expulsion threshold $q$")
    ax.set_ylabel("Cumulative net surplus")
    ax.set_title("(b) Welfare response to the threshold", fontsize=8)

    ax = fig.add_subplot(gs[1, 0])
    sub = coefs_rmst[coefs_rmst.term.str.startswith("q=")]
    y = np.arange(len(sub))
    ax.errorbar(sub.estimate, y,
                xerr=[sub.estimate - sub.ci_low, sub.ci_high - sub.estimate],
                fmt="o", ms=3.2, lw=1.0, capsize=2.0, color="#1F5C99")
    ax.axvline(0, color="#888888", lw=0.7, ls=":")
    ax.set_yticks(y)
    ax.set_yticklabels([t.replace("q=", "$q$=") for t in sub.term], fontsize=6.4)
    ax.set_xlabel("Difference in RMST(200) vs $q=1$, periods")
    ax.set_title("(c) Threshold dummies, 95% cluster intervals", fontsize=8)
    ax.invert_yaxis()

    ax = fig.add_subplot(gs[1, 1])
    labels = list(argmax_share.keys())
    vals = [argmax_share[k] for k in labels]
    ax.bar(range(len(labels)), vals, color="#1F5C99", alpha=0.85, lw=0)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([l.replace("q=", "") for l in labels])
    ax.set_xlabel("Threshold $q$")
    ax.set_ylabel("Share of bootstrap draws")
    ax.set_title("(d) Which $q$ is best on RMST, 2,000 draws", fontsize=8)
    ax.set_ylim(0, 1.12)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.03, f"{v:.2f}", ha="center", fontsize=5.8)

    fig.text(0.5, -0.01,
             "All panels: E = B = 1, N = 100, a = p = 3, T = 200, 100 seeds per cell; "
             "4,000 simulated markets in total (8 thresholds x 5 rho x 100 seeds).",
             ha="center", fontsize=5.8, color="#555555")
    fig.savefig(os.path.join(FIG, "Figure2.png"), bbox_inches="tight")
    plt.close(fig)


def main():
    t0 = time.time()
    os.makedirs(TAB, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    df = load()
    checks = validate(df)
    if not checks["balanced"] or checks["duplicate_keys"]:
        raise SystemExit(f"design check failed: {checks}")

    print(f"[1/5] {checks['n_rows']} runs, q grid {checks['grid']}, "
          f"events {checks['n_events']}, censored {checks['n_censored']}")

    cells = cell_table(df)
    cells.to_csv(os.path.join(TAB, "tableC1_cell_means.csv"), index=False)

    print("[2/5] threshold regressions ...")
    reg_rows, joint = [], {}
    for outcome in ("rmst_T", "welfare_T"):
        out, jt = threshold_regression(df, outcome)
        reg_rows.append(out)
        joint[outcome] = jt
    reg = pd.concat(reg_rows, ignore_index=True)

    print("[3/5] bootstrap and Romano-Wolf ...")
    draws_r, names_r = bootstrap_coefficients(df, "rmst_T")
    draws_w, names_w = bootstrap_coefficients(df, "welfare_T")
    rw_r = romano_wolf(df, "rmst_T", draws_r, names_r)
    rw_w = romano_wolf(df, "welfare_T", draws_w, names_w)
    for outcome, rw in (("rmst_T", rw_r), ("welfare_T", rw_w)):
        m = (reg.outcome == outcome) & (reg.term.str.startswith("q="))
        reg.loc[m, "rw_p"] = rw
    reg.to_csv(os.path.join(TAB, "tableC2_threshold_dummies.csv"), index=False)

    print("[4/5] quadratic summaries and grid argmax ...")
    quad = [quadratic(df, o) for o in ("rmst_T", "welfare_T")]
    pd.DataFrame(quad).to_csv(os.path.join(TAB, "tableC3_quadratic.csv"), index=False)

    share_r = argmax_distribution(df, "rmst_T", draws_r, names_r)
    share_w = argmax_distribution(df, "welfare_T", draws_w, names_w)
    arg = pd.DataFrame({"outcome": ["rmst_T"] * len(share_r) + ["welfare_T"] * len(share_w),
                        "threshold": list(share_r) + list(share_w),
                        "share_best": list(share_r.values()) + list(share_w.values())})
    arg.to_csv(os.path.join(TAB, "tableC4_argmax_share.csv"), index=False)

    per_rho = pd.concat([per_rho_regression(df, o) for o in ("rmst_T", "welfare_T")],
                        ignore_index=True)
    per_rho.to_csv(os.path.join(TAB, "tableC6_per_rho_effects.csv"), index=False)

    best = cells.loc[cells.groupby("rho").rmst_mean.idxmax()]
    best.to_csv(os.path.join(TAB, "tableC5_best_q_by_rho.csv"), index=False)

    print("[5/5] figure ...")
    make_figure(df, cells, reg[reg.outcome == "rmst_T"], reg[reg.outcome == "welfare_T"], share_r)

    meta = {
        "task": "C — expulsion threshold response",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "model_version": str(df.model_version.iloc[0]),
        "input_file": "data/processed/q_grid_run_level.csv",
        "input_sha256": sha256(DATA),
        "source": "scripts/run_extensions.py --plan configs/experiments/C_thresholds.json",
        "design": {"q": QGRID, "rho": RHOS, "seeds": "0-99", "E": 1, "B": 1,
                   "N": int(df.N.iloc[0]), "a": int(df.a.iloc[0]),
                   "p": int(df.p.iloc[0]), "T": int(df["T"].iloc[0]),
                   "w_init": float(df.w_init.iloc[0])},
        "n_runs": int(len(df)),
        "checks": checks,
        "joint_test_vs_q1": joint,
        "inference": {"bootstrap": "seed-block, 2,000 draws", "boot_seed": BOOT_SEED,
                      "cluster": "random seed", "multiple_testing": "Romano-Wolf step-down"},
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "pandas": pd.__version__, "platform": platform.platform()},
        "runtime_seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(ROOT, "outputs", "C", "analysis_metadata.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"done in {meta['runtime_seconds']}s")


if __name__ == "__main__":
    main()
