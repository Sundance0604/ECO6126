# 7. Mechanism and Welfare Analysis

Reputation punishment and market collapse in a closed trading market

Simulation-based study | Fixed observation window T = 200 | 1,840 runs

## Abstract

Expulsion changes market outcomes only if it changes what happens inside the
market. This section examines the composition of trade and the social value of that trade using
1,440 paired simulation runs spanning eight initial cheater shares, three conversion
thresholds and 30 random seeds. Three mechanism outcomes — fraudulent trades, the
conversion share and cooperative trades — are regressed on the institutional switch and
predetermined controls. Averaged over the experimental grid, expulsion lowers fraud from
553.95 to 295.19 trades and the conversion share from 0.985 to
0.574, while cooperative trades rise from 812.20 to 22,038.66;
all three effects attenuate as the initial cheater share increases. We then show why these
post-treatment outcomes cannot be inserted into the collapse equation as though they identified
a causal mediation channel: doing so absorbs 97.67% of the treatment
coefficient. Welfare is aggregated from transaction-level social net benefits over a fixed
horizon and reported together with cooperative volume, end-period wealth and market survival,
then recomputed under a per-step survival cost. Market exit is kept separate from
wealth-exhaustion death throughout.

## 7.0 Model overview

### Population, timing and synchronous settlement

At t = 0 a closed market contains N = 200 agents, each endowed with $w_0 = 20$.
A share $\rho$ of them are cheaters (C) and the remainder are honest (H), so $N = H_0 + C_0,\qquad \rho = C_0/N$ and
the initial composition is fixed for the whole run. There is no entry. Time is discrete,
$t = 0,1,\ldots,T$ with T = 200; t = 0 denotes the initial state and all trading occurs in steps
1 to T. Identities are frozen within a step: every payoff in step t is computed from the
identities prevailing at the beginning of that step, and identity changes are applied only at
the step end. $$\text{type}_{i,s}=\text{type}_{i,t}\quad \text{for every transaction } s \text{ settled in step } t$$

### Matching, capacity and blacklists

In each step an active agent may trade with at most a = 3 distinct counterparties, and
any pair trades at most once per step. Matching is implemented as rounds of random
permutations of the active set; a proposed pair is discarded if either agent has reached the
per-step cap, if the pair has already traded in the step, or if either side is blacklisted by
the other. $$|\mathcal{P}_{i,t}| \le a,\qquad (i,j)\in\mathcal{A}_t \Rightarrow j\notin\mathcal{B}_{i,t},\ i\notin\mathcal{B}_{j,t}$$ Blacklists are directional and permanent. An honest agent who is
defrauded blacklists the cheater and files one report against him; two cheaters who meet
blacklist each other but do not report. Blacklist updates take effect at the step end, so
the same pair can defraud a given honest agent at most once.

### Transaction types, identity change and exit

Three transaction types are possible. Two honest agents each receive
$g_{HH} = +1.5$; two cheaters each incur $g_{CC} = -2.0$; an honest–cheater pair transfers
$x = 5$ from the honest agent to the cheater, so the two sides sum to zero. The transfer is
truncated at the honest agent's balance and therefore remains a pure wealth transfer. A
defrauded honest agent accumulates one victimisation m, and one report r is filed against the
cheater. At the step end, $$m_{i,t}\ge p \ \Longrightarrow\ \text{type}_{i,t+1}=C \quad (\text{irreversible})$$ conversion is irreversible and the current step is
still settled as honest. Exit follows two rules: $$w_{i,t}\le 0 \Rightarrow w_{i,t}=0,\ \text{exit};\qquad r_{i,t}\ge q \Rightarrow \text{exit with } w_{i,t}\ \text{retained}$$ Eviction is active only under
the institutional switch E = 1, with q = 3; bankruptcy is always active. The two labels can
trigger simultaneously and are recorded as a "both" flag. An evicted agent keeps the wealth
he holds at exit; a bankrupt agent's wealth is zeroed. Exit makes an agent inactive but is
not by itself a death event.

### Survival cost and death accounting

A per-step survival cost c > 0 is charged to every active agent after trading and
before the exit checks; the baseline sets c = 0. Two death causes are distinguished: a trade
death (cause 0) if trading has driven wealth to zero, and a cost death (cause 1) if the
survival cost does so. Agents with positive wealth are recorded as alive even after eviction.
Table 7.1 lists the calibration and Table 7.2 gives the full output dictionary, including
the macro statistics, individual state variables and activity flags recorded by the
simulator.

Table 7.1. Calibration and experimental design.

| Parameter | Symbol | Value | Role |
|---|---|---|---|
| Market size | N | 200 | Closed population, no entry |
| Initial honest / cheaters | H0 / C0 | N(1-rho) / N*rho | rho on 0.05-0.40 grid |
| Initial wealth | w0 | 20 | Identical for every agent |
| Observation window | T | 200 | Fixed horizon, right censoring |
| Counterparties per step | a | 3 | Robustness: 2, 4 |
| H-H one-sided payoff | g_HH | +1.5 | 2 g_HH = +3 per trade |
| C-C one-sided payoff | g_CC | -2.0 | 2 g_CC = -4 per trade |
| H-C transfer | x | 5.0 | Pure transfer, sum = 0 |
| Conversion threshold | p | 2, 3, 4 | Victimisations before H becomes C |
| Eviction threshold | q | 3 | Reports before expulsion |
| Survival cost | c | 0 (main); 0.10, 0.30 | Per active agent per step |
| Expulsion switch | E | 0, 1 | Institutional treatment |
| Bankruptcy | w <= 0 | always on | Wealth zeroed, agent exits |
| Seeds per cell | S | 30 (main), 20 (subsamples) | Common random numbers |

Note: Values are fixed across all runs unless a robustness cell states otherwise. The initial cheater share takes eight values from 0.05 to 0.40; the conversion threshold p takes 2, 3 and 4.

Table 7.2. Output variables recorded by the simulator.

| Block | Variable | Definition |
|---|---|---|
| Macro | Active agents | Number of agents still participating in the market |
| Macro | Active honest / cheaters | Active agents split by current identity |
| Macro | Active wealth | Sum of wealth held by active agents |
| Macro | Evicted-label wealth | Wealth retained at exit by agents carrying the eviction label |
| Macro | Cumulative conversions | Honest agents crossing m >= p |
| Macro | Cumulative bankruptcy / eviction / both | Exit labels; both records simultaneous triggers |
| Macro | Cumulative exits | Agents leaving the market under any label |
| Macro | Trade edges in step | Distinct pairs settled in the current step |
| Macro | Surviving agents | Agents with positive wealth (alive flag) |
| Macro | Cumulative deaths | Agents whose wealth reached zero |
| Macro | Trade / cost deaths | Deaths caused by trading losses / by the survival cost |
| Individual | Identity | Honest (H) or cheater (C) at the end of the step |
| Individual | Current wealth | Balance after step-end settlement |
| Individual | Cumulative victimisation m | Number of fraudulent encounters |
| Individual | Report count r | Reports accumulated by a cheater |
| Individual | Blacklist size | Number of counterparties blacklisted by the agent |
| Individual | Blacklisted-by count | Number of agents blacklisting this agent |
| Individual | First-exit wealth snapshot | Wealth recorded at the first exit |
| Individual | First-exit time | Step of the first exit |
| Individual | Death time | Step in which wealth reached zero |
| Individual | Death cause | -1 none, 0 trade death, 1 cost death |
| Activity | Active flag | 1 while participating, 0 after exit |
| Activity | Bankruptcy flag | 1 if wealth was exhausted |
| Activity | Eviction flag | 1 if r reached q under E = 1 |
| Activity | Both flag | 1 if bankruptcy and eviction triggered together |
| Activity | Alive flag | 1 while wealth is positive; exit need not imply death |

Note: Market exit (bankruptcy, eviction, both) and wealth-exhaustion death are separate concepts; an evicted agent remains alive while his wealth is positive.

## 7.1 Experimental design and descriptive evidence

Two institutional arms are compared. Under E = 0 the report–eviction rule is
disabled; under E = 1 a cheater is expelled once r reaches q = 3. Bankruptcy operates in both
arms. Predetermined controls are the initial cheater share $\rho$ (eight values), the
conversion threshold p (three values), trading capacity a = 3 and the random seed
(30 seeds per cell). Common random numbers are used across arms: the same seed
initialises the same initial identities and the same random stream, although the trading
paths diverge once the institution removes agents. Each run is tracked for the full fixed
window, so welfare is measured on a common horizon. Market collapse is the first step at
which active honest agents fall to 10% of $H_0$; runs that never collapse are right
censored and the outcome is $Y=\min(T^{\mathrm{collapse}},T)$.

Table 7.3 reports the raw contrast. Restricted survival rises from
6.62 to 90.23 steps, cooperative trades from 812.20 to
22,038.66, and cumulative net benefit from -3,827.75 to 64,693.06.
These are unconditional differences; the regressions below condition on the experimental
controls.

Table 7.3. Descriptive statistics by institutional arm.

| Variable | E = 0 mean | (s.d.) | E = 1 mean | (s.d.) | Difference |
|---|---|---|---|---|---|
| Restricted survival steps | 6.622 | 2.921 | 90.235 | 95.818 | 83.612 |
| Collapse observed (0/1) | 1.0 | 0.0 | 0.568 | 0.496 | -0.432 |
| Fraudulent trades (H-C) | 553.954 | 147.358 | 295.189 | 175.523 | -258.765 |
| Cooperative trades (H-H) | 812.201 | 751.495 | 22038.664 | 24832.933 | 21226.462 |
| Cheater-cheater trades (C-C) | 1677.714 | 490.531 | 386.093 | 358.395 | -1291.621 |
| All traded edges | 3043.869 | 1353.703 | 22719.946 | 24346.482 | 19676.076 |
| Conversion share of H0 | 0.985 | 0.037 | 0.574 | 0.484 | -0.411 |
| Converted honest agents | 153.026 | 25.528 | 81.869 | 70.373 | -71.157 |
| Active agents at T | 8.286 | 6.002 | 73.785 | 83.705 | 65.499 |
| Active honest at T | 0.0 | 0.0 | 72.781 | 84.553 | 72.781 |
| Active cheaters at T | 8.286 | 6.002 | 1.004 | 1.919 | -7.282 |
| Wealth of active agents | 172.252 | 295.771 | 66177.608 | 76948.493 | 66005.356 |
| Wealth of evicted-label agents | 0.0 | 0.0 | 2515.455 | 1618.968 | 2515.455 |
| Bankruptcy labels | 191.714 | 6.002 | 52.601 | 49.688 | -139.113 |
| Eviction labels | 0.0 | 0.0 | 73.614 | 43.161 | 73.614 |
| Both labels | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| All exits | 191.714 | 6.002 | 126.215 | 83.705 | -65.499 |
| Deaths | 191.714 | 6.002 | 52.601 | 49.688 | -139.113 |
| Trade deaths | 191.714 | 6.002 | 52.601 | 49.688 | -139.113 |
| Cost deaths | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Surviving agents | 8.286 | 6.002 | 147.399 | 49.688 | 139.113 |
| Cumulative net benefit W_T | -3827.748 | 295.771 | 64693.063 | 75686.633 | 68520.811 |
| End-period total wealth | 172.252 | 295.771 | 68693.063 | 75686.633 | 68520.811 |
| Resource-adjusted W_T | -3827.748 | 295.771 | 64693.063 | 75686.633 | 68520.811 |

Note: Means over 720 runs per arm (main sample). Standard deviations in parentheses. Difference is the E = 1 mean minus the E = 0 mean.

## 7.2 Mechanism outcomes

Following the task specification, the three mechanism results are Fraud (the number
of honest–cheater transactions), Conversion (the share of initially honest agents who
become cheaters) and Cooperation (the number of honest–honest transactions). Each is
regressed separately on the institutional switch and predetermined controls, with
interactions between the switch and $\rho$ and between the switch and the p dummies:
$$Y_i^{k}=\alpha_k+\beta_k E_i+\gamma_k^{\prime}X_i+\delta_k(E_i\times\rho_i)+\lambda_k^{\prime}\left(E_i\times 1[p_i]\right)+\varepsilon_i^{k},\qquad k\in\{F,C,K\}$$ where $X_i$ contains $\rho_i$ and the p dummies. Standard errors
are clustered at the configuration × institution cell, and the confidence interval for
$\beta_E$ comes from a cluster bootstrap over the same cells. Because all three
outcomes are realised after treatment, these are reduced-form effects rather than
structural behavioural parameters.

Table 7.4 gives the estimates. Evaluated at $\rho = 0$ and p = 2, expulsion changes
fraud by -456.09 trades (s.e. 71.88), the conversion share by
-0.768 and cooperation by 40,124.13 trades. The signs are exactly
those predicted by a protection-of-cooperation mechanism: fewer fraudulent encounters,
slower conversion and more cooperative exchange. The interaction terms have the opposite
sign in every column (1,728.56, 2.866 and
-147,454.54), so each effect attenuates as the initial cheater share rises; the
implied zero crossings lie at $\rho \approx 0.26$, 0.27 and 0.27
respectively. Figure 7.1 shows the same attenuation directly.

Table 7.4. Mechanism outcome regressions.

| Variable | Fraud | Conversion | Cooperation |
|---|---|---|---|
| Constant | 545.243*** (13.088) | 1.036*** (0.015) | 1602.229*** (222.912) |
| E (expulsion) | -456.088*** (71.882) | -0.768*** (0.170) | 40124.126*** (8983.623) |
| rho | -646.786*** (43.977) | -0.160*** (0.060) | -4992.071*** (952.783) |
| p = 3 | 154.933*** (8.087) | -0.007 (0.008) | 315.404** (146.485) |
| p = 4 | 307.779*** (11.476) | -0.040*** (0.015) | 684.163*** (224.256) |
| E x rho | 1728.558*** (219.861) | 2.866*** (0.480) | -147454.542*** (23909.901) |
| E x p = 3 | -174.988*** (62.986) | -0.289** (0.131) | 14718.638** (6961.207) |
| E x p = 4 | -399.821*** (60.175) | -0.574*** (0.140) | 28120.188*** (6676.135) |
| 95% CI for E (cluster bootstrap) | [-613.020, -293.784] | [-1.126, -0.377] | [20983.963, 57256.484] |
| Observations | 1440 | 1440 | 1440 |
| R-squared | 0.8342 | 0.7624 | 0.795 |
| Clusters (rho x p x E cell) | 48 | 48 | 48 |

Note: Each column is a separate OLS regression. Cluster-robust standard errors in parentheses, clustered on the rho x p x E cell (48 cells); *** p < 0.01, ** p < 0.05, * p < 0.10 based on the normal approximation. The 95% CI for E resamples whole cells (1,200 replications).

![fig7_1_mechanism_by_rho](figures/fig7_1_mechanism_by_rho.png)

Figure 7.1. Mechanism outcomes across the initial cheater share, averaged over p and seeds. The protective effect of expulsion concentrates at low rho and vanishes near rho = 0.26.

![fig7_2_market_dynamics](figures/fig7_2_market_dynamics.png)

Figure 7.2. Market dynamics under each institution, averaged over two rho cells and 30 seeds. Without expulsion the honest layer disappears within roughly ten steps; with expulsion it stabilises.

![fig7_3_trade_composition](figures/fig7_3_trade_composition.png)

Figure 7.3. Trade composition in a representative run (rho = 0.10, p = 3, seed = 0). Shares are carried forward in steps with no trade.

The composition evidence matters because raw trade counts are mechanically scaled by
market lifetime: treated markets survive 90.23 steps on average against
6.62 for controls, so any cumulative count tends to rise with E even if
per-trade behaviour is unchanged. Re-estimating the mechanism equations on per-trade shares
isolates the structural change: the fraud share falls by 0.116
and the cooperation share rises by 0.493 (Table 7.8). Expulsion therefore
does more than keep the market open longer; it shifts the mix of transactions away from
zero-sum fraud and negative-sum cheater collusion toward positive-sum cooperation. This is
the sense in which the results are consistent with the protection-of-cooperation mechanism,
and it is also why the seizure of a cheater's future trading opportunities, rather than the
recovery of transferred wealth, is the operative channel.

## 7.3 Why these results are not a mediation analysis

The collapse equation relates restricted survival to the institutional switch and
predetermined controls: $$Y_i=\alpha+\beta E_i+\gamma^{\prime}X_i+\varepsilon_i$$ A tempting but invalid extension adds the three
mechanism outcomes as if they were mediators: $$Y_i=\alpha+\beta^{\prime}E_i+\phi_1 F_i+\phi_2 C_i+\phi_3 K_i+\gamma^{\prime}X_i+u_i$$ The coefficient on E in the
second equation is not a direct effect, and its difference from the first is not an indirect
effect. Table 7.5 reports both specifications.

The baseline treatment coefficient is 140.86 survival steps. Adding
Fraud, Conversion and Cooperation reduces it to 3.29; the apparent
"explained share" $1-\hat{\beta}^{\prime}/\hat{\beta}$ is 97.67%. Figure 7.5 plots the
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
share.

Table 7.5. Collapse equation with and without post-treatment controls.

| Specification | E coefficient (s.e.) | 95% CI | Fraud /1e3 | Conversion | Coop. /1e3 | R2 | N |
|---|---|---|---|---|---|---|---|
| (1) Baseline | 140.859 (33.018) | [70.005, 203.799] | - | - | - | 0.7666 | 1440 |
| (2) + post-treatment outcomes | 3.288 (3.639) | [-7.374, 12.729] | 119.067 | -176.442 | 1.405 | 0.9967 | 1440 |
| (3) + outcomes, config FE | 4.244 (2.018) | [-35.357, 10.329] | 113.546 | -173.292 | 1.379 | 0.9982 | 1440 |

Note: Dependent variable: restricted survival steps Y = min(Tcollapse, 200). All specifications include rho, p dummies and their interactions with E. Post-treatment controls are divided by 1,000 where indicated. Standard errors clustered on the rho x p x E cell; 95% CI from a cluster bootstrap.

![fig7_5_bad_control](figures/fig7_5_bad_control.png)

Figure 7.5. Post-treatment bias diagnostic. Panel (a): attenuation of the treatment coefficient with 95% cluster-bootstrap intervals. Panel (b): survival and realised fraud, with group-specific linear fits.

## 7.4 Transaction social net benefit and welfare

For a transaction between i and j, the social net benefit is the sum of the two
side payoffs: $S_{ij}=g_{ij}^{i}+g_{ij}^{j}$ By the payoff structure of the model, $$S^{HH}=2g_{HH}>0,\qquad S^{CC}=2g_{CC}<0,\qquad S^{HC}=g_{HC}^{H}+g_{HC}^{C}=0$$ The last sum is
zero because fraud is a pure wealth transfer, so no positive social value is imputed to it.
Welfare is accumulated over the fixed observation window: $$W_T=\sum_{t=1}^{T}\ \sum_{(i,j)\in\mathcal{A}_t}\left(g_{ij}^{i}+g_{ij}^{j}\right)$$ where
$A_t$ is the set of pairs actually settled in step t. Every run is tracked for the
full T = 200 steps; after collapse, agents that remain active continue to trade, and steps
with no trade contribute zero. The fixed horizon keeps $W_T$ comparable across
markets with different survival times.

When a loss exceeds an agent's balance, the realised change in wealth is truncated at
zero. We therefore report $W_T$ on the realised basis, $S_{ij}^{\mathrm{real}}=\Delta w_i+\Delta w_j$ and give the
theoretical sum and the truncation gap alongside it. This choice keeps the wealth accounting
identity exact: $$\sum_{i=1}^{N} w_{i,T}=N w_0+W_T^{\mathrm{real}}-C_T^{\mathrm{real}}$$ The maximum absolute accounting error across the main sample is
0.000.

Table 7.6a. Social net benefit by transaction type.

| Type | Payoff i | Payoff j | S(ij) | Interpretation |
|---|---|---|---|---|
| H-H (cooperation) | +g_HH = +1.5 | +g_HH = +1.5 | 2 g_HH = +3.0 | Positive (wealth creating) |
| C-C (collusion) | g_CC = -2.0 | g_CC = -2.0 | 2 g_CC = -4.0 | Negative (wealth destroying) |
| H-C (fraud) | g_HC^H = -x | g_HC^C = +x | 0 | Zero (pure transfer) |

Note: H-H is positive-sum, C-C is negative-sum, and H-C is a pure transfer.

Table 7.6. Welfare and market outcomes over the fixed horizon.

| Outcome | E = 0 | E = 1 | Difference |
|---|---|---|---|
| W_T, realised social net benefit | -3827.748 | 64693.063 | 68520.811 |
| W_T, theoretical (no truncation) | -4274.251 | 64571.619 | 68845.871 |
| Theoretical minus realised | -446.503 | -121.444 | 325.06 |
| Contribution of H-H trades | 2436.604 | 66115.992 | 63679.388 |
| Contribution of C-C trades | -6710.856 | -1544.372 | 5166.483 |
| Contribution of H-C trades | 0.0 | 0.0 | 0.0 |
| Cooperative trade volume (trades) | 812.201 | 22038.664 | 21226.462 |
| Cooperative traded value (2 g_HH x trades) | 2436.604 | 66115.992 | 63679.388 |
| Fraudulent trades | 553.954 | 295.189 | -258.765 |
| Cheater-cheater trades | 1677.714 | 386.093 | -1291.621 |
| End-period total wealth | 172.252 | 68693.063 | 68520.811 |
| End-period wealth of active agents | 172.252 | 66177.608 | 66005.356 |
| Wealth retained by evicted-label agents | 0.0 | 2515.455 | 2515.455 |
| Restricted market survival (steps) | 6.622 | 90.235 | 83.612 |
| Wealth accounting identity error | 0.0 | 0.0 | 0.0 |
| Realised survival cost | 0.0 | 0.0 | 0.0 |
| Resource-adjusted welfare W_T - c | -3827.748 | 64693.063 | 68520.811 |

Note: Means over the main sample. W_T is the realised cumulative social net benefit; cooperative traded value is 2 g_HH times the number of H-H trades; end-period total wealth includes wealth retained by evicted agents.

Table 7.6 shows that the welfare gain is a compositional result. Without expulsion
the H–H contribution of 2,436.60 is more than offset by the C–C
contribution of -6,710.86, leaving $W_T = -3,827.75$; end-period wealth
falls to 172.25 from an initial stock of 4,000. With expulsion the H–H
contribution rises to 66,115.99 while the C–C loss shrinks to
-1,544.37, giving $W_T = 64,693.06$ and end-period wealth of
68,693.06. Cooperative volume rises from 812.20 to 22,038.66
trades, and restricted survival from 6.62 to 90.23 steps. Figure 7.4
plots the cumulative path and the decomposition. Because H–H payoffs are exogenous
positive-sum injections, $W_T$ is a model-implied surplus index rather than a measure
of real resources; it should be read together with cooperative volume and survival, not
compared across calibrations as a welfare level.

![fig7_4_welfare](figures/fig7_4_welfare.png)

Figure 7.4. Cumulative social net benefit and its decomposition by transaction type. The treated market accumulates positive surplus because cooperative trade persists.

## 7.5 Survival cost, market exit and wealth-exhaustion death

A per-step survival cost c requires an explicit interpretation before it enters
welfare. If c represents a real resource consumed by keeping an agent active in the market,
it is a resource cost that never appears in any transaction payoff, and the appropriate
object is $$W_T^{R}=W_T-\sum_{t=1}^{T}\sum_{i\in\mathcal{I}_t} c$$ where $I_t$ is the set of active agents in step t. If c is
instead an accounting normalisation or a transfer between accounts, it is not a social cost
and must not be subtracted from $W_T$. Table 7.7 reports both objects separately.
The distinction is substantive: under the resource interpretation the same transaction path
can generate a smaller welfare number, while under the accounting interpretation welfare is
unchanged and only the distribution of balances moves.

At c = 0.30 and E = 1, realised transaction welfare is 80,456.90
and resource-adjusted welfare is 74,861.31; 2.08
agents die of the survival cost against 33.38 trade deaths, so cost
deaths are a distinct, small channel in this calibration. At c = 0 no cost death is possible
by construction. Figure 7.6 shows how both welfare measures and the death composition move
with c.

Market exit and wealth-exhaustion death are reported in separate columns. In the
c = 0, E = 1 cell there are 74.80 eviction labels,
34.35 bankruptcy labels and 0.00 simultaneous labels,
while 165.65 agents are alive and 34.35 are dead.
Every bankruptcy in this calibration is a wealth-exhaustion death, so the bankruptcy and
death counters coincide by construction; expulsion, by contrast, removes agents whose wealth
stays positive, which is why the number alive exceeds the number still active. The "both"
flag is empty here because a reported cheater is expelled before his balance is exhausted.
Separating the two concepts is therefore not bookkeeping: with c > 0, cost deaths appear as
a channel that leaves transaction welfare unchanged but reduces end-period wealth.

Table 7.7. Survival cost, resource-adjusted welfare and the exit/death decomposition.

| c | E | W_T | Cost c | Adj. W_T | End wealth | Survival | Trade deaths | Cost deaths | Bankruptcy | Eviction | Both | Exits | Alive | Evicted wealth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 0 | -3817.012 | 0.0 | -3817.012 | 182.988 | 6.825 | 188.175 | 0.0 | 188.175 | 0.0 | 0.0 | 188.175 | 11.825 | 0.0 |
| 0.0 | 1 | 80330.875 | 0.0 | 80330.875 | 84330.875 | 104.25 | 34.35 | 0.0 | 34.35 | 74.8 | 0.0 | 109.15 | 165.65 | 2568.2 |
| 0.1 | 0 | -3619.193 | 348.207 | -3967.4 | 32.6 | 6.825 | 183.725 | 12.0 | 195.725 | 0.0 | 0.0 | 195.725 | 4.275 | 0.0 |
| 0.1 | 1 | 80374.295 | 1868.8 | 78505.495 | 82505.495 | 104.25 | 33.45 | 2.0 | 35.45 | 74.8 | 0.0 | 110.25 | 164.55 | 2541.107 |
| 0.3 | 0 | -3239.803 | 760.197 | -4000.0 | 0.0 | 6.825 | 184.525 | 15.475 | 200.0 | 0.0 | 0.0 | 200.0 | 0.0 | 0.0 |
| 0.3 | 1 | 80456.902 | 5595.593 | 74861.31 | 78861.31 | 104.25 | 33.375 | 2.075 | 35.45 | 74.8 | 0.0 | 110.25 | 164.55 | 2486.922 |

Note: Subsample with rho in {0.10, 0.25}, p = 3, a = 3, 20 seeds per cell. 'Cost c' is the realised aggregate survival cost; 'Adj. W_T' subtracts it from W_T. Trade deaths and cost deaths correspond to death causes 0 and 1.

![fig7_6_survival_cost](figures/fig7_6_survival_cost.png)

Figure 7.6. Survival cost, resource-adjusted welfare, death composition and surviving agents. Cost deaths emerge only when c > 0; eviction removes agents without killing them.

## 7.6 Robustness

Table 7.8 re-estimates the three mechanism equations under alternative inference
and measurement choices: configuration fixed effects, clustering on the seed or on the
configuration × seed block, trading capacities a = 2 and a = 4, per-trade composition
outcomes instead of raw counts, and a conversion share truncated to [0.02, 0.98] to
respect its bounded support. The sign and significance of the treatment coefficient are
unchanged in every column. Clustering on the seed gives noticeably smaller intervals than
clustering on the cell, because common random numbers induce negative within-seed residual
correlation; the cell-clustered specification is therefore the conservative baseline. The
per-trade specification is the most informative about magnitude, because it removes the
mechanical dependence of cumulative counts on market lifetime.

Table 7.8. Robustness of the mechanism estimates.

| Specification | Fraud | Conversion | Cooperation | N |
|---|---|---|---|---|
| Main specification (Table 7.4) | -456.088*** (71.882) | -0.768*** (0.170) | 40124.126*** (8983.623) | 1440 |
| Configuration (rho x p) fixed effects | -456.088*** (53.254) | -0.768*** (0.122) | 40124.126*** (6373.299) | 1440 |
| Clustered on seed (common random numbers) | -456.088*** (1.278) | -0.768*** (0.002) | 40124.126*** (88.113) | 1440 |
| Clustered on config x seed block | -456.088*** (13.572) | -0.768*** (0.031) | 40124.126*** (1619.985) | 1440 |
| Trading capacity a = 2 (seed clusters) | -420.958*** (1.830) | -0.831*** (0.001) | 28623.992*** (48.233) | 80 |
| Trading capacity a = 4 (seed clusters) | -485.900*** (2.970) | -0.840*** (0.002) | 57851.825*** (119.609) | 80 |
| Per-trade composition outcomes | -0.116*** (0.033) | n.a. | 0.493*** (0.090) | 1440 |
| Conversion truncated to [0.02, 0.98] | -456.088*** (71.882) | -0.737*** (0.165) | 40124.126*** (8983.623) | 1440 |

Note: Cell-clustered standard errors in parentheses; trading-capacity rows cluster on the seed (20 clusters). In the per-trade composition row Conversion is already a share and is reported as n.a. *** p < 0.01, ** p < 0.05, * p < 0.10.

## 7.7 Conclusion and limits

Three conclusions follow. First, the institutional switch produces the joint
pattern predicted by the protection-of-cooperation mechanism: less fraud, slower conversion
and more cooperation, with all three effects concentrated in markets with a low initial
cheater share. Second, those variables are consequences of treatment, not mediators that can
be added to the collapse equation; the apparent attenuation of the treatment coefficient is
a post-treatment bias diagnostic, not a decomposition of the total effect. Third, the
welfare gain comes from shifting the composition of trade toward its positive-sum component,
and it must be reported together with cooperative volume, end-period wealth and survival on
a fixed horizon; a survival cost, when interpreted as a real resource, belongs in a separate
resource-adjusted measure.

The model deliberately omits false reports, enforcement costs, appeals and re-entry
by expelled cheaters. All estimates identify effects inside this simulated market and should
not be extrapolated to real platform policy without additional evidence. The numbers in this
report are generated from the run-level and transaction-level files listed below, and every
figure and table is reproduced as a separate file alongside the report.

## Appendix. Reproducibility

Simulation: code/simulate.py. Analysis: code/analysis_tables.py,
code/analysis_figures.py, code/render_formulas.js, code/build_report.py,
code/build_md_docx.py. Data:
data/run_level.csv (1,840 runs), data/timeseries.csv (step-level series),
data/event_ledger_baseline.csv (transaction ledger for the representative pair),
data/individual_final_baseline.csv (agent final states), data/params.json and
data/analysis.json. Figures: figures/*.svg and figures/*.png. Tables: tables/*.csv and
tables/tables_index.html.
