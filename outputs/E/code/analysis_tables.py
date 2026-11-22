"""Econometric analysis for Section 7 (Mechanism and Welfare Analysis).

Reads the simulation output, estimates the three mechanism regressions,
the collapse equation with and without post-treatment controls, carries out
the welfare accounting, and writes every table as CSV plus a single JSON
file that the report generator uses for in-text numbers.
"""
import sys, os, csv, json, math
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np

OUT = r"C:\Users\86187\WorkBuddy\2026-11-22-21-56-35\outputs"
DATA = os.path.join(OUT, "data")
TAB = os.path.join(OUT, "tables")
os.makedirs(TAB, exist_ok=True)

rng = np.random.default_rng(20261122)


def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def num(r, k, default=0.0):
    try:
        return float(r[k])
    except (KeyError, TypeError, ValueError):
        return default


RUNS = read_csv(os.path.join(DATA, "run_level.csv"))
PARAMS = json.load(open(os.path.join(DATA, "params.json"), encoding="utf-8"))
MAIN = [r for r in RUNS if r["sample"] == "main"]
A_SUB = [r for r in RUNS if r["sample"] == "a_robust"]
C_SUB = [r for r in RUNS if r["sample"] == "c_robust"]
# A cell is one parameter configuration x institution; the 30 seeds inside
# a cell share the same design and are the natural resampling cluster.
for r in RUNS:
    r["cell_id"] = "rho%.2f_p%d_a%d_E%d_c%.2f" % (
        num(r, "rho"), num(r, "p"), num(r, "a"), num(r, "E"), num(r, "c"))


# ----------------------------- OLS machinery -----------------------------
def ols(y, X, cluster):
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    u = y - X @ beta
    groups = np.unique(cluster)
    meat = np.zeros((k, k))
    for g in groups:
        idx = (cluster == g)
        s = X[idx].T @ u[idx]
        meat += np.outer(s, s)
    G = len(groups)
    adj = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    V = (XtX_inv @ meat @ XtX_inv) * adj
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    t = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
    return beta, se, t, V


def cluster_bootstrap(y, X, cluster, j, B=2000):
    """Resample whole clusters (seeds) and return percentile CI for beta_j."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    groups = np.unique(cluster)
    idx_by_g = {g: np.flatnonzero(cluster == g) for g in groups}
    G = len(groups)
    est = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, G, size=G)
        idx = np.concatenate([idx_by_g[groups[g]] for g in pick])
        try:
            bb = np.linalg.lstsq(X[idx], y[idx], rcond=None)[0]
            est[b] = bb[j]
        except np.linalg.LinAlgError:
            est[b] = np.nan
    est = est[~np.isnan(est)]
    return float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))


def stars(t):
    a = abs(t)
    return "***" if a >= 2.576 else ("**" if a >= 1.96 else ("*" if a >= 1.645 else ""))


def design(rows, with_fe=False, extra=None):
    n = len(rows)
    E = np.array([num(r, "E") for r in rows])
    rho = np.array([num(r, "rho") for r in rows])
    p = np.array([num(r, "p") for r in rows])
    p3 = (p == 3).astype(float)
    p4 = (p == 4).astype(float)
    cols = [np.ones(n), E, rho, p3, p4, E * rho, E * p3, E * p4]
    names = ["Constant", "E", "rho", "p=3", "p=4", "E x rho", "E x p=3", "E x p=4"]
    if with_fe:
        cfgs = sorted(set((num(r, "rho"), num(r, "p")) for r in rows))[1:]
        cm = np.array([[1.0 if (num(r, "rho"), num(r, "p")) == c else 0.0
                        for c in cfgs] for r in rows])
        cols.append(cm)
        for c in cfgs:
            names.append("FE rho=%.2f,p=%d" % c)
    if extra:
        for label, vals in extra:
            cols.append(np.asarray(vals, float))
            names.append(label)
    return np.column_stack(cols), names


def vec(rows, key):
    return np.array([num(r, key) for r in rows], float)


def reg_table(rows, outcomes, cluster_key="cell_id", with_fe=False, extra=None,
              boot=True, label=""):
    cluster = np.array([r[cluster_key] for r in rows])
    out = {}
    for name, key, scale in outcomes:
        y = vec(rows, key) * scale
        X, names = design(rows, with_fe=with_fe, extra=extra)
        beta, se, t, V = ols(y, X, cluster)
        ci = cluster_bootstrap(y, X, cluster, 1, B=1200) if boot else (np.nan, np.nan)
        out[name] = dict(
            coef=[round(float(b), 6) for b in beta],
            se=[round(float(s), 6) for s in se],
            t=[round(float(x), 4) for x in t],
            stars=[stars(x) for x in t],
            ci_E=[round(ci[0], 6), round(ci[1], 6)],
            names=names,
            n=len(rows), k=X.shape[1],
            r2=round(1.0 - float(np.sum((y - X @ beta) ** 2) /
                                np.sum((y - y.mean()) ** 2)), 4),
            clusters=len(np.unique(cluster)),
        )
    return out


# ----------------------------- Table 7.1 -----------------------------
tab71 = [
    dict(Parameter="Market size", Symbol="N", Value="200", Role="Closed population, no entry"),
    dict(Parameter="Initial honest / cheaters", Symbol="H0 / C0", Value="N(1-rho) / N*rho", Role="rho on 0.05-0.40 grid"),
    dict(Parameter="Initial wealth", Symbol="w0", Value="20", Role="Identical for every agent"),
    dict(Parameter="Observation window", Symbol="T", Value="200", Role="Fixed horizon, right censoring"),
    dict(Parameter="Counterparties per step", Symbol="a", Value="3", Role="Robustness: 2, 4"),
    dict(Parameter="H-H one-sided payoff", Symbol="g_HH", Value="+1.5", Role="2 g_HH = +3 per trade"),
    dict(Parameter="C-C one-sided payoff", Symbol="g_CC", Value="-2.0", Role="2 g_CC = -4 per trade"),
    dict(Parameter="H-C transfer", Symbol="x", Value="5.0", Role="Pure transfer, sum = 0"),
    dict(Parameter="Conversion threshold", Symbol="p", Value="2, 3, 4", Role="Victimisations before H becomes C"),
    dict(Parameter="Eviction threshold", Symbol="q", Value="3", Role="Reports before expulsion"),
    dict(Parameter="Survival cost", Symbol="c", Value="0 (main); 0.10, 0.30", Role="Per active agent per step"),
    dict(Parameter="Expulsion switch", Symbol="E", Value="0, 1", Role="Institutional treatment"),
    dict(Parameter="Bankruptcy", Symbol="w <= 0", Value="always on", Role="Wealth zeroed, agent exits"),
    dict(Parameter="Seeds per cell", Symbol="S", Value="30 (main), 20 (subsamples)", Role="Common random numbers"),
]


# ----------------------------- Table 7.2 -----------------------------
tab72 = [
    dict(Block="Macro", Variable="Active agents", Definition="Number of agents still participating in the market"),
    dict(Block="Macro", Variable="Active honest / cheaters", Definition="Active agents split by current identity"),
    dict(Block="Macro", Variable="Active wealth", Definition="Sum of wealth held by active agents"),
    dict(Block="Macro", Variable="Evicted-label wealth", Definition="Wealth retained at exit by agents carrying the eviction label"),
    dict(Block="Macro", Variable="Cumulative conversions", Definition="Honest agents crossing m >= p"),
    dict(Block="Macro", Variable="Cumulative bankruptcy / eviction / both", Definition="Exit labels; both records simultaneous triggers"),
    dict(Block="Macro", Variable="Cumulative exits", Definition="Agents leaving the market under any label"),
    dict(Block="Macro", Variable="Trade edges in step", Definition="Distinct pairs settled in the current step"),
    dict(Block="Macro", Variable="Surviving agents", Definition="Agents with positive wealth (alive flag)"),
    dict(Block="Macro", Variable="Cumulative deaths", Definition="Agents whose wealth reached zero"),
    dict(Block="Macro", Variable="Trade / cost deaths", Definition="Deaths caused by trading losses / by the survival cost"),
    dict(Block="Individual", Variable="Identity", Definition="Honest (H) or cheater (C) at the end of the step"),
    dict(Block="Individual", Variable="Current wealth", Definition="Balance after step-end settlement"),
    dict(Block="Individual", Variable="Cumulative victimisation m", Definition="Number of fraudulent encounters"),
    dict(Block="Individual", Variable="Report count r", Definition="Reports accumulated by a cheater"),
    dict(Block="Individual", Variable="Blacklist size", Definition="Number of counterparties blacklisted by the agent"),
    dict(Block="Individual", Variable="Blacklisted-by count", Definition="Number of agents blacklisting this agent"),
    dict(Block="Individual", Variable="First-exit wealth snapshot", Definition="Wealth recorded at the first exit"),
    dict(Block="Individual", Variable="First-exit time", Definition="Step of the first exit"),
    dict(Block="Individual", Variable="Death time", Definition="Step in which wealth reached zero"),
    dict(Block="Individual", Variable="Death cause", Definition="-1 none, 0 trade death, 1 cost death"),
    dict(Block="Activity", Variable="Active flag", Definition="1 while participating, 0 after exit"),
    dict(Block="Activity", Variable="Bankruptcy flag", Definition="1 if wealth was exhausted"),
    dict(Block="Activity", Variable="Eviction flag", Definition="1 if r reached q under E = 1"),
    dict(Block="Activity", Variable="Both flag", Definition="1 if bankruptcy and eviction triggered together"),
    dict(Block="Activity", Variable="Alive flag", Definition="1 while wealth is positive; exit need not imply death"),
]


# ----------------------------- Table 7.3 -----------------------------
DESC_VARS = [
    ("survival_steps", "Restricted survival steps"),
    ("collapse_event", "Collapse observed (0/1)"),
    ("fraud_count", "Fraudulent trades (H-C)"),
    ("cooperation_count", "Cooperative trades (H-H)"),
    ("collusion_count", "Cheater-cheater trades (C-C)"),
    ("total_edges", "All traded edges"),
    ("conversion_share", "Conversion share of H0"),
    ("converted_H", "Converted honest agents"),
    ("active_final", "Active agents at T"),
    ("active_h_final", "Active honest at T"),
    ("active_c_final", "Active cheaters at T"),
    ("end_active_wealth", "Wealth of active agents"),
    ("evicted_wealth", "Wealth of evicted-label agents"),
    ("cum_bankrupt", "Bankruptcy labels"),
    ("cum_evicted", "Eviction labels"),
    ("cum_both", "Both labels"),
    ("cum_exit", "All exits"),
    ("cum_death", "Deaths"),
    ("trade_death", "Trade deaths"),
    ("cost_death", "Cost deaths"),
    ("alive_final", "Surviving agents"),
    ("wt_realised", "Cumulative net benefit W_T"),
    ("end_wealth_total", "End-period total wealth"),
    ("resource_adjusted_wt", "Resource-adjusted W_T"),
]
tab73 = []
for key, label in DESC_VARS:
    v0 = vec([r for r in MAIN if num(r, "E") == 0], key)
    v1 = vec([r for r in MAIN if num(r, "E") == 1], key)
    tab73.append(dict(Variable=label,
                      E0_mean=round(float(v0.mean()), 3), E0_sd=round(float(v0.std(ddof=1)), 3),
                      E1_mean=round(float(v1.mean()), 3), E1_sd=round(float(v1.std(ddof=1)), 3),
                      Difference=round(float(v1.mean() - v0.mean()), 3)))


# ----------------------------- Table 7.4 -----------------------------
OUTCOMES = [
    ("Fraud", "fraud_count", 1.0),
    ("Conversion", "conversion_share", 1.0),
    ("Cooperation", "cooperation_count", 1.0),
]
mech = reg_table(MAIN, OUTCOMES, cluster_key="cell_id", boot=True)
# also normalised-by-trade composition outcomes
for r in MAIN:
    te = num(r, "total_edges")
    r["_fraud_share"] = num(r, "fraud_count") / te if te else 0.0
    r["_coop_share"] = num(r, "cooperation_count") / te if te else 0.0
mech_share = reg_table(MAIN, [("Fraud share", "_fraud_share", 1.0),
                              ("Cooperation share", "_coop_share", 1.0)],
                       cluster_key="cell_id", boot=False)

tab74_rows = []
order = ["Constant", "E (expulsion)", "rho", "p = 3", "p = 4", "E x rho", "E x p = 3", "E x p = 4"]
keymap = {"Constant": "Constant", "E (expulsion)": "E", "rho": "rho", "p = 3": "p=3",
          "p = 4": "p=4", "E x rho": "E x rho", "E x p = 3": "E x p=3", "E x p = 4": "E x p=4"}
for disp in order:
    src = keymap[disp]
    row = dict(Variable=disp)
    for name in ("Fraud", "Conversion", "Cooperation"):
        d = mech[name]
        i = d["names"].index(src)
        row[name] = "%.3f%s (%.3f)" % (d["coef"][i], d["stars"][i], d["se"][i])
    tab74_rows.append(row)
cirow = dict(Variable="95% CI for E (cluster bootstrap)")
for name in ("Fraud", "Conversion", "Cooperation"):
    cirow[name] = "[%.3f, %.3f]" % tuple(mech[name]["ci_E"])
tab74_rows.append(cirow)
for label, attr in [("Observations", "n"), ("R-squared", "r2"),
                    ("Clusters (rho x p x E cell)", "clusters")]:
    tab74_rows.append(dict(Variable=label,
                           Fraud=mech["Fraud"][attr],
                           Conversion=mech["Conversion"][attr],
                           Cooperation=mech["Cooperation"][attr]))


# ----------------------------- Table 7.5 -----------------------------
PT = [("Fraud / 1e3", [num(r, "fraud_count") / 1000.0 for r in MAIN]),
      ("Conversion", [num(r, "conversion_share") for r in MAIN]),
      ("Cooperation / 1e3", [num(r, "cooperation_count") / 1000.0 for r in MAIN])]
specs = []
for label, extra in [("(1) Baseline", None), ("(2) + post-treatment outcomes", PT),
                     ("(3) + outcomes, config FE", PT)]:
    X, names = design(MAIN, with_fe=(label.startswith("(3)")), extra=extra)
    y = vec(MAIN, "survival_steps")
    cl = np.array([r["cell_id"] for r in MAIN])
    beta, se, t, V = ols(y, X, cl)
    j = names.index("E")
    specs.append(dict(Specification=label,
                      beta_E=round(float(beta[j]), 4),
                      se_E=round(float(se[j]), 4),
                      t_E=round(float(t[j]), 3),
                      ci_E=[round(x, 4) for x in cluster_bootstrap(y, X, cl, j, B=1200)],
                      r2=round(1.0 - float(np.sum((y - X @ beta) ** 2) / np.sum((y - y.mean()) ** 2)), 4),
                      n=len(MAIN)))
    # also store coefficients on the three post-treatment variables
    if extra:
        for nm, _ in PT:
            jj = names.index(nm)
            specs[-1][nm] = (round(float(beta[jj]), 4), round(float(se[jj]), 4), round(float(t[jj]), 3))
base_beta = specs[0]["beta_E"]
naive_beta = specs[1]["beta_E"]
tab75_rows = []
for s in specs:
    tab75_rows.append(dict(
        Specification=s["Specification"],
        E_coefficient="%.3f (%.3f)" % (s["beta_E"], s["se_E"]),
        CI_95="[%.3f, %.3f]" % tuple(s["ci_E"]),
        Fraud=("%.3f" % s["Fraud / 1e3"][0]) if "Fraud / 1e3" in s else "-",
        Conversion=("%.3f" % s["Conversion"][0]) if "Conversion" in s else "-",
        Cooperation=("%.3f" % s["Cooperation / 1e3"][0]) if "Cooperation / 1e3" in s else "-",
        R2=s["r2"], N=s["n"]))
apparent_share = (base_beta - naive_beta) / base_beta if base_beta else float("nan")


# ----------------------------- Table 7.6 -----------------------------
def mean_by(rows, key, filt=lambda r: True):
    v = vec([r for r in rows if filt(r)], key)
    return float(v.mean()) if len(v) else float("nan")


tab76_rules = [
    dict(Type="H-H (cooperation)", Payoff_i="+g_HH = +1.5", Payoff_j="+g_HH = +1.5",
         S_ij="2 g_HH = +3.0", Sign="Positive (wealth creating)"),
    dict(Type="C-C (collusion)", Payoff_i="g_CC = -2.0", Payoff_j="g_CC = -2.0",
         S_ij="2 g_CC = -4.0", Sign="Negative (wealth destroying)"),
    dict(Type="H-C (fraud)", Payoff_i="g_HC^H = -x", Payoff_j="g_HC^C = +x",
         S_ij="0", Sign="Zero (pure transfer)"),
]
tab76_rows = []
WELFARE_VARS = [
    ("wt_realised", "W_T, realised social net benefit"),
    ("wt_theory", "W_T, theoretical (no truncation)"),
    ("truncation_gap", "Theoretical minus realised"),
    ("wt_hh", "Contribution of H-H trades"),
    ("wt_cc", "Contribution of C-C trades"),
    ("wt_hc", "Contribution of H-C trades"),
    ("cooperation_count", "Cooperative trade volume (trades)"),
    ("cooperation_volume", "Cooperative traded value (2 g_HH x trades)"),
    ("fraud_count", "Fraudulent trades"),
    ("collusion_count", "Cheater-cheater trades"),
    ("end_wealth_total", "End-period total wealth"),
    ("end_active_wealth", "End-period wealth of active agents"),
    ("evicted_wealth", "Wealth retained by evicted-label agents"),
    ("survival_steps", "Restricted market survival (steps)"),
    ("accounting_gap", "Wealth accounting identity error"),
    ("cost_realised", "Realised survival cost"),
    ("resource_adjusted_wt", "Resource-adjusted welfare W_T - c"),
]
for key, label in WELFARE_VARS:
    tab76_rows.append(dict(Outcome=label,
                           E0=round(mean_by(MAIN, key, lambda r: num(r, "E") == 0), 3),
                           E1=round(mean_by(MAIN, key, lambda r: num(r, "E") == 1), 3),
                           Difference=round(mean_by(MAIN, key, lambda r: num(r, "E") == 1)
                                            - mean_by(MAIN, key, lambda r: num(r, "E") == 0), 3)))


# ----------------------------- Table 7.7 -----------------------------
COST_VARS = [
    ("wt_realised", "Transaction welfare W_T"),
    ("cost_realised", "Realised survival cost c"),
    ("resource_adjusted_wt", "Resource-adjusted welfare"),
    ("end_wealth_total", "End-period total wealth"),
    ("survival_steps", "Restricted survival steps"),
    ("trade_death", "Trade deaths"),
    ("cost_death", "Cost deaths"),
    ("cum_bankrupt", "Bankruptcy labels"),
    ("cum_evicted", "Eviction labels"),
    ("cum_both", "Both labels"),
    ("cum_exit", "All market exits"),
    ("alive_final", "Surviving agents"),
    ("evicted_wealth", "Wealth retained at eviction"),
]
tab77_rows = []
for c in [0.0, 0.10, 0.30]:
    for E in [0, 1]:
        sub = [r for r in C_SUB if num(r, "c") == c and num(r, "E") == E]
        rec = dict(c=c, E=E)
        for key, label in COST_VARS:
            rec[key] = round(mean_by(sub, key), 3)
        tab77_rows.append(rec)


# ----------------------------- Table 7.8 -----------------------------
ROBUST_ROWS = []
def add_rob(label, rows, outcomes, cluster="cell_id", **kw):
    res = reg_table(rows, outcomes, cluster_key=cluster, boot=False, **kw)
    ROBUST_ROWS.append(dict(
        Specification=label,
        Fraud="%.3f%s (%.3f)" % (res["Fraud"]["coef"][1], res["Fraud"]["stars"][1], res["Fraud"]["se"][1]),
        Conversion="%.3f%s (%.3f)" % (res["Conversion"]["coef"][1], res["Conversion"]["stars"][1], res["Conversion"]["se"][1]),
        Cooperation="%.3f%s (%.3f)" % (res["Cooperation"]["coef"][1], res["Cooperation"]["stars"][1], res["Cooperation"]["se"][1]),
        N=res["Fraud"]["n"]))

add_rob("Main specification (Table 7.4)", MAIN, OUTCOMES)
add_rob("Configuration (rho x p) fixed effects", MAIN, OUTCOMES, with_fe=True)
add_rob("Clustered on seed (common random numbers)", MAIN, OUTCOMES,
        cluster="seed")
add_rob("Clustered on config x seed block", MAIN, OUTCOMES,
        cluster="paired_block_id")
for a in [2, 4]:
    add_rob("Trading capacity a = %d (seed clusters)" % a,
            [r for r in A_SUB if num(r, "a") == a], OUTCOMES, cluster="seed")
# composition outcomes
comp = reg_table(MAIN, [("Fraud", "_fraud_share", 1.0),
                        ("Conversion", "conversion_share", 1.0),
                        ("Cooperation", "_coop_share", 1.0)], boot=False)
ROBUST_ROWS.append(dict(
    Specification="Per-trade composition outcomes",
    Fraud="%.3f%s (%.3f)" % (comp["Fraud"]["coef"][1], comp["Fraud"]["stars"][1], comp["Fraud"]["se"][1]),
    Conversion="n.a.",
    Cooperation="%.3f%s (%.3f)" % (comp["Cooperation"]["coef"][1], comp["Cooperation"]["stars"][1], comp["Cooperation"]["se"][1]),
    N=comp["Fraud"]["n"]))
# truncated conversion
for r in MAIN:
    r["_conv_trunc"] = min(max(num(r, "conversion_share"), 0.02), 0.98)
trunc = reg_table(MAIN, [("Fraud", "fraud_count", 1.0),
                         ("Conversion", "_conv_trunc", 1.0),
                         ("Cooperation", "cooperation_count", 1.0)], boot=False)
ROBUST_ROWS.append(dict(
    Specification="Conversion truncated to [0.02, 0.98]",
    Fraud="%.3f%s (%.3f)" % (trunc["Fraud"]["coef"][1], trunc["Fraud"]["stars"][1], trunc["Fraud"]["se"][1]),
    Conversion="%.3f%s (%.3f)" % (trunc["Conversion"]["coef"][1], trunc["Conversion"]["stars"][1], trunc["Conversion"]["se"][1]),
    Cooperation="%.3f%s (%.3f)" % (trunc["Cooperation"]["coef"][1], trunc["Cooperation"]["stars"][1], trunc["Cooperation"]["se"][1]),
    N=trunc["Fraud"]["n"]))


# ----------------------------- write everything -----------------------------
def write(name, rows):
    if not rows:
        return
    path = os.path.join(TAB, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print("wrote", name, len(rows), "rows")


write("table7_1_calibration.csv", tab71)
write("table7_2_variables.csv", tab72)
write("table7_3_descriptives.csv", tab73)
write("table7_4_mechanism_regressions.csv", tab74_rows)
write("table7_5_collapse_bad_control.csv", tab75_rows)
write("table7_6_welfare.csv", tab76_rows)
write("table7_6a_net_benefit_rules.csv", tab76_rules)
write("table7_7_cost_and_exit.csv", tab77_rows)
write("table7_8_robustness.csv", ROBUST_ROWS)

# numbers used in the report text
KN = dict(
    n_main=len(MAIN), n_total=len(RUNS),
    n_clusters=len(set(r["cell_id"] for r in MAIN)),
    n_seeds=len(set(r["seed"] for r in MAIN)),
    beta_fraud=mech["Fraud"]["coef"][1], se_fraud=mech["Fraud"]["se"][1],
    ci_fraud=mech["Fraud"]["ci_E"],
    beta_conv=mech["Conversion"]["coef"][1], se_conv=mech["Conversion"]["se"][1],
    ci_conv=mech["Conversion"]["ci_E"],
    beta_coop=mech["Cooperation"]["coef"][1], se_coop=mech["Cooperation"]["se"][1],
    ci_coop=mech["Cooperation"]["ci_E"],
    inter_fraud=mech["Fraud"]["coef"][5], inter_conv=mech["Conversion"]["coef"][5],
    inter_coop=mech["Cooperation"]["coef"][5],
    r2_fraud=mech["Fraud"]["r2"], r2_conv=mech["Conversion"]["r2"],
    r2_coop=mech["Cooperation"]["r2"],
    beta_fraud_share=comp["Fraud"]["coef"][1],
    beta_coop_share=comp["Cooperation"]["coef"][1],
    base_beta=base_beta, naive_beta=naive_beta,
    base_ci=specs[0]["ci_E"], naive_ci=specs[1]["ci_E"],
    apparent_share=apparent_share,
    surv0=mean_by(MAIN, "survival_steps", lambda r: num(r, "E") == 0),
    surv1=mean_by(MAIN, "survival_steps", lambda r: num(r, "E") == 1),
    fraud0=mean_by(MAIN, "fraud_count", lambda r: num(r, "E") == 0),
    fraud1=mean_by(MAIN, "fraud_count", lambda r: num(r, "E") == 1),
    conv0=mean_by(MAIN, "conversion_share", lambda r: num(r, "E") == 0),
    conv1=mean_by(MAIN, "conversion_share", lambda r: num(r, "E") == 1),
    coop0=mean_by(MAIN, "cooperation_count", lambda r: num(r, "E") == 0),
    coop1=mean_by(MAIN, "cooperation_count", lambda r: num(r, "E") == 1),
    wt0=mean_by(MAIN, "wt_realised", lambda r: num(r, "E") == 0),
    wt1=mean_by(MAIN, "wt_realised", lambda r: num(r, "E") == 1),
    wthh0=mean_by(MAIN, "wt_hh", lambda r: num(r, "E") == 0),
    wthh1=mean_by(MAIN, "wt_hh", lambda r: num(r, "E") == 1),
    wtcc0=mean_by(MAIN, "wt_cc", lambda r: num(r, "E") == 0),
    wtcc1=mean_by(MAIN, "wt_cc", lambda r: num(r, "E") == 1),
    endw0=mean_by(MAIN, "end_wealth_total", lambda r: num(r, "E") == 0),
    endw1=mean_by(MAIN, "end_wealth_total", lambda r: num(r, "E") == 1),
    acct_gap=max(abs(num(r, "accounting_gap")) for r in MAIN),
    cost_c30_wt0=mean_by(C_SUB, "wt_realised", lambda r: num(r, "c") == 0.30 and num(r, "E") == 0),
    cost_c30_wt1=mean_by(C_SUB, "wt_realised", lambda r: num(r, "c") == 0.30 and num(r, "E") == 1),
    cost_c30_adj1=mean_by(C_SUB, "resource_adjusted_wt", lambda r: num(r, "c") == 0.30 and num(r, "E") == 1),
    cost_c30_costdeath1=mean_by(C_SUB, "cost_death", lambda r: num(r, "c") == 0.30 and num(r, "E") == 1),
    cost_c30_tradedeath1=mean_by(C_SUB, "trade_death", lambda r: num(r, "c") == 0.30 and num(r, "E") == 1),
    cost_c0_evicted1=mean_by(C_SUB, "cum_evicted", lambda r: num(r, "c") == 0.0 and num(r, "E") == 1),
    cost_c0_bank1=mean_by(C_SUB, "cum_bankrupt", lambda r: num(r, "c") == 0.0 and num(r, "E") == 1),
    cost_c0_both1=mean_by(C_SUB, "cum_both", lambda r: num(r, "c") == 0.0 and num(r, "E") == 1),
    cost_c0_alive1=mean_by(C_SUB, "alive_final", lambda r: num(r, "c") == 0.0 and num(r, "E") == 1),
    cost_c0_death1=mean_by(C_SUB, "cum_death", lambda r: num(r, "c") == 0.0 and num(r, "E") == 1),
)

payload = dict(key_numbers=KN, tables=dict(
    t71=tab71, t72=tab72, t73=tab73, t74=tab74_rows, t75=tab75_rows,
    t76=tab76_rows, t76a=tab76_rules, t77=tab77_rows, t78=ROBUST_ROWS),
    regressions=dict(mechanism=mech, mechanism_share=mech_share, collapse=specs))
with open(os.path.join(DATA, "analysis.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, default=float)
print("wrote analysis.json")
print("KEY:", json.dumps({k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in KN.items() if not isinstance(v, list)}, indent=1, default=float))
