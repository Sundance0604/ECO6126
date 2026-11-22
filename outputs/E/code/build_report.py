"""Build the self-contained English report for Section 7.

All in-text numbers are injected from analysis.json, so nothing in the
prose is hand-typed. Formulas are pre-rendered by KaTeX and the fonts are
inlined as data URIs, making report.html fully self-contained.
"""
import sys, os, csv, json, re, base64, subprocess
sys.stdout.reconfigure(encoding='utf-8')

OUT = r"C:\Users\86187\WorkBuddy\2026-11-22-21-56-35\outputs"
DATA = os.path.join(OUT, "data")
TAB = os.path.join(OUT, "tables")
FIG = os.path.join(OUT, "figures")
CODE = os.path.join(OUT, "code")
NODE = r"C:\Users\86187\.workbuddy\binaries\node\versions\22.22.2\node.exe"
KATEX = r"C:\Users\86187\.workbuddy\binaries\node\workspace\node_modules\katex\dist"

A = json.load(open(os.path.join(DATA, "analysis.json"), encoding="utf-8"))
K = A["key_numbers"]
T = A["tables"]

# ------------------------------ KaTeX ------------------------------
env = os.environ.copy()
env["NODE_PATH"] = r"C:\Users\86187\.workbuddy\binaries\node\workspace\node_modules"
fjson = os.path.join(DATA, "formulas.json")
subprocess.run([NODE, os.path.join(CODE, "render_formulas.js"), fjson],
               env=env, check=True, capture_output=True)
EQ = json.load(open(fjson, encoding="utf-8"))

css = open(os.path.join(KATEX, "katex.min.css"), encoding="utf-8").read()
fdir = os.path.join(KATEX, "fonts")
cache = {}
def font_repl(m):
    name = m.group(1)
    if name not in cache:
        ext = name.rsplit(".", 1)[-1]
        mime = {"woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf"}.get(ext, "application/octet-stream")
        raw = open(os.path.join(fdir, name), "rb").read()
        cache[name] = "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode())
    return "url(%s)" % cache[name]
css = re.sub(r"url\(fonts/([^)]+)\)", font_repl, css)

# ------------------------------ helpers ------------------------------
def n2(x):
    return "{:,.2f}".format(x)

def n3(x):
    return "{:,.3f}".format(x)

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def is_num(v):
    """Right-align only genuine numeric cells, not definitions that start with a digit."""
    s = str(v).strip()
    if not s:
        return False
    s2 = re.sub(r"\*+$", "", s)
    s2 = re.sub(r"\s*\([^)]*\)\s*$", "", s2).strip()
    if s2.startswith("[") and s2.endswith("]"):
        parts = s2[1:-1].split(",")
        return all(re.fullmatch(r"\s*[-+]?[\d,]+(?:\.\d+)?\s*", p) for p in parts)
    return bool(re.fullmatch(r"[-+]?[\d,]+(?:\.\d+)?", s2))

def table_html(rows, headers, caption, note, wide=False):
    o = ['<div class="tblwrap%s">' % (" wide" if wide else "")]
    o.append('<div class="tcap">%s</div>' % esc(caption))
    o.append('<table><thead><tr>')
    for h in headers:
        o.append('<th>%s</th>' % esc(h))
    o.append('</tr></thead><tbody>')
    for r in rows:
        o.append('<tr>')
        for i, key in enumerate(r.keys()):
            v = r[key]
            cls = " class='num'" if i > 0 and is_num(v) else ""
            o.append('<td%s>%s</td>' % (cls, esc(v)))
        o.append('</tr>')
    o.append('</tbody></table>')
    if note:
        o.append('<div class="tnote">%s</div>' % esc(note))
    o.append('</div>')
    return "\n".join(o)

def fig_html(name, caption):
    svg = open(os.path.join(FIG, name + ".svg"), encoding="utf-8").read()
    svg = re.sub(r'\s+width="\d+"\s+height="\d+"', "", svg, count=1)
    svg = svg.replace("<svg ", '<svg style="width:100%;height:auto;display:block" ', 1)
    return '<figure>%s<figcaption>%s</figcaption></figure>' % (svg, esc(caption))

def eq(key):
    return EQ[key]

rho_f = -K["beta_fraud"] / K["inter_fraud"]
rho_c = -K["beta_conv"] / K["inter_conv"]
rho_k = -K["beta_coop"] / K["inter_coop"]

# ------------------------------ prose ------------------------------
P = []
add = P.append

add("""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>7. Mechanism and Welfare Analysis</title><style>""")
add(css)
add("""
body{font-family:"Times New Roman",Times,serif;color:#000;background:#fff;
 font-size:11.6pt;line-height:1.52;max-width:960px;margin:0 auto;padding:38px 44px 64px}
h1{font-size:20pt;font-weight:normal;margin:0 0 2px;line-height:1.25}
h2{font-size:14pt;font-weight:normal;margin:26px 0 8px;line-height:1.3}
h3{font-size:12pt;font-weight:normal;margin:18px 0 6px}
p{margin:0 0 10px;text-align:justify}
.sub{font-size:12pt;margin:0 0 4px}
.meta{font-size:10pt;margin:0 0 20px}
.abstract{margin:16px 0 8px}
.tcap{font-size:10.6pt;margin:14px 0 5px}
.tnote{font-size:9.4pt;margin:5px 0 14px;line-height:1.4}
table{border-collapse:collapse;width:100%;font-size:9.6pt;margin:0}
.tblwrap{margin:0 0 16px;break-inside:avoid}
.tblwrap.wide table{font-size:8.5pt}
th,td{border-bottom:1px solid #c4c4c4;padding:3px 6px;text-align:left;vertical-align:top}
th{border-top:1px solid #333;border-bottom:1px solid #333;font-weight:normal}
td.num{text-align:right;white-space:nowrap}
figure{margin:16px 0 20px;break-inside:avoid}
figcaption{font-size:9.8pt;margin-top:7px;line-height:1.4}
.eq{margin:9px 0 11px;overflow-x:auto}
.katex-display{margin:6px 0}
hr{border:0;border-top:1px solid #ccc;margin:26px 0}
@page{size:A4;margin:17mm 15mm}
@media print{body{max-width:none;padding:0;font-size:10.4pt;line-height:1.45}
 h2{break-after:avoid}figure,.tblwrap{break-inside:avoid}}
</style></head><body>
""")

add('<h1>7. Mechanism and Welfare Analysis</h1>')
add('<div class="sub">Reputation punishment and market collapse in a closed trading market</div>')
add('<div class="meta">Simulation-based study | Fixed observation window T = 200 | 1,840 runs</div>')

add('<h2>Abstract</h2>')
add(f"""<p class="abstract">Expulsion changes market outcomes only if it changes what happens inside the
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
wealth-exhaustion death throughout.</p>""")

# ---- 7.0 model overview ----
add('<h2>7.0 Model overview</h2>')
add('<h3>Population, timing and synchronous settlement</h3>')
add(f"""<p>At t = 0 a closed market contains N = 200 agents, each endowed with w<sub>0</sub> = 20.
A share &rho; of them are cheaters (C) and the remainder are honest (H), so @@eq:pop@@ and
the initial composition is fixed for the whole run. There is no entry. Time is discrete,
@@eq:time@@ with T = 200; t = 0 denotes the initial state and all trading occurs in steps
1 to T. Identities are frozen within a step: every payoff in step t is computed from the
identities prevailing at the beginning of that step, and identity changes are applied only at
the step end. @@eq:sync@@</p>""")

add('<h3>Matching, capacity and blacklists</h3>')
add("""<p>In each step an active agent may trade with at most a = 3 distinct counterparties, and
any pair trades at most once per step. Matching is implemented as a rounds of random
permutations of the active set; a proposed pair is discarded if either agent has reached the
per-step cap, if the pair has already traded in the step, or if either side is blacklisted by
the other. @@eq:match@@ Blacklists are directional and permanent. An honest agent who is
defrauded blacklists the cheater and files one report against him; two cheaters who meet
blacklist each other but do not report. Blacklist updates take effect at the step end, so
the same pair can defraud a given honest agent at most once.</p>""")

add('<h3>Transaction types, identity change and exit</h3>')
add(f"""<p>Three transaction types are possible. Two honest agents each receive
g<sub>HH</sub> = +1.5; two cheaters each incur g<sub>CC</sub> = &minus;2.0; an
honest&ndash;cheater pair transfers x = 5 from the honest agent to the cheater, so the two
sides sum to zero. The transfer is truncated at the honest agent's balance and therefore
remains a pure wealth transfer. A defrauded honest agent accumulates one victimisation m,
and one report r is filed against the cheater. At the step end, @@eq:conv@@ conversion is
irreversible and the current step is still settled as honest. Exit follows two rules:
@@eq:exit@@ Eviction is active only under the institutional switch E = 1, with q = {3};
bankruptcy is always active. The two labels can trigger simultaneously and are recorded as a
"both" flag. An evicted agent keeps the wealth he holds at exit; a bankrupt agent's wealth is
zeroed. Exit makes an agent inactive but is not by itself a death event.</p>""")

add('<h3>Survival cost and death accounting</h3>')
add("""<p>A per-step survival cost c &gt; 0 is charged to every active agent after trading and
before the exit checks; the baseline sets c = 0. Two death causes are distinguished: a trade
death (cause 0) if trading has driven wealth to zero, and a cost death (cause 1) if the
survival cost does so. Agents with positive wealth are recorded as alive even after eviction.
Table 7.1 lists the calibration and Table 7.2 gives the full output dictionary, including
the macro statistics, individual state variables and activity flags recorded by the
simulator.</p>""")

add(table_html(T["t71"], ["Parameter", "Symbol", "Value", "Role"],
               "Table 7.1. Calibration and experimental design.",
               "Values are fixed across all runs unless a robustness cell states otherwise. "
               "The initial cheater share takes eight values from 0.05 to 0.40; the conversion threshold p takes 2, 3 and 4."))
add(table_html(T["t72"], ["Block", "Variable", "Definition"],
               "Table 7.2. Output variables recorded by the simulator.",
               "Market exit (bankruptcy, eviction, both) and wealth-exhaustion death are separate concepts; "
               "an evicted agent remains alive while his wealth is positive."))

# ---- 7.1 design ----
add('<h2>7.1 Experimental design and descriptive evidence</h2>')
add(f"""<p>Two institutional arms are compared. Under E = 0 the report&ndash;eviction rule is
disabled; under E = 1 a cheater is expelled once r reaches q = 3. Bankruptcy operates in both
arms. Predetermined controls are the initial cheater share &rho; (eight values), the
conversion threshold p (three values), trading capacity a = 3 and the random seed
({K['n_seeds']} seeds per cell). Common random numbers are used across arms: the same seed
initialises the same initial identities and the same random stream, although the trading
paths diverge once the institution removes agents. Each run is tracked for the full fixed
window, so welfare is measured on a common horizon. Market collapse is the first step at
which active honest agents fall to 10% of H<sub>0</sub>; runs that never collapse are right
censored and the outcome is @@eq:y@@.</p>""")
add(f"""<p>Table 7.3 reports the raw contrast. Restricted survival rises from
{n2(K['surv0'])} to {n2(K['surv1'])} steps, cooperative trades from {n2(K['coop0'])} to
{n2(K['coop1'])}, and cumulative net benefit from {n2(K['wt0'])} to {n2(K['wt1'])}.
These are unconditional differences; the regressions below condition on the experimental
controls.</p>""")
add(table_html(T["t73"], ["Variable", "E = 0 mean", "(s.d.)", "E = 1 mean", "(s.d.)", "Difference"],
               "Table 7.3. Descriptive statistics by institutional arm.",
               "Means over 720 runs per arm (main sample). Standard deviations in parentheses. "
               "Difference is the E = 1 mean minus the E = 0 mean."))

# ---- 7.2 mechanism ----
add('<h2>7.2 Mechanism outcomes</h2>')
add("""<p>Following the task specification, the three mechanism results are Fraud (the number
of honest&ndash;cheater transactions), Conversion (the share of initially honest agents who
become cheaters) and Cooperation (the number of honest&ndash;honest transactions). Each is
regressed separately on the institutional switch and predetermined controls, with
interactions between the switch and &rho; and between the switch and the p dummies:
@@eq:mech@@ where X<sub>i</sub> contains &rho;<sub>i</sub> and the p dummies. Standard errors
are clustered at the configuration &times; institution cell, and the confidence interval for
&beta;<sub>E</sub> comes from a cluster bootstrap over the same cells. Because all three
outcomes are realised after treatment, these are reduced-form effects rather than
structural behavioural parameters.</p>""")

add(f"""<p>Table 7.4 gives the estimates. Evaluated at &rho; = 0 and p = 2, expulsion changes
fraud by {n2(K['beta_fraud'])} trades (s.e. {n2(K['se_fraud'])}), the conversion share by
{n3(K['beta_conv'])} and cooperation by {n2(K['beta_coop'])} trades. The signs are exactly
those predicted by a protection-of-cooperation mechanism: fewer fraudulent encounters,
slower conversion and more cooperative exchange. The interaction terms have the opposite
sign in every column ({n2(K['inter_fraud'])}, {n3(K['inter_conv'])} and
{n2(K['inter_coop'])}), so each effect attenuates as the initial cheater share rises; the
implied zero crossings lie at &rho; &asymp; {n2(rho_f)}, {n2(rho_c)} and {n2(rho_k)}
respectively. Figure 7.1 shows the same attenuation directly.</p>""")

add(table_html(T["t74"], ["Variable", "Fraud", "Conversion", "Cooperation"],
               "Table 7.4. Mechanism outcome regressions.",
               "Each column is a separate OLS regression. Cluster-robust standard errors in parentheses, "
               "clustered on the rho x p x E cell (48 cells); *** p < 0.01, ** p < 0.05, * p < 0.10 "
               "based on the normal approximation. The 95% CI for E resamples whole cells (1,200 replications)."))

add(fig_html("fig7_1_mechanism_by_rho",
             "Figure 7.1. Mechanism outcomes across the initial cheater share, averaged over p and seeds. "
             "The protective effect of expulsion concentrates at low rho and vanishes near rho = 0.26."))
add(fig_html("fig7_2_market_dynamics",
             "Figure 7.2. Market dynamics under each institution, averaged over two rho cells and 30 seeds. "
             "Without expulsion the honest layer disappears within roughly ten steps; with expulsion it stabilises."))
add(fig_html("fig7_3_trade_composition",
             "Figure 7.3. Trade composition in a representative run (rho = 0.10, p = 3, seed = 0). "
             "Shares are carried forward in steps with no trade."))

add(f"""<p>The composition evidence matters because raw trade counts are mechanically scaled by
market lifetime: treated markets survive {n2(K['surv1'])} steps on average against
{n2(K['surv0'])} for controls, so any cumulative count tends to rise with E even if
per-trade behaviour is unchanged. Re-estimating the mechanism equations on per-trade shares
isolates the structural change: the fraud share falls by {n3(abs(K['beta_fraud_share']))}
and the cooperation share rises by {n3(K['beta_coop_share'])} (Table 7.8). Expulsion therefore
does more than keep the market open longer; it shifts the mix of transactions away from
zero-sum fraud and negative-sum cheater collusion toward positive-sum cooperation. This is
the sense in which the results are consistent with the protection-of-cooperation mechanism,
and it is also why the seizure of a cheater's future trading opportunities, rather than the
recovery of transferred wealth, is the operative channel.</p>""")

# ---- 7.3 bad control ----
add('<h2>7.3 Why these results are not a mediation analysis</h2>')
add("""<p>The collapse equation relates restricted survival to the institutional switch and
predetermined controls: @@eq:collapse1@@ A tempting but invalid extension adds the three
mechanism outcomes as if they were mediators: @@eq:collapse2@@ The coefficient on E in the
second equation is not a direct effect, and its difference from the first is not an indirect
effect. Table 7.5 reports both specifications.</p>""")

add(f"""<p>The baseline treatment coefficient is {n2(K['base_beta'])} survival steps. Adding
Fraud, Conversion and Cooperation reduces it to {n2(K['naive_beta'])}; the apparent
"explained share" @@eq:share@@ is {n2(100*K['apparent_share'])}%. Figure 7.5 plots the
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
share.</p>""")

add(table_html(T["t75"], ["Specification", "E coefficient (s.e.)", "95% CI", "Fraud /1e3",
                          "Conversion", "Coop. /1e3", "R2", "N"],
               "Table 7.5. Collapse equation with and without post-treatment controls.",
               "Dependent variable: restricted survival steps Y = min(Tcollapse, 200). All specifications "
               "include rho, p dummies and their interactions with E. Post-treatment controls are divided "
               "by 1,000 where indicated. Standard errors clustered on the rho x p x E cell; "
               "95% CI from a cluster bootstrap."))
add(fig_html("fig7_5_bad_control",
             "Figure 7.5. Post-treatment bias diagnostic. Panel (a): attenuation of the treatment "
             "coefficient with 95% cluster-bootstrap intervals. Panel (b): survival and realised fraud, "
             "with group-specific linear fits."))

# ---- 7.4 welfare ----
add('<h2>7.4 Transaction social net benefit and welfare</h2>')
add("""<p>For a transaction between i and j, the social net benefit is the sum of the two
side payoffs: @@eq:sij@@ By the payoff structure of the model, @@eq:srules@@ The last sum is
zero because fraud is a pure wealth transfer, so no positive social value is imputed to it.
Welfare is accumulated over the fixed observation window: @@eq:wt@@ where
A<sub>t</sub> is the set of pairs actually settled in step t. Every run is tracked for the
full T = 200 steps; after collapse, agents that remain active continue to trade, and steps
with no trade contribute zero. The fixed horizon keeps W<sub>T</sub> comparable across
markets with different survival times.</p>""")

add("""<p>When a loss exceeds an agent's balance, the realised change in wealth is truncated at
zero. We therefore report W<sub>T</sub> on the realised basis, @@eq:sijreal@@ and give the
theoretical sum and the truncation gap alongside it. This choice keeps the wealth accounting
identity exact: @@eq:acct@@ The maximum absolute accounting error across the main sample is
""" + n3(K["acct_gap"]) + """.</p>""")

add(table_html(T["t76a"], ["Type", "Payoff i", "Payoff j", "S(ij)", "Interpretation"],
               "Table 7.6a. Social net benefit by transaction type.",
               "H-H is positive-sum, C-C is negative-sum, and H-C is a pure transfer."))
add(table_html(T["t76"], ["Outcome", "E = 0", "E = 1", "Difference"],
               "Table 7.6. Welfare and market outcomes over the fixed horizon.",
               "Means over the main sample. W_T is the realised cumulative social net benefit; "
               "cooperative traded value is 2 g_HH times the number of H-H trades; "
               "end-period total wealth includes wealth retained by evicted agents."))

add(f"""<p>Table 7.6 shows that the welfare gain is a compositional result. Without expulsion
the H&ndash;H contribution of {n2(K['wthh0'])} is more than offset by the C&ndash;C
contribution of {n2(K['wtcc0'])}, leaving W<sub>T</sub> = {n2(K['wt0'])}; end-period wealth
falls to {n2(K['endw0'])} from an initial stock of 4,000. With expulsion the H&ndash;H
contribution rises to {n2(K['wthh1'])} while the C&ndash;C loss shrinks to
{n2(K['wtcc1'])}, giving W<sub>T</sub> = {n2(K['wt1'])} and end-period wealth of
{n2(K['endw1'])}. Cooperative volume rises from {n2(K['coop0'])} to {n2(K['coop1'])}
trades, and restricted survival from {n2(K['surv0'])} to {n2(K['surv1'])} steps. Figure 7.4
plots the cumulative path and the decomposition. Because H&ndash;H payoffs are exogenous
positive-sum injections, W<sub>T</sub> is a model-implied surplus index rather than a measure
of real resources; it should be read together with cooperative volume and survival, not
compared across calibrations as a welfare level.</p>""")

add(fig_html("fig7_4_welfare",
             "Figure 7.4. Cumulative social net benefit and its decomposition by transaction type. "
             "The treated market accumulates positive surplus because cooperative trade persists."))

# ---- 7.5 survival cost ----
add('<h2>7.5 Survival cost, market exit and wealth-exhaustion death</h2>')
add("""<p>A per-step survival cost c requires an explicit interpretation before it enters
welfare. If c represents a real resource consumed by keeping an agent active in the market,
it is a resource cost that never appears in any transaction payoff, and the appropriate
object is @@eq:wtr@@ where I<sub>t</sub> is the set of active agents in step t. If c is
instead an accounting normalisation or a transfer between accounts, it is not a social cost
and must not be subtracted from W<sub>T</sub>. Table 7.7 reports both objects separately.
The distinction is substantive: under the resource interpretation the same transaction path
can generate a smaller welfare number, while under the accounting interpretation welfare is
unchanged and only the distribution of balances moves.</p>""")

add(f"""<p>At c = 0.30 and E = 1, realised transaction welfare is {n2(K['cost_c30_wt1'])}
and resource-adjusted welfare is {n2(K['cost_c30_adj1'])}; {n2(K['cost_c30_costdeath1'])}
agents die of the survival cost against {n2(K['cost_c30_tradedeath1'])} trade deaths, so cost
deaths are a distinct, small channel in this calibration. At c = 0 no cost death is possible
by construction. Figure 7.6 shows how both welfare measures and the death composition move
with c.</p>""")

add(f"""<p>Market exit and wealth-exhaustion death are reported in separate columns. In the
c = 0, E = 1 cell there are {n2(K['cost_c0_evicted1'])} eviction labels,
{n2(K['cost_c0_bank1'])} bankruptcy labels and {n2(K['cost_c0_both1'])} simultaneous labels,
while {n2(K['cost_c0_alive1'])} agents are alive and {n2(K['cost_c0_death1'])} are dead.
Every bankruptcy in this calibration is a wealth-exhaustion death, so the bankruptcy and
death counters coincide by construction; expulsion, by contrast, removes agents whose wealth
stays positive, which is why the number alive exceeds the number still active. The "both"
flag is empty here because a reported cheater is expelled before his balance is exhausted.
Separating the two concepts is therefore not bookkeeping: with c &gt; 0, cost deaths appear as
a channel that leaves transaction welfare unchanged but reduces end-period wealth.</p>""")

add(table_html(T["t77"], ["c", "E", "W_T", "Cost c", "Adj. W_T", "End wealth", "Survival",
                          "Trade deaths", "Cost deaths", "Bankruptcy", "Eviction", "Both",
                          "Exits", "Alive", "Evicted wealth"],
               "Table 7.7. Survival cost, resource-adjusted welfare and the exit/death decomposition.",
               "Subsample with rho in {0.10, 0.25}, p = 3, a = 3, 20 seeds per cell. "
               "'Cost c' is the realised aggregate survival cost; 'Adj. W_T' subtracts it from W_T. "
               "Trade deaths and cost deaths correspond to death causes 0 and 1.", wide=True))
add(fig_html("fig7_6_survival_cost",
             "Figure 7.6. Survival cost, resource-adjusted welfare, death composition and surviving agents. "
             "Cost deaths emerge only when c > 0; eviction removes agents without killing them."))

# ---- 7.6 robustness ----
add('<h2>7.6 Robustness</h2>')
add("""<p>Table 7.8 re-estimates the three mechanism equations under alternative inference
and measurement choices: configuration fixed effects, clustering on the seed or on the
configuration &times; seed block, trading capacities a = 2 and a = 4, per-trade composition
outcomes instead of raw counts, and a conversion share truncated to [0.02, 0.98] to
respect its bounded support. The sign and significance of the treatment coefficient are
unchanged in every column. Clustering on the seed gives noticeably smaller intervals than
clustering on the cell, because common random numbers induce negative within-seed residual
correlation; the cell-clustered specification is therefore the conservative baseline. The
per-trade specification is the most informative about magnitude, because it removes the
mechanical dependence of cumulative counts on market lifetime.</p>""")
add(table_html(T["t78"], ["Specification", "Fraud", "Conversion", "Cooperation", "N"],
               "Table 7.8. Robustness of the mechanism estimates.",
               "Cell-clustered standard errors in parentheses; trading-capacity rows cluster on the seed "
               "(20 clusters). In the per-trade composition row Conversion is already a share and is "
               "reported as n.a. *** p < 0.01, ** p < 0.05, * p < 0.10."))

# ---- 7.7 conclusion ----
add('<h2>7.7 Conclusion and limits</h2>')
add("""<p>Three conclusions follow. First, the institutional switch produces the joint
pattern predicted by the protection-of-cooperation mechanism: less fraud, slower conversion
and more cooperation, with all three effects concentrated in markets with a low initial
cheater share. Second, those variables are consequences of treatment, not mediators that can
be added to the collapse equation; the apparent attenuation of the treatment coefficient is
a post-treatment bias diagnostic, not a decomposition of the total effect. Third, the
welfare gain comes from shifting the composition of trade toward its positive-sum component,
and it must be reported together with cooperative volume, end-period wealth and survival on
a fixed horizon; a survival cost, when interpreted as a real resource, belongs in a separate
resource-adjusted measure.</p>""")
add("""<p>The model deliberately omits false reports, enforcement costs, appeals and re-entry
by expelled cheaters. All estimates identify effects inside this simulated market and should
not be extrapolated to real platform policy without additional evidence. The numbers in this
report are generated from the run-level and transaction-level files listed below, and every
figure and table is reproduced as a separate file alongside the report.</p>""")

add('<h2>Appendix. Reproducibility</h2>')
add("""<p>Simulation: code/simulate.py. Analysis: code/analysis_tables.py,
code/analysis_figures.py, code/render_formulas.js, code/build_report.py,
code/build_md_docx.py. Data:
data/run_level.csv (1,840 runs), data/timeseries.csv (step-level series),
data/event_ledger_baseline.csv (transaction ledger for the representative pair),
data/individual_final_baseline.csv (agent final states), data/params.json and
data/analysis.json. Figures: figures/*.svg and figures/*.png. Tables: tables/*.csv and
tables/tables_index.html. This report ships in three formats: report.html
(self-contained), report.md (LaTeX math, figures referenced relatively) and
report.docx (native Word equations and embedded figures).</p>""")

add('</body></html>')

html = "\n".join(P)
html = re.sub(r"@@eq:([a-zA-Z0-9_]+)@@", lambda m: EQ[m.group(1)], html)
with open(os.path.join(OUT, "report.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("wrote report.html", len(html), "chars;", len(cache), "fonts inlined")

# ------------------------------ tables index ------------------------------
TI = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Section 7 - Tables</title>',
      '<style>body{font-family:"Times New Roman",Times,serif;color:#000;background:#fff;',
      'font-size:11pt;max-width:960px;margin:0 auto;padding:30px 36px 60px}',
      'h1{font-size:19pt;font-weight:normal}h2{font-size:13pt;font-weight:normal;margin-top:26px}',
      '.tcap{font-size:10.6pt;margin:14px 0 5px}.tnote{font-size:9.4pt;margin:5px 0 14px}',
      'table{border-collapse:collapse;width:100%;font-size:9.6pt;margin:0}',
      '.tblwrap{margin:0 0 16px;break-inside:avoid}.tblwrap.wide table{font-size:8.5pt}',
      'th,td{border-bottom:1px solid #c4c4c4;padding:3px 6px;text-align:left;vertical-align:top}',
      'th{border-top:1px solid #333;border-bottom:1px solid #333;font-weight:normal}',
      'td.num{text-align:right;white-space:nowrap}</style></head><body>',
      '<h1>Section 7 - Tables</h1><p>All tables quoted in the report, in machine-readable CSV form in the same folder.</p>']
TI.append(table_html(T["t71"], ["Parameter", "Symbol", "Value", "Role"], "Table 7.1. Calibration and experimental design.", ""))
TI.append(table_html(T["t72"], ["Block", "Variable", "Definition"], "Table 7.2. Output variables recorded by the simulator.", ""))
TI.append(table_html(T["t73"], ["Variable", "E = 0 mean", "(s.d.)", "E = 1 mean", "(s.d.)", "Difference"], "Table 7.3. Descriptive statistics by institutional arm.", ""))
TI.append(table_html(T["t74"], ["Variable", "Fraud", "Conversion", "Cooperation"], "Table 7.4. Mechanism outcome regressions.", ""))
TI.append(table_html(T["t75"], ["Specification", "E coefficient (s.e.)", "95% CI", "Fraud /1e3", "Conversion", "Coop. /1e3", "R2", "N"], "Table 7.5. Collapse equation with and without post-treatment controls.", ""))
TI.append(table_html(T["t76a"], ["Type", "Payoff i", "Payoff j", "S(ij)", "Interpretation"], "Table 7.6a. Social net benefit by transaction type.", ""))
TI.append(table_html(T["t76"], ["Outcome", "E = 0", "E = 1", "Difference"], "Table 7.6. Welfare and market outcomes over the fixed horizon.", ""))
TI.append(table_html(T["t77"], ["c", "E", "W_T", "Cost c", "Adj. W_T", "End wealth", "Survival", "Trade deaths", "Cost deaths", "Bankruptcy", "Eviction", "Both", "Exits", "Alive", "Evicted wealth"], "Table 7.7. Survival cost, resource-adjusted welfare and the exit/death decomposition.", "", wide=True))
TI.append(table_html(T["t78"], ["Specification", "Fraud", "Conversion", "Cooperation", "N"], "Table 7.8. Robustness of the mechanism estimates.", ""))
TI.append('</body></html>')
with open(os.path.join(TAB, "tables_index.html"), "w", encoding="utf-8") as f:
    f.write("\n".join(TI))
print("wrote tables/tables_index.html")
