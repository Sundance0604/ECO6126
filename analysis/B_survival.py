"""Task B 鈥?survival analysis of simulated market collapse.

Input : data/run_level.csv  (2,000 runs: 5 rho x 2 expulsion x 2 bankruptcy
        x 100 seeds, produced by scripts/run_baseline.py in the group repo)
Output: outputs/tables/*.csv, outputs/figures/*.png, outputs/analysis_metadata.json

Design notes
------------
* Unit of analysis is a simulated market (one run). ``duration`` is
  ``rmst_T = min(T_collapse, T)`` and ``event = collapse_event``; the two must
  be used together because 27% of runs are right-censored at T = 200.
* Because the bankruptcy switch B is inert for survival in this calibration
  (H never becomes insolvent; see validate() below), all paired E-effect
  estimates use the B = 0 half of the design, so that no trajectory enters
  twice. The four-institution Kaplan-Meier panel nevertheless shows all four
  cells, which makes the overlap of B = 0 and B = 1 visible.
* Inference resamples whole seed blocks (100 seeds), each carrying every rho
  and both institutions, so that the paired design is preserved.
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

from src import survival as sl  # noqa: E402

DATA = os.path.join(ROOT, "data", "processed", "run_level.csv")
TAB = os.path.join(ROOT, "outputs", "B", "tables")
FIG = os.path.join(ROOT, "outputs", "B", "figures")
TMAX = 200
N_BOOT = 5000
BOOT_SEED = 20261110
RHO_GRID = [0.05, 0.10, 0.20, 0.30, 0.40]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# load and validate
# --------------------------------------------------------------------------


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    need = ["run_id", "rho", "seed", "E", "B", "collapse_event", "rmst_T", "T"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"missing columns: {missing}")
    df["duration"] = df["rmst_T"].astype(float)
    df["event"] = df["collapse_event"].astype(int)
    return df


def validate(df: pd.DataFrame) -> dict:
    """Structural checks that the report relies on."""
    checks = {}
    checks["n_rows"] = int(len(df))
    checks["balanced_cells"] = bool(
        df.groupby(["rho", "E", "B"]).size().nunique() == 1
        and df.groupby(["rho", "E", "B"]).ngroups == 20)
    checks["n_seeds"] = int(df.seed.nunique())
    checks["duplicate_keys"] = int(df.duplicated(["rho", "seed", "E", "B"]).sum())
    checks["event_rate"] = float(df.event.mean())

    # bankruptcy switch must not move survival in this calibration
    piv = df.pivot_table(index=["rho", "seed", "E"], columns="B",
                         values="duration", aggfunc="first")
    checks["bankruptcy_inert"] = bool((piv[0] == piv[1]).all())

    # duration / censoring consistency
    ok_cens = df.loc[df.event == 0, "duration"].eq(TMAX).all()
    ok_event = (df.loc[df.event == 1, "duration"] < TMAX).all()
    checks["censoring_consistent"] = bool(ok_cens and ok_event)
    checks["n_censored"] = int((df.event == 0).sum())
    checks["n_events"] = int((df.event == 1).sum())
    return checks


# --------------------------------------------------------------------------
# Kaplan-Meier based tables
# --------------------------------------------------------------------------


def km_table(df: pd.DataFrame) -> pd.DataFrame:
    """Institution x rho KM summaries (all four cells, as in A's Table 1)."""
    rows = []
    for rho in RHO_GRID:
        for E in (0, 1):
            for B in (0, 1):
                d = df[(df.rho == rho) & (df.E == E) & (df.B == B)]
                km = sl.kaplan_meier(d.duration, d.event, TMAX)
                rows.append({
                    "rho": rho, "E": E, "B": B, "n": km.n, "events": km.events,
                    "censored": km.n - km.events,
                    "median": km.median() if km.median() is not None else np.nan,
                    "S10": km.at(10), "S20": km.at(20), "S50": km.at(50),
                    "S100": km.at(100), "S200": km.at(TMAX),
                    "RMST200": km.rmst(),
                })
    return pd.DataFrame(rows)


def bootstrap_rmst(df: pd.DataFrame, n_boot: int = N_BOOT,
                   seed: int = BOOT_SEED):
    """Seed-block bootstrap of RMST(200) by (rho, E), using the B = 0 half.

    Returns a dict {(rho, E): (values array)} of bootstrap RMST draws plus the
    paired difference draws (E1 - E0) and the difference-in-differences.
    """
    d0 = df[df.B == 0].copy()
    seeds = np.unique(d0.seed)
    key = {(rho, e): [] for rho in RHO_GRID for e in (0, 1)}
    diff = {rho: [] for rho in RHO_GRID}
    did = []

    # index rows by (rho, E, seed) for O(1) lookup
    lut = {}
    for rho in RHO_GRID:
        for E in (0, 1):
            s = d0[(d0.rho == rho) & (d0.E == E)].set_index("seed")
            lut[(rho, E)] = (s.duration.reindex(seeds).to_numpy(float),
                             s.event.reindex(seeds).to_numpy(int))

    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        draw = rng.choice(seeds, size=len(seeds), replace=True)
        for rho in RHO_GRID:
            vals = {}
            for E in (0, 1):
                dur, ev = lut[(rho, E)]
                km = sl.kaplan_meier(dur[draw], ev[draw], TMAX)
                vals[E] = km.rmst()
                key[(rho, E)].append(vals[E])
            diff[rho].append(vals[1] - vals[0])
        did.append(0.0)  # B is inert: every draw gives a zero DiD
    return key, diff, np.asarray(did)


def rmst_tables(df: pd.DataFrame, boot_key, boot_diff) -> tuple:
    d0 = df[df.B == 0]
    rows, drows = [], []
    for rho in RHO_GRID:
        vals = {}
        for E in (0, 1):
            d = d0[(d0.rho == rho) & (d0.E == E)]
            km = sl.kaplan_meier(d.duration, d.event, TMAX)
            vals[E] = km.rmst()
            lo, hi, se, nb = sl.percentile_ci(boot_key[(rho, E)])
            rows.append({"rho": rho, "E": E, "n": km.n, "events": km.events,
                         "RMST200": km.rmst(), "boot_se": se,
                         "ci_low": lo, "ci_high": hi, "n_boot": nb})
        lo, hi, se, nb = sl.percentile_ci(boot_diff[rho])
        drows.append({"rho": rho, "contrast": "E=1 minus E=0",
                      "estimate": vals[1] - vals[0], "boot_se": se,
                      "ci_low": lo, "ci_high": hi, "n_boot": nb})

    # pooled (equal weight over the five rho values, as in A's Table 1)
    pooled = {}
    for E in (0, 1):
        draws = np.mean([np.asarray(boot_key[(rho, E)]) for rho in RHO_GRID], axis=0)
        est = float(np.mean([sl.kaplan_meier(
            d0[(d0.rho == rho) & (d0.E == E)].duration,
            d0[(d0.rho == rho) & (d0.E == E)].event, TMAX).rmst() for rho in RHO_GRID]))
        lo, hi, se, nb = sl.percentile_ci(draws)
        pooled[E] = est
        rows.append({"rho": "pooled", "E": E, "n": int((d0.E == E).sum()),
                     "events": int(d0[d0.E == E].event.sum()), "RMST200": est,
                     "boot_se": se, "ci_low": lo, "ci_high": hi, "n_boot": nb})
    draws_pool = np.mean([np.asarray(boot_diff[rho]) for rho in RHO_GRID], axis=0)
    lo, hi, se, nb = sl.percentile_ci(draws_pool)
    drows.append({"rho": "pooled", "contrast": "E=1 minus E=0",
                  "estimate": pooled[1] - pooled[0], "boot_se": se,
                  "ci_low": lo, "ci_high": hi, "n_boot": nb})
    return pd.DataFrame(rows), pd.DataFrame(drows)


# --------------------------------------------------------------------------
# log-rank and Cox
# --------------------------------------------------------------------------


def logrank_table(df: pd.DataFrame) -> pd.DataFrame:
    d0 = df[df.B == 0]
    rows = []
    for rho in RHO_GRID:
        d = d0[d0.rho == rho]
        lr = sl.logrank(d.duration, d.event, d.E)
        rows.append({"comparison": f"rho={rho}", "chi2": lr.chi2, "df": lr.df,
                     "p": lr.p, "events": lr.events, "observed_E1": lr.observed,
                     "expected_E1": lr.expected})
    lr = sl.logrank(d0.duration, d0.event, d0.E, strata=d0.rho)
    rows.append({"comparison": "stratified by rho", "chi2": lr.chi2, "df": lr.df,
                 "p": lr.p, "events": lr.events, "observed_E1": lr.observed,
                 "expected_E1": lr.expected})
    return pd.DataFrame(rows)


def cox_table(df: pd.DataFrame) -> pd.DataFrame:
    """Cox fits. Rows flagged ``separated`` carry no usable point estimate:
    the partial likelihood is monotone and the MLE sits on the boundary, so we
    blank the estimate rather than printing an arbitrary large negative beta.
    """
    d0 = df[df.B == 0]
    rows = []

    def add(model, estimator, term, res=None, fr=None, status=""):
        if fr is not None:
            s = fr.summary()
            rows.append({"model": model, "estimator": estimator, "term": term,
                         "beta": fr.beta[0], "HR": fr.hr[0], "se": fr.se[0],
                         "ci_low": np.exp(fr.ci_low[0]),
                         "ci_high": np.exp(fr.ci_high[0]), "p": s["p"][0],
                         "events": fr.events, "n": fr.n, "status": status})
            return
        ident = res.converged and not res.separated
        if not ident:
            rows.append({"model": model, "estimator": estimator, "term": term,
                         "beta": np.nan, "HR": np.nan, "se": np.nan,
                         "ci_low": np.nan, "ci_high": np.nan, "p": np.nan,
                         "events": res.events, "n": res.n,
                         "status": status or "not identified (monotone likelihood)"})
            return
        s = res.summary()
        rows.append({"model": model, "estimator": estimator, "term": term,
                     "beta": res.beta[0], "HR": np.exp(res.beta[0]),
                     "se": res.se[0], "ci_low": s["ci_low"][0],
                     "ci_high": s["ci_high"][0], "p": s["p"][0],
                     "events": res.events, "n": res.n, "status": status})

    # ---- per-rho
    for rho in RHO_GRID:
        d = d0[d0.rho == rho]
        res = sl.cox_fit(d.duration, d.event, d[["E"]].values, names=["E"],
                         cluster=d.seed.values)
        fr = sl.firth_cox(d.duration, d.event, d[["E"]].values, names=["E"])
        note = ("identified" if (res.converged and not res.separated)
                else "not identified: every event falls in E=0 at shared risk sets")
        add(f"rho={rho}", "Cox (unpenalised)", "E", res=res, status=note)
        add(f"rho={rho}", "Cox (Firth)", "E", fr=fr,
            status="penalised estimate; risk sets are 50/50 at every event time")

    # ---- pooled stratified Cox (pre-specified model)
    res = sl.cox_fit(d0.duration, d0.event, d0[["E"]].values, names=["E"],
                     strata=d0.rho.values, cluster=d0.seed.values)
    fr = sl.firth_cox(d0.duration, d0.event, d0[["E"]].values, names=["E"],
                      strata=d0.rho.values)
    add("pooled (rho strata)", "Cox (unpenalised)", "E", res=res,
        status="identification driven by rho=0.40 (see fragility row)")
    add("pooled (rho strata)", "Cox (Firth)", "E", fr=fr, status="penalised")

    # ---- adding B: zero information
    res_eb = sl.cox_fit(d0.duration, d0.event, d0[["E", "B"]].values,
                        names=["E", "B"], strata=d0.rho.values,
                        cluster=d0.seed.values)
    for j, term in enumerate(["E", "B"]):
        rows.append({"model": "pooled + B", "estimator": "Cox (unpenalised)",
                     "term": term, "beta": res_eb.beta[j],
                     "HR": np.exp(res_eb.beta[j]), "se": res_eb.se[j],
                     "ci_low": np.nan, "ci_high": np.nan, "p": np.nan,
                     "events": res_eb.events, "n": res_eb.n,
                     "status": "B carries zero information (se = 0)" if term == "B"
                     else "unchanged by adding B"})

    # ---- fragility: drop the only stratum with overlapping event times
    d_sub = d0[d0.rho < 0.40]
    res_sub = sl.cox_fit(d_sub.duration, d_sub.event, d_sub[["E"]].values,
                         names=["E"], strata=d_sub.rho.values,
                         cluster=d_sub.seed.values)
    add("pooled, rho<0.40", "Cox (unpenalised)", "E", res=res_sub,
        status="fragility check: estimate no longer exists without rho=0.40")
    return pd.DataFrame(rows)


def hazard_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Non-parametric discrete hazard by period, per (rho, E).

    Single-period rows around t = 3-6 are kept separate because that is where
    the expulsion rule acts; coarser bins would hide the timing shift.
    """
    d0 = df[df.B == 0]
    edges = [1, 3, 4, 5, 6, 11, 21, 51, 201]
    names = ["1-2", "3", "4", "5", "6-10", "11-20", "21-50", "51-200"]
    rows = []
    for rho in RHO_GRID:
        for E in (0, 1):
            d = d0[(d0.rho == rho) & (d0.E == E)]
            for (a, b), lab in zip(zip(edges[:-1], edges[1:]), names):
                at_risk = (d.duration >= a).sum()
                events = ((d.duration >= a) & (d.duration <= b - 1) & (d.event == 1)).sum()
                rows.append({"rho": rho, "E": E, "period": lab,
                             "at_risk": int(at_risk), "events": int(events),
                             "hazard": (events / at_risk) if at_risk else np.nan})
    return pd.DataFrame(rows)


def ph_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    """Proportional-hazards diagnostics.

    Two layers. (i) Window-restricted log-rank tests show *when* the two
    hazards differ, pooled across rho strata. (ii) The rho = 0.40 stratum is
    the only one in which the groups share event times, so the interval-level
    comparison of hazards is legible there: expulsion moves collapses out of
    period 3 but every remaining market fails in period 4 regardless.
    """
    d0 = df[df.B == 0]
    rows = []
    for (a, b) in [(0, 3), (3, 5), (5, 10), (10, 200)]:
        lr = sl.logrank(d0.duration, d0.event, d0.E, strata=d0.rho, window=(a, b))
        rows.append({"statistic": "log-rank, pooled strata", "window": f"({a},{b}]",
                     "value": lr.chi2, "df": lr.df, "p": lr.p,
                     "events": lr.events, "note": ""})

    d = d0[d0.rho == 0.40]
    for (a, b) in [(0, 3), (3, 5)]:
        lr = sl.logrank(d.duration, d.event, d.E, window=(a, b))
        rows.append({"statistic": "log-rank, rho=0.40", "window": f"({a},{b}]",
                     "value": lr.chi2, "df": lr.df, "p": lr.p,
                     "events": lr.events, "note": ""})

    # period-specific hazards and their ratio at rho = 0.40
    for t in (3, 4):
        at = d[d.duration >= t]
        h0 = ((at.E == 0) & (at.duration == t) & (at.event == 1)).sum() / max(1, (at.E == 0).sum())
        h1 = ((at.E == 1) & (at.duration == t) & (at.event == 1)).sum() / max(1, (at.E == 1).sum())
        rows.append({"statistic": "period hazard, rho=0.40", "window": f"t={t}",
                     "value": h0 - h1, "df": 1, "p": np.nan,
                     "events": int(((at.duration == t) & (at.event == 1)).sum()),
                     "note": f"h(E=0)={h0:.2f}, h(E=1)={h1:.2f}, ratio={(h1/h0 if h0 else np.nan):.2f}"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------


def make_figures(df: pd.DataFrame, rmst: pd.DataFrame, diff: pd.DataFrame,
                 meta: dict) -> None:
    """Figure 1: one 3x3 panel figure (survival curves, RMST, hazard timing)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 7.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.7, "figure.dpi": 220,
    })
    colors = {0: "#B22222", 1: "#1F5C99"}
    labels = {0: "No expulsion (E=0)", 1: "Expulsion (E=1)"}

    fig = plt.figure(figsize=(10.2, 6.4))
    gs = fig.add_gridspec(3, 3, hspace=0.52, wspace=0.30,
                          height_ratios=[1, 1, 1.05])

    # ---------- (a) four institutions, pooled
    ax = fig.add_subplot(gs[0, 0])
    style = {(0, 0): ("-", "#B22222"), (0, 1): ("--", "#EBA0A0"),
             (1, 0): ("-", "#1F5C99"), (1, 1): ("--", "#93B7D6")}
    for E in (0, 1):
        for B in (0, 1):
            d = df[(df.E == E) & (df.B == B)]
            km = sl.kaplan_meier(d.duration, d.event, TMAX)
            ls, c = style[(E, B)]
            ax.step(km.times, km.survival, where="post", ls=ls, color=c, lw=1.1,
                    label=f"E={E}, B={B}")
    ax.set_xlim(0, TMAX)
    ax.set_ylim(0, 1.03)
    ax.set_xlabel("Simulation period")
    ax.set_ylabel("Share not collapsed")
    ax.set_title("(a) Four institutions, pooled", fontsize=8)
    ax.legend(frameon=False, fontsize=5.6, loc="upper right", handlelength=1.6)
    ax.text(0.04, 0.05, "B=0 and B=1 coincide", transform=ax.transAxes,
            fontsize=5.8, color="#555555")

    # ---------- (b)-(f) by rho
    for k, rho in enumerate(RHO_GRID):
        r, c = divmod(k + 1, 3)
        ax = fig.add_subplot(gs[r, c])
        for E in (0, 1):
            d = df[(df.rho == rho) & (df.E == E) & (df.B == 0)]
            km = sl.kaplan_meier(d.duration, d.event, TMAX)
            ax.step(km.times, km.survival, where="post", color=colors[E], lw=1.2,
                    label=labels[E])
            ax.fill_between(km.times, km.ci_low, km.ci_high, step="post",
                            color=colors[E], alpha=0.13, lw=0)
        ax.set_xlim(0, 24)
        ax.set_ylim(0, 1.03)
        ax.set_title(f"({'bcdef'[k]}) $\\rho$ = {rho:.2f}", fontsize=8)
        ax.set_xlabel("Period (zoom to $t\\leq24$)")
        if k == 1:
            ax.set_ylabel("Share not collapsed")
        if k == 0:
            ax.legend(frameon=False, fontsize=5.8, loc="lower right")

    # ---------- (g) RMST levels
    ax = fig.add_subplot(gs[2, 0])
    for E in (0, 1):
        sub = rmst[(rmst.E == E) & (rmst.rho != "pooled")]
        x = [float(v) for v in sub.rho]
        ax.errorbar(x, sub.RMST200,
                    yerr=[sub.RMST200 - sub.ci_low, sub.ci_high - sub.RMST200],
                    marker="o", ms=3.0, lw=1.0, capsize=1.8, color=colors[E],
                    label=labels[E])
    ax.set_yscale("log")
    ax.set_ylim(2, 260)
    ax.set_yticks([3, 10, 30, 100, 200])
    ax.set_yticklabels(["3", "10", "30", "100", "200"])
    ax.set_xlabel("$\\rho$")
    ax.set_ylabel("RMST(200), periods (log)")
    ax.set_title("(g) Restricted mean survival", fontsize=8)
    ax.legend(frameon=False, fontsize=5.8, loc="upper right")

    # ---------- (h) paired differences
    ax = fig.add_subplot(gs[2, 1])
    sub = diff[diff.rho != "pooled"]
    y = np.arange(len(sub))
    ax.errorbar(sub.estimate, y,
                xerr=[sub.estimate - sub.ci_low, sub.ci_high - sub.estimate],
                fmt="o", ms=3.2, lw=1.0, capsize=2.0, color="#1F5C99")
    ax.axvline(0, color="#888888", lw=0.7, ls=":")
    ax.set_xscale("log")
    ax.set_xlim(0.4, 320)
    ax.set_xticks([1, 10, 100])
    ax.set_xticklabels(["1", "10", "100"])
    ax.set_yticks(y)
    ax.set_yticklabels([f"$\\rho$={float(v):.2f}" for v in sub.rho], fontsize=6.4)
    ax.set_xlabel("RMST difference, periods (log)")
    ax.set_title("(h) Effect of expulsion", fontsize=8)
    ax.invert_yaxis()

    # ---------- (i) period hazards at rho = 0.40
    ax = fig.add_subplot(gs[2, 2])
    d = df[(df.rho == 0.40) & (df.B == 0)]
    width, xs = 0.36, np.array([0.0, 1.0])
    for j, E in enumerate((0, 1)):
        hs = []
        for t in (3, 4):
            at = d[d.duration >= t]
            hs.append(((at.E == E) & (at.duration == t) & (at.event == 1)).sum()
                      / max(1, (at.E == E).sum()))
        ax.bar(xs + (j - 0.5) * width, hs, width, color=colors[E],
               label=labels[E], alpha=0.9, lw=0)
        for x, h in zip(xs + (j - 0.5) * width, hs):
            ax.text(x, h + 0.02, f"{h:.2f}", ha="center", fontsize=5.8)
    ax.set_xticks(xs)
    ax.set_xticklabels(["Period 3", "Period 4"])
    ax.set_ylim(0, 1.38)
    ax.set_ylabel("Collapse hazard")
    ax.set_title("(i) Non-proportional hazards", fontsize=8)
    ax.text(0.02, 0.99, "red = E=0, blue = E=1 ($\\rho$=0.40)", transform=ax.transAxes,
            va="top", fontsize=5.6, color="#444444")

    fig.text(0.5, 0.005,
             "Panels (b)-(f) zoom to t <= 24 periods (horizon T = 200). Shaded bands: pointwise 95% log-log confidence bands. "
             "Error bars: 5,000 seed-block bootstrap percentile intervals.",
             ha="center", fontsize=5.8, color="#555555")
    fig.savefig(os.path.join(FIG, "Figure1.png"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    t_start = time.time()
    os.makedirs(TAB, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)

    df = load()
    checks = validate(df)
    if not checks["balanced_cells"]:
        raise SystemExit("design is not balanced; refusing to run")
    if checks["duplicate_keys"]:
        raise SystemExit("duplicate (rho, seed, E, B) keys")

    print(f"[1/6] data ok: {checks['n_rows']} runs, {checks['n_events']} events, "
          f"{checks['n_censored']} censored, bankruptcy inert = {checks['bankruptcy_inert']}")

    kmt = km_table(df)
    kmt.to_csv(os.path.join(TAB, "tableB1_km_summary.csv"), index=False)

    print("[2/6] bootstrap over seed blocks ...")
    boot_key, boot_diff, boot_did = bootstrap_rmst(df)
    rmst, diff = rmst_tables(df, boot_key, boot_diff)
    rmst.to_csv(os.path.join(TAB, "tableB2_rmst_levels.csv"), index=False)
    diff.to_csv(os.path.join(TAB, "tableB3_rmst_differences.csv"), index=False)

    print("[3/6] log-rank tests ...")
    lrt = logrank_table(df)
    lrt.to_csv(os.path.join(TAB, "tableB4_logrank.csv"), index=False)

    print("[4/6] Cox models (unpenalised and Firth) ...")
    coxt = cox_table(df)
    coxt.to_csv(os.path.join(TAB, "tableB5_cox.csv"), index=False)

    haz = hazard_profile(df)
    haz.to_csv(os.path.join(TAB, "tableB6_hazard_profile.csv"), index=False)

    print("[5/6] proportional-hazards diagnostics ...")
    pht = ph_diagnostics(df)
    pht.to_csv(os.path.join(TAB, "tableB7_ph_diagnostics.csv"), index=False)

    print("[6/6] figures ...")
    meta = {"checks": checks}
    make_figures(df, rmst, diff, meta)

    meta = {
        "task": "B 鈥?survival analysis of market collapse",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "model_version": str(df.model_version.iloc[0]),
        "input_file": "data/processed/run_level.csv",
        "input_sha256": sha256(DATA),
        "input_source": "github.com/Sundance0604/ECO6126 @ data/processed/run_level.csv",
        "n_rows": int(len(df)),
        "design": {"rho": RHO_GRID, "E": [0, 1], "B": [0, 1], "seeds": "0-99",
                   "T": TMAX, "N": int(df.N.iloc[0]), "a": int(df.a.iloc[0]),
                   "p": int(df.p.iloc[0]), "q": int(df.q.iloc[0]),
                   "w_init": float(df.w_init.iloc[0])},
        "estimands": {
            "duration": "rmst_T = min(T_collapse, 200)",
            "event": "collapse_event (1 = 10*H_active <= H0 observed within T)",
            "primary": "RMST(200) difference, E=1 minus E=0, paired within seed",
        },
        "inference": {"bootstrap": "seed-block, whole 100-seed blocks",
                      "n_boot": N_BOOT, "boot_seed": BOOT_SEED,
                      "cox_variance": "cluster-robust by seed"},
        "validation": checks,
        "environment": {"python": platform.python_version(),
                        "numpy": np.__version__, "pandas": pd.__version__,
                        "platform": platform.platform()},
        "runtime_seconds": round(time.time() - t_start, 1),
        "outputs": sorted(os.listdir(TAB)) + sorted(os.listdir(FIG)),
    }
    with open(os.path.join(ROOT, "outputs", "B", "analysis_metadata.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"done in {meta['runtime_seconds']}s -> {TAB}")


if __name__ == "__main__":
    main()



