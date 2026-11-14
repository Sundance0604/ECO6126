# B. Survival analysis of market collapse

We treat each simulated market as a survival observation and ask how long the honest-trading base lasts under the two expulsion regimes. The section reports Kaplan-Meier curves, restricted mean survival times and their paired contrasts, and uses Cox models as a supplementary description where they are identified. The analysis is pre-specified in the sense that the estimand, the censoring rule and the bootstrap scheme follow the baseline protocol; nothing is selected on the basis of the results.

## B.1 Design and estimand

The design contains 2,000 runs: five initial cheater shares (rho = 0.05, 0.10, 0.20, 0.30, 0.40), two expulsion states, two bankruptcy states and 100 random seeds, so that every (rho, seed) pair is observed under both regimes. The outcome is the restricted collapse time Y = min(T_collapse, 200) together with the event indicator; 270 of the 1,000 expulsion runs reach the horizon without collapsing and are right-censored at 200, which is a censoring date and not an observed collapse. Collapse is the first period end at which active honest traders fall to at most 10 per cent of their initial number.

The estimand is Delta(rho) = E[Y(1) - Y(0) | rho], the difference in restricted mean survival time at the horizon, measured in simulation periods. Both states are simulated with the same seed, so the contrast is paired. The bankruptcy switch does not enter the survival estimand: for every (rho, seed, expulsion) triple the two bankruptcy states produce identical collapse times, because honest traders never exhaust their wealth in this calibration. Paired estimates therefore use the 1,000 runs with the switch off, so that no trajectory is counted twice; panel (a) of Figure 1 nevertheless plots all four institutions, which makes the duplication visible rather than implicit.

## B.2 Estimation and inference

Curves are estimated by the Kaplan-Meier product-limit estimator with Greenwood variances and pointwise log-log confidence bands, and the restricted mean is the area under the estimated curve from zero to the horizon. Differences are tested with the Mantel-Cox log-rank statistic, within each market type and stratified across rho. Cox models use the Efron correction for ties, enter rho as strata, and cluster standard errors on the random seed so that the pairing is respected.

Two features of the data shape the inference. Collapse times are integers, so the risk sets are dominated by tied events; Efron's correction is used throughout and a non-parametric discrete hazard is tabulated alongside. More consequentially, in four of the five market types the two regimes share no event time: every collapse in the no-expulsion arm occurs in a period in which the expulsion arm is still alive. The partial likelihood is then monotone in the coefficient and the maximum-likelihood estimate does not exist, so those fits are reported as not identified and Firth's penalised likelihood, which remains finite, is added as a bound.

Uncertainty is quantified by resampling whole seed blocks 5,000 times, each draw carrying all five market types and both regimes. Because outcomes are close to deterministic within a cell, these intervals describe simulation variability conditional on the model rather than sampling uncertainty about real platforms.

## B.3 Results

Pooled over the five market types, expulsion raises restricted survival from 5.90 to 110.65 periods, a gain of 104.75 periods (95 per cent interval 101.37 to 108.09), and the collapse rate falls from 1.00 to 0.46. This is the number reported in the baseline table, and it is a poor summary of the mechanism, because it averages a regime in which collapse is postponed beyond the window with a regime in which it is postponed by half a period.

**Table 1. Restricted mean survival and its difference by market type**

| rho | RMST(200), E=0 | RMST(200), E=1 | Difference | 95% CI | S(200), E=1 |
|---|---:|---:|---:|---|---:|
| 0.05 | 10.36 | 200.00 | 189.64 | 189.53 to 189.76 | 1.00 |
| 0.1 | 7.06 | 200.00 | 192.94 | 192.88 to 192.99 | 1.00 |
| 0.2 | 4.99 | 144.02 | 139.03 | 122.12 to 155.71 | 0.70 |
| 0.3 | 4.00 | 5.37 | 1.37 | 1.27 to 1.47 | 0.00 |
| 0.4 | 3.07 | 3.85 | 0.78 | 0.69 to 0.86 | 0.00 |
| pooled | 5.90 | 110.65 | 104.75 | 101.37 to 108.09 | 0.54 |

Notes: 100 markets per cell and market type, horizon 200. S(200) is the Kaplan-Meier share still active at the horizon. Intervals are 5,000 seed-block bootstrap percentile intervals. The pooled row weights the five market types equally.

![Figure 1](outputs/B/figures/Figure1.png)

**Figure 1. Survival of the honest-trading base under expulsion.** Panels (a)-(f): Kaplan-Meier curves, pooled and by initial cheater share, with pointwise 95 per cent log-log bands; panels (b)-(f) zoom to the first 24 periods. Panel (g): restricted mean survival on a logarithmic scale. Panel (h): paired difference with 5,000 seed-block bootstrap intervals. Panel (i): period-specific collapse hazards at rho = 0.40.

The contrast is a step, not a gradient. At rho = 0.05 and 0.10 no market in the expulsion arm collapses inside the window, so the gain equals the censoring-adjusted ceiling of 189.64 and 192.94 periods. At rho = 0.20, 0.70 of expulsion markets are still active at period 200 and the gain is 139.03 periods. At rho = 0.30 it falls to 1.37 periods and at rho = 0.40 to 0.78 periods, where most markets simply move from period 3 to period 4 and nothing else changes. The log-rank statistics trace the same pattern: 204.7, 216.9, 198.0, 199.0 and 121.9 across the five market types (all p < 1e-27), and 931.8 when stratified over rho.

**Table 2. Cox models for the expulsion effect**

| Specification | HR | 95% CI | Status |
|---|---:|---:|---|
| rho = 0.05 to 0.30 | not identified | — | monotone likelihood |
| rho = 0.05 to 0.30, Firth | 0.00094 | 0 to 0.00690 | penalised bound |
| rho = 0.40 | 0.212 | 0.033 to 1.379 | identified |
| pooled, rho strata | 0.0465 | 0.0084 to 0.2586 | driven by rho = 0.40 |
| pooled, Firth | 0.0467 | 0.0368 to 0.0587 | penalised |
| bankruptcy switch B | 1.000 | — | zero information, se = 0 |

Notes: Efron ties, rho as strata, standard errors clustered on seed. The Firth estimate for rho = 0.05 to 0.30 is a single number because every event time in those strata has a 50/50 risk set, so the penalised likelihood differs across strata only by a constant.

Only the highest-share market admits an unpenalised Cox estimate, with a hazard ratio of 0.212 (interval 0.033 to 1.379). Even there the proportional-hazards description fails where it matters: the collapse hazard in period 3 is 0.93 without expulsion and 0.15 with it, a ratio of 0.16, whereas in period 4 both arms collapse with probability one, a ratio of 1.00. A single hazard ratio averages a contrast that is present in one period and absent in the next, which is why the restricted mean, not the hazard ratio, is the primary estimand.

The pooled Cox coefficient is not a safe compromise. Dropping the rho = 0.40 stratum removes the only market type in which the two regimes share an event time, and the estimate ceases to exist. The pooled number is therefore a one-stratum estimate presented as a five-stratum one. Adding the bankruptcy switch confirms the diagnosis instead of changing it: the coefficient on that switch is exactly zero with a standard error of zero, because the switch leaves every risk set unchanged, and adding the E x B interaction leaves the log-likelihood unchanged to numerical precision.

## B.4 Interpretation

The expulsion rule does not rescale the hazard; it moves the collapse date. In markets with few initial cheaters the rule removes cheaters before honest traders accumulate the three losses that convert them, and the market never collapses inside the window. As the initial cheater share rises, the same rule must process more reports within a shorter window: the collapse is delayed by a period or two, and then not at all. The threshold is fixed at q = 3 throughout, so the results describe the value of one specific rule rather than the optimal one.

Two implications follow for the rest of the project. The survival effect is concentrated in the low-share region, so any pooled average across the five market types is a weighting artefact of the calibration grid rather than a policy-relevant quantity. And longer survival is not welfare: at rho = 0.20 the expulsion arm survives 144 periods on average, and the surplus generated over those periods is a separate object, analysed in the welfare section.

## B.5 Limitations

The intervals are Monte Carlo intervals. Within a cell the standard deviation of collapse times is at most 0.6 periods and is often zero across all 100 seeds, so the effective number of independent observations is closer to one per cell than to 100. Resampling seeds measures the stability of the simulation, not the precision with which a real platform's collapse time would be estimated.

The design holds q = 3, p = 3 and N = 100 fixed; nothing here generalises across those parameters. Censoring is administrative, not random. Finally, the model omits false reporting, enforcement costs and re-entry, so the survival advantage measured here is an upper bound on what a real reporting system would deliver.
