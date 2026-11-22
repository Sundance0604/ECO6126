"""Build Markdown and Word versions of the Section 7 report.

The prose mirrors build_report.py (same numbers injected from analysis.json).
Math is written as LaTeX ($...$ / $$...$$). The Markdown file references the
PNG figures with relative paths; pandoc converts it to report.docx with native
OMML equations and embedded images. A python-docx pass then enforces the
house style: black text only, no bold, no italic.
"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

OUT = r"C:\Users\86187\WorkBuddy\2026-11-22-21-56-35\outputs"
DATA = os.path.join(OUT, "data")
A = json.load(open(os.path.join(DATA, "analysis.json"), encoding="utf-8"))
K = A["key_numbers"]
T = A["tables"]

def n2(x):
    return "{:,.2f}".format(x)

def n3(x):
    return "{:,.3f}".format(x)

rho_f = -K["beta_fraud"] / K["inter_fraud"]
rho_c = -K["beta_conv"] / K["inter_conv"]
rho_k = -K["beta_coop"] / K["inter_coop"]

EQ = {
    "pop":      (r"N = H_0 + C_0,\qquad \rho = C_0/N", False),
    "time":     (r"t = 0,1,\ldots,T", False),
    "match":    (r"|\mathcal{P}_{i,t}| \le a,\qquad (i,j)\in\mathcal{A}_t \Rightarrow j\notin\mathcal{B}_{i,t},\ i\notin\mathcal{B}_{j,t}", True),
    "sync":     (r"\text{type}_{i,s}=\text{type}_{i,t}\quad \text{for every transaction } s \text{ settled in step } t", True),
    "conv":     (r"m_{i,t}\ge p \ \Longrightarrow\ \text{type}_{i,t+1}=C \quad (\text{irreversible})", True),
    "exit":     (r"w_{i,t}\le 0 \Rightarrow w_{i,t}=0,\ \text{exit};\qquad r_{i,t}\ge q \Rightarrow \text{exit with } w_{i,t}\ \text{retained}", True),
    "sij":      (r"S_{ij}=g_{ij}^{i}+g_{ij}^{j}", False),
    "srules":   (r"S^{HH}=2g_{HH}>0,\qquad S^{CC}=2g_{CC}<0,\qquad S^{HC}=g_{HC}^{H}+g_{HC}^{C}=0", True),
    "wt":       (r"W_T=\sum_{t=1}^{T}\ \sum_{(i,j)\in\mathcal{A}_t}\left(g_{ij}^{i}+g_{ij}^{j}\right)", True),
    "wtr":      (r"W_T^{R}=W_T-\sum_{t=1}^{T}\sum_{i\in\mathcal{I}_t} c", True),
    "mech":     (r"Y_i^{k}=\alpha_k+\beta_k E_i+\gamma_k^{\prime}X_i+\delta_k(E_i\times\rho_i)+\lambda_k^{\prime}\left(E_i\times 1[p_i]\right)+\varepsilon_i^{k},\qquad k\in\{F,C,K\}", True),
    "collapse1":(r"Y_i=\alpha+\beta E_i+\gamma^{\prime}X_i+\varepsilon_i", True),
    "collapse2":(r"Y_i=\alpha+\beta^{\prime}E_i+\phi_1 F_i+\phi_2 C_i+\phi_3 K_i+\gamma^{\prime}X_i+u_i", True),
    "share":    (r"1-\hat{\beta}^{\prime}/\hat{\beta}", False),
    "acct":     (r"\sum_{i=1}^{N} w_{i,T}=N w_0+W_T^{\mathrm{real}}-C_T^{\mathrm{real}}", True),
    "y":        (r"Y=\min(T^{\mathrm{collapse}},T)", False),
    "sijreal":  (r"S_{ij}^{\mathrm{real}}=\Delta w_i+\Delta w_j", False),
}

def eq(key):
    src, disp = EQ[key]
    return ("$$%s$$" % src) if disp else ("$%s$" % src)

def md_table(rows, headers):
    o = ["| " + " | ".join(headers) + " |",
         "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        cells = [str(r[k]).replace("|", "\\|") for k in r.keys()]
        o.append("| " + " | ".join(cells) + " |")
    return "\n".join(o)

def table_md(rows, headers, caption, note=None):
    o = [caption, "", md_table(rows, headers)]
    if note:
        o += ["", "Note: " + note]
    return "\n".join(o)

def fig_md(name, caption):
    return "![%s](figures/%s.png)\n\n%s" % (name, name, caption)

M = []
add = M.append

add("# 7. Mechanism and Welfare Analysis")
add("")
add("Reputation punishment and market collapse in a closed trading market")
add("")
add("Simulation-based study | Fixed observation window T = 200 | 1,840 runs")
add("")

add("## Abstract")
add("")
add(f"""Expulsion changes market outcomes only if it changes what happens inside the
market. This section examines the composition of trade and the social value of that trade using
{K['n_main']:,} paired simulation runs spanning eight initial cheater shares, three conversion
thresholds and {K['n_seeds']} random seeds. Three mechanism outcomes — fraudulent trades, the
conversion share and cooperative trades — are regressed on the institutional switch and
predetermined controls. Averaged over the experimental grid, expulsion lowers fraud from
{n2(K['fraud0'])} to {n2(K['fraud1'])} trades and the conversion share from {n3(K['conv0'])} to
{n3(K['conv1'])}, while cooperative trades rise from {n2(K['coop0'])} to {n2(K['coop1'])};
all three effects attenuate as the initial cheater share increases. We then show why these
post-treatment outcomes cannot be inserted into the collapse equation as though they identified
a causal mediation channel: doing so absorbs {n2(100*K['apparent_share'])}% of the treatment
coefficient. Welfare is aggregated from transaction-level social net benefits over a fixed
horizon and reported together with cooperative volume, end-period wealth and market survival,
then recomputed under a per-step survival cost. Market exit is kept separate from
wealth-exhaustion death throughout.""")

add("")
add("## 7.0 Model overview")
add("")
add("### Population, timing and synchronous settlement")
add("")
add(f"""At t = 0 a closed market contains N = 200 agents, each endowed with $w_0 = 20$.
A share $\\rho$ of them are cheaters (C) and the remainder are honest (H), so {eq('pop')} and
the initial composition is fixed for the whole run. There is no entry. Time is discrete,
{eq('time')} with T = 200; t = 0 denotes the initial state and all trading occurs in steps
1 to T. Identities are frozen within a step: every payoff in step t is computed from the
identities prevailing at the beginning of that step, and identity changes are applied only at
the step end. {eq('sync')}""")

add("")
add("### Matching, capacity and blacklists")
add("")
add(f"""In each step an active agent may trade with at most a = 3 distinct counterparties, and
any pair trades at most once per step. Matching is implemented as rounds of random
permutations of the active set; a proposed pair is discarded if either agent has reached the
per-step cap, if the pair has already traded in the step, or if either side is blacklisted by
the other. {eq('match')} Blacklists are directional and permanent. An honest agent who is
defrauded blacklists the cheater and files one report against him; two cheaters who meet
blacklist each other but do not report. Blacklist updates take effect at the step end, so
the same pair can defraud a given honest agent at most once.""")

add("")
add("### Transaction types, identity change and exit")
add("")
add(f"""Three transaction types are possible. Two honest agents each receive
$g_{{HH}} = +1.5$; two cheaters each incur $g_{{CC}} = -2.0$; an honest–cheater pair transfers
$x = 5$ from the honest agent to the cheater, so the two sides sum to zero. The transfer is
truncated at the honest agent's balance and therefore remains a pure wealth transfer. A
defrauded honest agent accumulates one victimisation m, and one report r is filed against the
cheater. At the step end, {eq('conv')} conversion is irreversible and the current step is
still settled as honest. Exit follows two rules: {eq('exit')} Eviction is active only under
the institutional switch E = 1, with q = 3; bankruptcy is always active. The two labels can
trigger simultaneously and are recorded as a "both" flag. An evicted agent keeps the wealth
he holds at exit; a bankrupt agent's wealth is zeroed. Exit makes an agent inactive but is
not by itself a death event.""")

add("")
add("### Survival cost and death accounting")
add("")
add(f"""A per-step survival cost c > 0 is charged to every active agent after trading and
before the exit checks; the baseline sets c = 0. Two death causes are distinguished: a trade
death (cause 0) if trading has driven wealth to zero, and a cost death (cause 1) if the
survival cost does so. Agents with positive wealth are recorded as alive even after eviction.
Table 7.1 lists the calibration and Table 7.2 gives the full output dictionary, including
the macro statistics, individual state variables and activity flags recorded by the
simulator.""")

add("")
add(table_md(T["t71"], ["Parameter", "Symbol", "Value", "Role"],
             "Table 7.1. Calibration and experimental design.",
             "Values are fixed across all runs unless a robustness cell states otherwise. "
             "The initial cheater share takes eight values from 0.05 to 0.40; the conversion threshold p takes 2, 3 and 4."))
add("")
add(table_md(T["t72"], ["Block", "Variable", "Definition"],
             "Table 7.2. Output variables recorded by the simulator.",
             "Market exit (bankruptcy, eviction, both) and wealth-exhaustion death are separate concepts; "
             "an evicted agent remains alive while his wealth is positive."))

add("")
add("## 7.1 Experimental design and descriptive evidence")
add("")
add(f"""Two institutional arms are compared. Under E = 0 the report–eviction rule is
disabled; under E = 1 a cheater is expelled once r reaches q = 3. Bankruptcy operates in both
arms. Predetermined controls are the initial cheater share $\\rho$ (eight values), the
conversion threshold p (three values), trading capacity a = 3 and the random seed
({K['n_seeds']} seeds per cell). Common random numbers are used across arms: the same seed
initialises the same initial identities and the same random stream, although the trading
paths diverge once the institution removes agents. Each run is tracked for the full fixed
window, so welfare is measured on a common horizon. Market collapse is the first step at
which active honest agents fall to 10% of $H_0$; runs that never collapse are right
censored and the outcome is {eq('y')}.""")
add("")
add(f"""Table 7.3 reports the raw contrast. Restricted survival rises from
{n2(K['surv0'])} to {n2(K['surv1'])} steps, cooperative trades from {n2(K['coop0'])} to
{n2(K['coop1'])}, and cumulative net benefit from {n2(K['wt0'])} to {n2(K['wt1'])}.
These are unconditional differences; the regressions below condition on the experimental
controls.""")
add("")
add(table_md(T["t73"], ["Variable", "E = 0 mean", "(s.d.)", "E = 1 mean", "(s.d.)", "Difference"],
             "Table 7.3. Descriptive statistics by institutional arm.",
             "Means over 720 runs per arm (main sample). Standard deviations in parentheses. "
             "Difference is the E = 1 mean minus the E = 0 mean."))

add("")
add("## 7.2 Mechanism outcomes")
add("")
add(f"""Following the task specification, the three mechanism results are Fraud (the number
of honest–cheater transactions), Conversion (the share of initially honest agents who
become cheaters) and Cooperation (the number of honest–honest transactions). Each is
regressed separately on the institutional switch and predetermined controls, with
interactions between the switch and $\\rho$ and between the switch and the p dummies:
{eq('mech')} where $X_i$ contains $\\rho_i$ and the p dummies. Standard errors
are clustered at the configuration × institution cell, and the confidence interval for
$\\beta_E$ comes from a cluster bootstrap over the same cells. Because all three
outcomes are realised after treatment, these are reduced-form effects rather than
structural behavioural parameters.""")
add("")
add(f"""Table 7.4 gives the estimates. Evaluated at $\\rho = 0$ and p = 2, expulsion changes
fraud by {n2(K['beta_fraud'])} trades (s.e. {n2(K['se_fraud'])}), the conversion share by
{n3(K['beta_conv'])} and cooperation by {n2(K['beta_coop'])} trades. The signs are exactly
those predicted by a protection-of-cooperation mechanism: fewer fraudulent encounters,
slower conversion and more cooperative exchange. The interaction terms have the opposite
sign in every column ({n2(K['inter_fraud'])}, {n3(K['inter_conv'])} and
{n2(K['inter_coop'])}), so each effect attenuates as the initial cheater share rises; the
implied zero crossings lie at $\\rho \\approx {n2(rho_f)}$, {n2(rho_c)} and {n2(rho_k)}
respectively. Figure 7.1 shows the same attenuation directly.""")
add("")
add(table_md(T["t74"], ["Variable", "Fraud", "Conversion", "Cooperation"],
             "Table 7.4. Mechanism outcome regressions.",
             "Each column is a separate OLS regression. Cluster-robust standard errors in parentheses, "
             "clustered on the rho x p x E cell (48 cells); *** p < 0.01, ** p < 0.05, * p < 0.10 "
             "based on the normal approximation. The 95% CI for E resamples whole cells (1,200 replications)."))
add("")
add(fig_md("fig7_1_mechanism_by_rho",
           "Figure 7.1. Mechanism outcomes across the initial cheater share, averaged over p and seeds. "
           "The protective effect of expulsion concentrates at low rho and vanishes near rho = 0.26."))
add("")
add(fig_md("fig7_2_market_dynamics",
           "Figure 7.2. Market dynamics under each institution, averaged over two rho cells and 30 seeds. "
           "Without expulsion the honest layer disappears within roughly ten steps; with expulsion it stabilises."))
add("")
add(fig_md("fig7_3_trade_composition",
           "Figure 7.3. Trade composition in a representative run (rho = 0.10, p = 3, seed = 0). "
           "Shares are carried forward in steps with no trade."))
add("")
add(f"""The composition evidence matters because raw trade counts are mechanically scaled by
market lifetime: treated markets survive {n2(K['surv1'])} steps on average against
{n2(K['surv0'])} for controls, so any cumulative count tends to rise with E even if
per-trade behaviour is unchanged. Re-estimating the mechanism equations on per-trade shares
isolates the structural change: the fraud share falls by {n3(abs(K['beta_fraud_share']))}
and the cooperation share rises by {n3(K['beta_coop_share'])} (Table 7.8). Expulsion therefore
does more than keep the market open longer; it shifts the mix of transactions away from
zero-sum fraud and negative-sum cheater collusion toward positive-sum cooperation. This is
the sense in which the results are consistent with the protection-of-cooperation mechanism,
and it is also why the seizure of a cheater's future trading opportunities, rather than the
recovery of transferred wealth, is the operative channel.""")

add("")
add("## 7.3 Why these results are not a mediation analysis")
add("")
add(f"""The collapse equation relates restricted survival to the institutional switch and
predetermined controls: {eq('collapse1')} A tempting but invalid extension adds the three
mechanism outcomes as if they were mediators: {eq('collapse2')} The coefficient on E in the
second equation is not a direct effect, and its difference from the first is not an indirect
effect. Table 7.5 reports both specifications.""")
add("")
add(f"""The baseline treatment coefficient is {n2(K['base_beta'])} survival steps. Adding
Fraud, Conversion and Cooperation reduces it to {n2(K['naive_beta'])}; the apparent
"explained share" {eq('share')} is {n2(100*K['apparent_share'])}%. Figure 7.5 plots the
attenuation and the mechanical correlation between realised fraud and survival that drives
it; the coefficient on Fraud in specification (2) is positive even though expulsion reduces
fraud, which is itself a symptom of conditioning on a cumulative post-treatment count.
Three problems make this number uninterpretable as mediation. First, all three variables
are post-treatment: conditioning on them blocks part of the treatment path and introduces
selection on outcomes that the institution itself generated. Second, they share a common
time scale with survival, so longer-lived markets accumulate more of everything; the
regression partly divides one consequence of treatment by another. Third, conversion and
eviction are simultaneous — an expelled cheater both stops defrauding and ceases to be a
future conversion risk — and expulsion changes the composition of the active population, so
the comparison is not between like agents. A causal mediation claim would require an
intervention that shifts one mediator while holding the matching process and the other
mediators fixed, together with sequential ignorability; a two-arm institutional experiment
provides neither. We therefore report three reduced-form mechanism effects and no mediated
share.""")
add("")
add(table_md(T["t75"], ["Specification", "E coefficient (s.e.)", "95% CI", "Fraud /1e3",
                        "Conversion", "Coop. /1e3", "R2", "N"],
             "Table 7.5. Collapse equation with and without post-treatment controls.",
             "Dependent variable: restricted survival steps Y = min(Tcollapse, 200). All specifications "
             "include rho, p dummies and their interactions with E. Post-treatment controls are divided "
             "by 1,000 where indicated. Standard errors clustered on the rho x p x E cell; "
             "95% CI from a cluster bootstrap."))
add("")
add(fig_md("fig7_5_bad_control",
           "Figure 7.5. Post-treatment bias diagnostic. Panel (a): attenuation of the treatment "
           "coefficient with 95% cluster-bootstrap intervals. Panel (b): survival and realised fraud, "
           "with group-specific linear fits."))

add("")
add("## 7.4 Transaction social net benefit and welfare")
add("")
add(f"""For a transaction between i and j, the social net benefit is the sum of the two
side payoffs: {eq('sij')} By the payoff structure of the model, {eq('srules')} The last sum is
zero because fraud is a pure wealth transfer, so no positive social value is imputed to it.
Welfare is accumulated over the fixed observation window: {eq('wt')} where
$A_t$ is the set of pairs actually settled in step t. Every run is tracked for the
full T = 200 steps; after collapse, agents that remain active continue to trade, and steps
with no trade contribute zero. The fixed horizon keeps $W_T$ comparable across
markets with different survival times.""")
add("")
add(f"""When a loss exceeds an agent's balance, the realised change in wealth is truncated at
zero. We therefore report $W_T$ on the realised basis, {eq('sijreal')} and give the
theoretical sum and the truncation gap alongside it. This choice keeps the wealth accounting
identity exact: {eq('acct')} The maximum absolute accounting error across the main sample is
{n3(K["acct_gap"])}.""")
add("")
add(table_md(T["t76a"], ["Type", "Payoff i", "Payoff j", "S(ij)", "Interpretation"],
             "Table 7.6a. Social net benefit by transaction type.",
             "H-H is positive-sum, C-C is negative-sum, and H-C is a pure transfer."))
add("")
add(table_md(T["t76"], ["Outcome", "E = 0", "E = 1", "Difference"],
             "Table 7.6. Welfare and market outcomes over the fixed horizon.",
             "Means over the main sample. W_T is the realised cumulative social net benefit; "
             "cooperative traded value is 2 g_HH times the number of H-H trades; "
             "end-period total wealth includes wealth retained by evicted agents."))
add("")
add(f"""Table 7.6 shows that the welfare gain is a compositional result. Without expulsion
the H–H contribution of {n2(K['wthh0'])} is more than offset by the C–C
contribution of {n2(K['wtcc0'])}, leaving $W_T = {n2(K['wt0'])}$; end-period wealth
falls to {n2(K['endw0'])} from an initial stock of 4,000. With expulsion the H–H
contribution rises to {n2(K['wthh1'])} while the C–C loss shrinks to
{n2(K['wtcc1'])}, giving $W_T = {n2(K['wt1'])}$ and end-period wealth of
{n2(K['endw1'])}. Cooperative volume rises from {n2(K['coop0'])} to {n2(K['coop1'])}
trades, and restricted survival from {n2(K['surv0'])} to {n2(K['surv1'])} steps. Figure 7.4
plots the cumulative path and the decomposition. Because H–H payoffs are exogenous
positive-sum injections, $W_T$ is a model-implied surplus index rather than a measure
of real resources; it should be read together with cooperative volume and survival, not
compared across calibrations as a welfare level.""")
add("")
add(fig_md("fig7_4_welfare",
           "Figure 7.4. Cumulative social net benefit and its decomposition by transaction type. "
           "The treated market accumulates positive surplus because cooperative trade persists."))

add("")
add("## 7.5 Survival cost, market exit and wealth-exhaustion death")
add("")
add(f"""A per-step survival cost c requires an explicit interpretation before it enters
welfare. If c represents a real resource consumed by keeping an agent active in the market,
it is a resource cost that never appears in any transaction payoff, and the appropriate
object is {eq('wtr')} where $I_t$ is the set of active agents in step t. If c is
instead an accounting normalisation or a transfer between accounts, it is not a social cost
and must not be subtracted from $W_T$. Table 7.7 reports both objects separately.
The distinction is substantive: under the resource interpretation the same transaction path
can generate a smaller welfare number, while under the accounting interpretation welfare is
unchanged and only the distribution of balances moves.""")
add("")
add(f"""At c = 0.30 and E = 1, realised transaction welfare is {n2(K['cost_c30_wt1'])}
and resource-adjusted welfare is {n2(K['cost_c30_adj1'])}; {n2(K['cost_c30_costdeath1'])}
agents die of the survival cost against {n2(K['cost_c30_tradedeath1'])} trade deaths, so cost
deaths are a distinct, small channel in this calibration. At c = 0 no cost death is possible
by construction. Figure 7.6 shows how both welfare measures and the death composition move
with c.""")
add("")
add(f"""Market exit and wealth-exhaustion death are reported in separate columns. In the
c = 0, E = 1 cell there are {n2(K['cost_c0_evicted1'])} eviction labels,
{n2(K['cost_c0_bank1'])} bankruptcy labels and {n2(K['cost_c0_both1'])} simultaneous labels,
while {n2(K['cost_c0_alive1'])} agents are alive and {n2(K['cost_c0_death1'])} are dead.
Every bankruptcy in this calibration is a wealth-exhaustion death, so the bankruptcy and
death counters coincide by construction; expulsion, by contrast, removes agents whose wealth
stays positive, which is why the number alive exceeds the number still active. The "both"
flag is empty here because a reported cheater is expelled before his balance is exhausted.
Separating the two concepts is therefore not bookkeeping: with c > 0, cost deaths appear as
a channel that leaves transaction welfare unchanged but reduces end-period wealth.""")
add("")
add(table_md(T["t77"], ["c", "E", "W_T", "Cost c", "Adj. W_T", "End wealth", "Survival",
                        "Trade deaths", "Cost deaths", "Bankruptcy", "Eviction", "Both",
                        "Exits", "Alive", "Evicted wealth"],
             "Table 7.7. Survival cost, resource-adjusted welfare and the exit/death decomposition.",
             "Subsample with rho in {0.10, 0.25}, p = 3, a = 3, 20 seeds per cell. "
             "'Cost c' is the realised aggregate survival cost; 'Adj. W_T' subtracts it from W_T. "
             "Trade deaths and cost deaths correspond to death causes 0 and 1."))
add("")
add(fig_md("fig7_6_survival_cost",
           "Figure 7.6. Survival cost, resource-adjusted welfare, death composition and surviving agents. "
           "Cost deaths emerge only when c > 0; eviction removes agents without killing them."))

add("")
add("## 7.6 Robustness")
add("")
add(f"""Table 7.8 re-estimates the three mechanism equations under alternative inference
and measurement choices: configuration fixed effects, clustering on the seed or on the
configuration × seed block, trading capacities a = 2 and a = 4, per-trade composition
outcomes instead of raw counts, and a conversion share truncated to [0.02, 0.98] to
respect its bounded support. The sign and significance of the treatment coefficient are
unchanged in every column. Clustering on the seed gives noticeably smaller intervals than
clustering on the cell, because common random numbers induce negative within-seed residual
correlation; the cell-clustered specification is therefore the conservative baseline. The
per-trade specification is the most informative about magnitude, because it removes the
mechanical dependence of cumulative counts on market lifetime.""")
add("")
add(table_md(T["t78"], ["Specification", "Fraud", "Conversion", "Cooperation", "N"],
             "Table 7.8. Robustness of the mechanism estimates.",
             "Cell-clustered standard errors in parentheses; trading-capacity rows cluster on the seed "
             "(20 clusters). In the per-trade composition row Conversion is already a share and is "
             "reported as n.a. *** p < 0.01, ** p < 0.05, * p < 0.10."))

add("")
add("## 7.7 Conclusion and limits")
add("")
add("""Three conclusions follow. First, the institutional switch produces the joint
pattern predicted by the protection-of-cooperation mechanism: less fraud, slower conversion
and more cooperation, with all three effects concentrated in markets with a low initial
cheater share. Second, those variables are consequences of treatment, not mediators that can
be added to the collapse equation; the apparent attenuation of the treatment coefficient is
a post-treatment bias diagnostic, not a decomposition of the total effect. Third, the
welfare gain comes from shifting the composition of trade toward its positive-sum component,
and it must be reported together with cooperative volume, end-period wealth and survival on
a fixed horizon; a survival cost, when interpreted as a real resource, belongs in a separate
resource-adjusted measure.""")
add("")
add("""The model deliberately omits false reports, enforcement costs, appeals and re-entry
by expelled cheaters. All estimates identify effects inside this simulated market and should
not be extrapolated to real platform policy without additional evidence. The numbers in this
report are generated from the run-level and transaction-level files listed below, and every
figure and table is reproduced as a separate file alongside the report.""")

add("")
add("## Appendix. Reproducibility")
add("")
add("""Simulation: code/simulate.py. Analysis: code/analysis_tables.py,
code/analysis_figures.py, code/render_formulas.js, code/build_report.py,
code/build_md_docx.py. Data:
data/run_level.csv (1,840 runs), data/timeseries.csv (step-level series),
data/event_ledger_baseline.csv (transaction ledger for the representative pair),
data/individual_final_baseline.csv (agent final states), data/params.json and
data/analysis.json. Figures: figures/*.svg and figures/*.png. Tables: tables/*.csv and
tables/tables_index.html.""")

md = "\n\n".join(x for x in M if x != "") + "\n"
md_path = os.path.join(OUT, "report.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md)
print("wrote report.md", len(md), "chars")

# ------------------------------ docx via pandoc ------------------------------
import pypandoc
os.chdir(OUT)
pypandoc.convert_file(
    "report.md", "docx", outputfile="report.docx",
    extra_args=["--resource-path=" + OUT])
print("wrote report.docx via pandoc")

# ------------------------------ house style pass ------------------------------
from docx import Document
from docx.shared import RGBColor

doc = Document(os.path.join(OUT, "report.docx"))

# style-level: black, no bold, no italic
for st in doc.styles:
    try:
        f = st.font
    except Exception:
        continue
    if f is None:
        continue
    try:
        f.color.rgb = RGBColor(0, 0, 0)
    except Exception:
        pass
    try:
        f.bold = False
    except Exception:
        pass
    try:
        f.italic = False
    except Exception:
        pass

# ------------------------------ typography pass (match PDF) ------------------------------
# PDF print metrics: A4, margins 17mm/15mm, Times New Roman, body 10.5pt
# justified line 1.45, h1 20pt, h2 14pt, h3 12pt, table captions 10.5pt,
# notes 9.5pt, figure captions 9.8pt, tables 9.5pt (wide 8.5pt), figures full width.
import re
from docx.shared import Pt, Cm, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BLACK = RGBColor(0, 0, 0)
FONT = "Times New Roman"

def set_borders(tbl):
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement('w:' + edge)
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), '333333')
        borders.append(el)
    old = tblPr.find(qn('w:tblBorders'))
    if old is not None:
        tblPr.remove(old)
    tblPr.append(borders)

def style_font(st, size=None, name=FONT):
    f = st.font
    f.name = name
    f.color.rgb = BLACK
    f.bold = False
    f.italic = False
    if size is not None:
        f.size = Pt(size)
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts')
        rpr.insert(0, rf)
    for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
        rf.set(qn(attr), name)

def by_name(name):
    try:
        return doc.styles[name]
    except KeyError:
        return None

BODY_STYLES = {'BodyText', 'FirstParagraph', 'Compact'}
CAPTION_RE = re.compile(r'^Table 7\.\d+a?\. [A-Z]')

# page geometry: A4, 17mm top/bottom, 15mm left/right -> 18cm text width
for sec in doc.sections:
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Mm(17)
    sec.left_margin = sec.right_margin = Mm(15)

# style-level fonts, sizes and spacing
norm = by_name('Normal')
if norm is not None:
    style_font(norm, 10.5)
    pf = norm.paragraph_format
    pf.line_spacing = 1.45
    pf.space_after = Pt(8)
    pf.space_before = Pt(0)

for sname in ('BodyText', 'FirstParagraph', 'Compact'):
    st = by_name(sname)
    if st is None:
        continue
    style_font(st, 10.5)
    st.paragraph_format.line_spacing = 1.45
    st.paragraph_format.space_after = Pt(8)
    st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

H = {'Heading1': (20, 0, 8), 'Heading2': (14, 18, 6), 'Heading3': (12, 12, 4)}
for sname, (size, before, after) in H.items():
    st = by_name(sname)
    if st is None:
        continue
    style_font(st, size)
    pf = st.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    pf.keep_with_next = True
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT

cap = by_name('ImageCaption')
if cap is not None:
    style_font(cap, 9.8)
    cap.paragraph_format.space_after = Pt(14)
    cap.paragraph_format.line_spacing = 1.35
    cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

# run-level enforcement: colour, weights, fonts; contextual sizes for
# table cells, table captions and notes
def style_runs(paras, size=None):
    for p in paras:
        for r in p.runs:
            r.font.color.rgb = BLACK
            r.font.bold = False
            r.font.italic = False
            r.font.name = FONT
            if size is not None:
                r.font.size = Pt(size)
            rpr = r._element.get_or_add_rPr()
            rf = rpr.find(qn('w:rFonts'))
            if rf is None:
                rf = OxmlElement('w:rFonts')
                rpr.insert(0, rf)
            for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
                rf.set(qn(attr), FONT)

for tbl in doc.tables:
    size = 8.5 if len(tbl.columns) >= 12 else 9.5
    for row in tbl.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.line_spacing = 1.15
            style_runs(cell.paragraphs, size=size)
    set_borders(tbl)

for p in doc.paragraphs:
    t = p.text.strip()
    if CAPTION_RE.match(t):
        style_runs([p], size=10.5)
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
    elif t.startswith('Note: '):
        style_runs([p], size=9.5)
        p.paragraph_format.space_after = Pt(14)
        p.paragraph_format.line_spacing = 1.35
    else:
        style_runs([p])

# figures: full text width (18 cm), aspect preserved
TEXT_W = Cm(18)
for shp in doc.inline_shapes:
    w, h = shp.width, shp.height
    shp.width = TEXT_W
    shp.height = int(h * TEXT_W / w)

doc.save(os.path.join(OUT, "report.docx"))
print("typography applied: A4 17/15mm, Times, body 10.5pt justified 1.45, "
      "h1 20 / h2 14 / h3 12pt, tables 9.5/8.5pt, captions 10.5/9.8/9.5pt, figures 18cm")
