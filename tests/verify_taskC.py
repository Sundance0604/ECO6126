"""Independent verification of Task C results.

Run: python -B code/verify_taskC.py
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src import threshold as tl  # noqa: E402

DATA = os.path.join(ROOT, "data", "processed", "q_grid_run_level.csv")
TAB = os.path.join(ROOT, "outputs", "C", "tables")
FIG = os.path.join(ROOT, "outputs", "C", "figures")
QS = [1, 2, 3, 4, 5, 6, 8, 10]
RHOS = [0.05, 0.10, 0.20, 0.30, 0.40]

fails, checks = [], 0


def check(name, ok, detail=""):
    global checks
    checks += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        fails.append(name)


def main():
    df = pd.read_csv(DATA)
    df["duration"] = df.rmst_T.astype(float)
    df["event"] = df.collapse_event.astype(int)

    check("4,000 runs = 8 thresholds x 5 rho x 100 seeds",
          len(df) == 4000 and df.q.nunique() == 8 and df.rho.nunique() == 5
          and df.seed.nunique() == 100, f"{len(df)} rows")
    check("all cells share one institution (E=1, B=1)",
          df.E.nunique() == 1 and df.B.nunique() == 1
          and int(df.E.iloc[0]) == 1 and int(df.B.iloc[0]) == 1)
    check("no duplicate (q, rho, seed)",
          df.duplicated(["q", "rho", "seed"]).sum() == 0)
    check("every (q, rho) cell has exactly 100 runs",
          df.groupby(["q", "rho"]).size().nunique() == 1
          and df.groupby(["q", "rho"]).size().iloc[0] == 100)
    check("model version matches the A baseline",
          df.model_version.iloc[0] == "v1.5-A-raw-4d85097a0e80")

    # --- cell means
    cells = pd.read_csv(os.path.join(TAB, "tableC1_cell_means.csv"))
    worst = 0.0
    for _, row in cells.iterrows():
        d = df[(df.q == int(row.q)) & (np.isclose(df.rho, row.rho))]
        worst = max(worst, abs(d.duration.mean() - row.rmst_mean),
                    abs(d.event.mean() - row.collapse_rate))
    check("cell means reproduce from the raw runs", worst < 1e-9,
          f"max abs diff {worst:.2e}")

    # --- dummy coefficient = equal-weight mean of within-rho contrasts
    reg = pd.read_csv(os.path.join(TAB, "tableC2_threshold_dummies.csv"))
    reg = reg[reg.outcome == "rmst_T"].set_index("term")
    manual = {}
    for q in QS[1:]:
        per = []
        for r in RHOS:
            a = df[(df.q == q) & np.isclose(df.rho, r)].duration.mean()
            b = df[(df.q == 1) & np.isclose(df.rho, r)].duration.mean()
            per.append(a - b)
        manual[f"q={q}"] = float(np.mean(per))
    diff = max(abs(manual[t] - reg.loc[t, "estimate"]) for t in manual)
    check("threshold dummies equal the equal-weighted mean within-rho contrast",
          diff < 1e-8, f"max abs diff {diff:.2e}")

    # --- joint test
    meta = json.load(open(os.path.join(ROOT, "outputs", "C", "analysis_metadata.json"),
                          encoding="utf-8"))
    jt = meta["joint_test_vs_q1"]["rmst_T"]
    check("joint Wald test rejects equality of all thresholds",
          jt["wald"] > 100 and jt["p"] < 1e-6, f"chi2={jt['wald']:.1f}, df={jt['df']}")

    # --- quadratic vertex
    q = df.q.to_numpy(float)
    y = df.duration.to_numpy(float)
    X = np.column_stack([np.ones_like(q), q, q ** 2])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    vertex = -beta[1] / (2 * beta[2])
    quad = pd.read_csv(os.path.join(TAB, "tableC3_quadratic.csv")).set_index("outcome")
    check("quadratic curvature is positive (no interior maximum)",
          beta[2] > 0, f"b2={beta[2]:.3f}")
    check("quadratic vertex matches and lies outside the grid",
          abs(vertex - quad.loc["rmst_T", "vertex"]) < 1e-6
          and not (1 <= vertex <= 10), f"vertex={vertex:.2f}")

    # --- argmax: q = 1 best in every cell
    best = cells.loc[cells.groupby("q").rmst_mean.mean().idxmax()]
    check("q = 1 has the highest mean RMST of the eight thresholds",
          int(best.q) == 1, f"best q={int(best.q)}")
    arg = pd.read_csv(os.path.join(TAB, "tableC4_argmax_share.csv"))
    a1 = float(arg[(arg.outcome == "rmst_T") & (arg.threshold == "q=1")].share_best.iloc[0])
    check("q = 1 is the bootstrap argmax in essentially all draws", a1 > 0.99,
          f"share={a1:.3f}")

    # --- monotonicity
    means = cells.groupby("q").rmst_mean.mean().sort_index()
    mono = all(means.loc[QS[i]] >= means.loc[QS[i + 1]] - 1e-9 for i in range(len(QS) - 1))
    check("pooled RMST is non-increasing in q", mono,
          " -> ".join(f"{v:.1f}" for v in means.values))

    # --- figure and metadata
    fig = os.path.join(FIG, "Figure2.png")
    check("Figure 2 exists and is a real image",
          os.path.exists(fig) and os.path.getsize(fig) > 50_000,
          f"{os.path.getsize(fig)/1024:.0f} kB")
    h = hashlib.sha256(open(DATA, "rb").read()).hexdigest()
    check("metadata input hash matches the data on disk", meta["input_sha256"] == h)
    for name in ["tableC1_cell_means.csv", "tableC2_threshold_dummies.csv",
                 "tableC3_quadratic.csv", "tableC4_argmax_share.csv",
                 "tableC5_best_q_by_rho.csv", "tableC6_per_rho_effects.csv"]:
        check(f"table present: {name}", os.path.exists(os.path.join(TAB, name)))

    print()
    print(f"{checks - len(fails)}/{checks} checks passed")
    if fails:
        print("FAILED:", ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
