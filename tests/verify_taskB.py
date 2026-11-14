"""Independent verification of Task B results.

Every check recomputes a published number from ``data/run_level.csv`` using a
different code path from ``B_survival.py`` (brute-force loops instead of the
vectorised helpers, grid search instead of Newton-Raphson), then compares it
with the value stored in ``outputs/tables``.

Run:  python -B code/verify_taskB.py
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, "data", "processed", "run_level.csv")
TAB = os.path.join(ROOT, "outputs", "B", "tables")
FIG = os.path.join(ROOT, "outputs", "B", "figures")

fails: list[str] = []
checks = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        fails.append(name)


def close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def brute_km(dur, ev, tmax):
    """Deliberately naive product-limit estimator."""
    surv = {0: 1.0}
    s = 1.0
    for t in range(1, tmax + 1):
        n = sum(1 for d in dur if d >= t)
        d = sum(1 for dd, ee in zip(dur, ev) if dd == t and ee == 1)
        if n > 0 and d > 0:
            s *= 1.0 - d / n
        surv[t] = s
    return surv


def brute_logrank(t1, e1, t0, e0):
    """Two-group log-rank by explicit 2x2 tables at each event time."""
    times = sorted({t for t, e in zip(list(t1) + list(t0), list(e1) + list(e0)) if e == 1})
    O = E = V = 0.0
    for u in times:
        n1 = sum(1 for t in t1 if t >= u)
        n0 = sum(1 for t in t0 if t >= u)
        d1 = sum(1 for t, e in zip(t1, e1) if t == u and e == 1)
        d0 = sum(1 for t, e in zip(t0, e0) if t == u and e == 1)
        n, d = n1 + n0, d1 + d0
        if n < 2 or d == 0:
            continue
        O += d1
        E += d * n1 / n
        V += d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
    chi2 = (O - E) ** 2 / V if V > 0 else 0.0
    return chi2, O, E


def cox_grid(dur, ev, x, lo=-6.0, hi=0.5, n=2601):
    """Maximise the Efron partial likelihood by grid search (single covariate)."""
    ts = np.asarray(dur, float)
    es = np.asarray(ev, int)
    xs = np.asarray(x, float)
    times = np.unique(ts[es == 1])

    def loglik(b):
        ll = 0.0
        w = np.exp(np.clip(b * xs, -50, 50))
        for u in times:
            R = ts >= u
            D = (ts == u) & (es == 1)
            d = int(D.sum())
            s0 = w[R].sum()
            d0 = w[D].sum()
            ll += float((b * xs[D]).sum())
            for r in range(d):
                c = r / d
                ll -= math.log(s0 - c * d0)
        return ll

    grid = np.linspace(lo, hi, n)
    vals = np.array([loglik(b) for b in grid])
    i = int(np.argmax(vals))
    # golden-section refinement around the grid maximum
    a, b = grid[max(0, i - 2)], grid[min(n - 1, i + 2)]
    for _ in range(80):
        m1 = a + 0.382 * (b - a)
        m2 = a + 0.618 * (b - a)
        if loglik(m1) < loglik(m2):
            a = m1
        else:
            b = m2
    return 0.5 * (a + b)


def main() -> int:
    df = pd.read_csv(DATA)
    df["duration"] = df.rmst_T.astype(float)
    df["event"] = df.collapse_event.astype(int)

    # ---------------- 1. design integrity
    cell = df.groupby(["rho", "E", "B"]).size()
    check("grid is complete and balanced (5 rho x 2 E x 2 B x 100 seeds)",
          len(cell) == 20 and cell.nunique() == 1 and cell.iloc[0] == 100,
          f"{len(cell)} cells, {cell.iloc[0]} runs each")
    check("no duplicate (rho, seed, E, B) keys",
          df.duplicated(["rho", "seed", "E", "B"]).sum() == 0)
    piv = df.pivot_table(index=["rho", "seed", "E"], columns="B",
                         values="duration", aggfunc="first")
    check("bankruptcy switch does not change survival (B is inert)",
          bool((piv[0] == piv[1]).all()))
    check("censored runs are recorded at the horizon",
          bool((df.loc[df.event == 0, "duration"] == 200).all()),
          f"{(df.event == 0).sum()} censored runs")
    check("observed events occur strictly before the horizon",
          bool((df.loc[df.event == 1, "duration"] < 200).all()))

    # ---------------- 2. Kaplan-Meier and RMST reproduce the raw means
    km_tab = pd.read_csv(os.path.join(TAB, "tableB1_km_summary.csv"))
    worst_km = 0.0
    for _, row in km_tab.iterrows():
        d = df[(df.rho == row.rho) & (df.E == row.E) & (df.B == row.B)]
        surv = brute_km(list(d.duration), list(d.event), 200)
        worst_km = max(worst_km, abs(surv[200] - row.S200), abs(surv[10] - row.S10))
        rmst = sum(surv[t] for t in range(0, 200))
        worst_km = max(worst_km, abs(rmst - row.RMST200))
    check("KM survival and RMST match a brute-force product-limit estimator",
          worst_km < 1e-9, f"max abs diff {worst_km:.2e}")

    rmst_tab = pd.read_csv(os.path.join(TAB, "tableB2_rmst_levels.csv"))
    d0 = df[df.B == 0]
    worst_mean = 0.0
    for _, row in rmst_tab[rmst_tab.rho != "pooled"].iterrows():
        d = d0[(d0.rho == float(row.rho)) & (d0.E == row.E)]
        worst_mean = max(worst_mean, abs(d.rmst_T.mean() - row.RMST200))
    check("RMST(200) equals the cell mean of rmst_T",
          worst_mean < 1e-9, f"max abs diff {worst_mean:.2e}")

    # ---------------- 3. paired difference equal to A's OLS coefficient
    diff_tab = pd.read_csv(os.path.join(TAB, "tableB3_rmst_differences.csv"))
    pooled = float(diff_tab.loc[diff_tab.rho == "pooled", "estimate"].iloc[0])
    direct = (d0.groupby(["rho", "E"]).rmst_T.mean().unstack()[1]
              - d0.groupby(["rho", "E"]).rmst_T.mean().unstack()[0]).mean()
    check("pooled RMST difference equals the equal-weight mean of rho contrasts",
          close(pooled, direct, 1e-9), f"{pooled:.4f} vs {direct:.4f}")
    check("pooled difference matches A-baseline OLS E coefficient (104.752)",
          close(pooled, 104.752, 5e-3), f"{pooled:.3f}")

    # per-rho contrast should equal the mean difference within rho
    worst_d = 0.0
    for rho in sorted(d0.rho.unique()):
        est = float(diff_tab.loc[diff_tab.rho.astype(str) == str(rho), "estimate"].iloc[0])
        d = d0[d0.rho == rho]
        truth = d[d.E == 1].rmst_T.mean() - d[d.E == 0].rmst_T.mean()
        worst_d = max(worst_d, abs(est - truth))
    check("per-rho contrasts equal the raw mean differences", worst_d < 1e-9,
          f"max abs diff {worst_d:.2e}")

    # ---------------- 4. log-rank
    lr_tab = pd.read_csv(os.path.join(TAB, "tableB4_logrank.csv"))
    for rho in sorted(d0.rho.unique()):
        d = d0[d0.rho == rho]
        chi2, O, E = brute_logrank(d[d.E == 1].duration, d[d.E == 1].event,
                                   d[d.E == 0].duration, d[d.E == 0].event)
        rep = float(lr_tab.loc[lr_tab.comparison == f"rho={rho}", "chi2"].iloc[0])
        check(f"log-rank chi-square reproduces by hand (rho={rho})",
              abs(chi2 - rep) < 1e-6, f"{chi2:.4f} vs {rep:.4f}")

    # ---------------- 5. Cox at the identified stratum
    cox_tab = pd.read_csv(os.path.join(TAB, "tableB5_cox.csv"))
    d = d0[d0.rho == 0.40]
    beta_grid = cox_grid(d.duration, d.event, d.E)
    rep = cox_tab[(cox_tab.model == "rho=0.4") & (cox_tab.estimator == "Cox (unpenalised)")]
    beta_rep = float(rep.beta.iloc[0])
    check("Cox coefficient at rho=0.40 matches a grid-search MLE",
          abs(beta_grid - beta_rep) < 2e-3, f"{beta_grid:.4f} vs {beta_rep:.4f}")

    # separation claim: at every event time at which both groups are still at
    # risk, the deaths come from a single group, so the partial likelihood is
    # monotone in beta.
    separated = []
    for rho in sorted(d0.rho.unique()):
        dd = d0[d0.rho == rho]
        flag, mixed_time = True, False
        for u in np.unique(dd[dd.event == 1].duration):
            risk = dd[dd.duration >= u]
            if risk.E.nunique() < 2:
                continue
            mixed_time = True
            dead = dd[(dd.duration == u) & (dd.event == 1)]
            if dead.E.nunique() > 1:
                flag = False
                break
        separated.append((rho, flag and mixed_time))
    check("rho <= 0.30 strata are separated; rho = 0.40 is not",
          all(flag for r, flag in separated if r < 0.40) and not dict(separated)[0.40],
          str(dict(separated)))

    # ---------------- 6. B carries no information
    row_b = cox_tab[(cox_tab.model == "pooled + B") & (cox_tab.term == "B")]
    check("Cox coefficient on B is exactly zero with zero standard error",
          close(row_b.beta.iloc[0], 0.0, 1e-12) and close(row_b.se.iloc[0], 0.0, 1e-12),
          f"beta={row_b.beta.iloc[0]:.3e}, se={row_b.se.iloc[0]:.3e}")

    # interaction of the two switches: no information either
    from src import survival as slv
    X1 = d0[["E"]].values
    X3 = np.column_stack([d0.E.values, d0.B.values, d0.E.values * d0.B.values])
    r1 = slv.cox_fit(d0.duration, d0.event, X1, names=["E"],
                     strata=d0.rho.values, cluster=d0.seed.values)
    r3 = slv.cox_fit(d0.duration, d0.event, X3, names=["E", "B", "ExB"],
                     strata=d0.rho.values, cluster=d0.seed.values)
    check("adding B and the E x B interaction leaves the log-likelihood unchanged",
          abs(r3.loglik - r1.loglik) < 1e-6,
          f"loglik {r1.loglik:.6f} vs {r3.loglik:.6f}, E x B coef {r3.beta[2]:.2e}")

    # ---------------- 7. proportional hazards evidence
    ph = pd.read_csv(os.path.join(TAB, "tableB7_ph_diagnostics.csv"))
    h3 = ph[(ph.statistic == "period hazard, rho=0.40") & (ph.window == "t=3")].note.iloc[0]
    h4 = ph[(ph.statistic == "period hazard, rho=0.40") & (ph.window == "t=4")].note.iloc[0]
    check("period-3 hazard differs and period-4 hazard coincides (rho=0.40)",
          "h(E=0)=0.93" in h3 and "h(E=1)=0.15" in h3 and "ratio=1.00" in h4,
          f"{h3}; {h4}")

    # ---------------- 8. outputs exist
    fig = os.path.join(FIG, "Figure1.png")
    check("Figure 1 exists and is a real image",
          os.path.exists(fig) and os.path.getsize(fig) > 60_000,
          f"{os.path.getsize(fig)/1024:.0f} kB" if os.path.exists(fig) else "missing")
    for name in ["tableB1_km_summary.csv", "tableB2_rmst_levels.csv",
                 "tableB3_rmst_differences.csv", "tableB4_logrank.csv",
                 "tableB5_cox.csv", "tableB6_hazard_profile.csv",
                 "tableB7_ph_diagnostics.csv"]:
        check(f"table present: {name}", os.path.exists(os.path.join(TAB, name)))

    # ---------------- 9. reproducibility metadata
    meta_path = os.path.join(ROOT, "outputs", "B", "analysis_metadata.json")
    if os.path.exists(meta_path):
        import hashlib
        import json
        meta = json.load(open(meta_path, encoding="utf-8"))
        h = hashlib.sha256(open(DATA, "rb").read()).hexdigest()
        check("metadata input hash matches the data on disk",
              meta["input_sha256"] == h)
        check("metadata records the model version",
              meta["model_version"].startswith("v1.5-A-raw"))
    else:
        check("analysis_metadata.json present", False)

    print()
    print(f"{checks - len(fails)}/{checks} checks passed")
    if fails:
        print("FAILED:", ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
