# C. How strict should expulsion be? A threshold response surface

Section B fixes the expulsion threshold at q = 3 and therefore answers the question whether expulsion works, not how strict it should be. This section varies the threshold itself. q is the number of public reports a cheater must accumulate before being expelled, so a smaller q is a stricter rule: q = 1 expels on the first report, q = 10 after ten.

## C.1 Design

We simulate the eight thresholds q = 1, 2, 3, 4, 5, 6, 8, 10 against the same five initial cheater shares and the same 100 random seeds, holding N = 100, a = 3, p = 3, T = 200 and the bankruptcy switch on. That is 4,000 simulated markets, of which 2,413 collapse inside the window. Expulsion is switched on in every cell, because q is undefined when there is no expulsion rule; the two switches are not crossed here. Seeds are shared across thresholds, so the same seed is the same market under eight rules, which is what makes the threshold contrasts paired.

Two features of the design limit what can be concluded. The thresholds are a grid of eight integers, not a continuous policy parameter, so any 'optimal q' is an optimum over the grid. And the bankruptcy switch is held at one so that the extension reproduces the baseline configuration of Section B; because that switch does not affect survival, the choice is immaterial for the survival outcome and matters only for the welfare panel.

## C.2 Estimands and inference

The primary specification is a set of threshold dummies with q = 1 as the reference, estimated with market-type fixed effects and standard errors clustered on the random seed:

Y = alpha + sum_{k != 1} beta_k 1(q = k) + gamma_rho + epsilon.

The coefficients are therefore differences from the strictest rule, in simulation periods for survival and in surplus units for welfare. Because eight thresholds produce seven coefficients per outcome, we report Romano-Wolf step-down adjusted p-values alongside the conventional cluster-robust ones, which controls the family of seven coefficients. A quadratic in q is reported only as a summary: the implied turning point is interpreted only if the curvature is estimated precisely and the turning point falls inside the grid. Finally, for every bootstrap replicate we record which threshold would have been chosen as best, which shows how confident a 'q = 1 is optimal' conclusion would be.

## C.3 Results

Survival declines monotonically in q. Relative to q = 1, the coefficients are -31.4, -49.9, -85.9, -90.5, -105.1, -117.9 and -140.3 periods for q = 2 to 10, all with intervals that exclude zero and all with Romano-Wolf adjusted p-values below 0.001. Welfare moves the same way and by larger relative amounts: from -12,710 to -71,058.

**Table 1. Threshold response by market type**

| q | RMST rho=0.05 | 0.10 | 0.20 | 0.30 | 0.40 | collapse rate (pooled) |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 200.0 | 200.0 | 200.0 | 181.5 | 21.5 | 0.21 |
| 2 | 200.0 | 200.0 | 200.0 | 40.8 | 5.0 | 0.37 |
| 3 | 200.0 | 200.0 | 144.0 | 5.4 | 3.9 | 0.46 |
| 4 | 200.0 | 159.5 | 6.4 | 4.2 | 3.3 | 0.64 |
| 5 | 200.0 | 137.2 | 5.9 | 4.0 | 3.1 | 0.67 |
| 6 | 200.0 | 65.0 | 5.3 | 4.0 | 3.1 | 0.74 |
| 8 | 192.8 | 8.9 | 5.0 | 4.0 | 3.1 | 0.81 |
| 10 | 81.6 | 7.8 | 5.0 | 4.0 | 3.1 | 0.93 |

Notes: restricted mean survival to period 200, 100 markets per cell. The collapse-rate column is the equal-weighted mean over the five market types.

**Table 2. Threshold dummies relative to q = 1**

| Threshold | RMST difference | 95% CI | RW p | Welfare difference | 95% CI |
|---|---:|---|---:|---:|---|
| 2 | -31.4 | -35.6 to -27.3 | <0.001 | -12,710 | -14,306 to -11,114 |
| 3 | -49.9 | -54.5 to -45.4 | <0.001 | -21,931 | -23,856 to -20,006 |
| 4 | -85.9 | -90.1 to -81.7 | <0.001 | -39,351 | -41,408 to -37,294 |
| 5 | -90.5 | -94.9 to -86.2 | <0.001 | -42,045 | -44,218 to -39,871 |
| 6 | -105.1 | -109.5 to -100.7 | <0.001 | -50,262 | -52,393 to -48,130 |
| 8 | -117.9 | -121.4 to -114.3 | <0.001 | -57,444 | -59,011 to -55,876 |
| 10 | -140.3 | -144.8 to -135.8 | <0.001 | -71,058 | -73,506 to -68,611 |

Notes: market-type fixed effects, standard errors clustered on the random seed, Romano-Wolf step-down p-values for the family of seven thresholds.

![Figure 2](outputs/C/figures/Figure2.png)

**Figure 2. Threshold response surface.** (a) Restricted mean survival by threshold and market type; (b) cumulative net surplus; (c) threshold dummies with 95 per cent cluster intervals; (d) share of bootstrap draws in which each threshold is best on survival.

The response is not a smooth gradient but a set of cliffs that move with the market. At rho = 0.05 no threshold below 8 changes anything: the market never collapses. At rho = 0.10 the cliff is between q = 3 and q = 4 (-0.0 vs -40.5 periods). At rho = 0.20 it is between q = 3 and q = 4, at rho = 0.30 between q = 1 and q = 2 (181.5 vs 40.8 periods of restricted survival), and at rho = 0.40 the whole range is compressed into 21.5 periods at q = 1 and about 5.0 thereafter. The stricter the rule that is required, the earlier the cliff appears as the cheater share rises.

No interior optimum exists in these data. The estimated quadratic is convex (second-order coefficient 1.49 with standard error 0.08), so its turning point at q = 10.4 is a minimum, and it lies outside the grid. In 100 per cent of the 2,000 seed-block bootstrap draws q = 1 produces the highest restricted survival, and the same holds for welfare (100 per cent). The data therefore say 'as strict as the grid allows', not 'strict up to a point'.

## C.4 Interpretation

Within the model, moving from q = 10 to q = 1 buys between 18 and 195 periods depending on the market, and the gain is concentrated where the cheater share is low to moderate. In high-share markets the strict rule shortens the collapse hazard but cannot prevent collapse; in low-share markets every rule up to q = 3 or 4 is already strict enough, so the additional strictness is free but worthless.

The policy reading has to stop there. This model has no false reports, no enforcement cost and no appeal, all of which are incurred per expulsion and are therefore proportional to strictness. A monotone 'stricter is better' surface with zero enforcement cost is close to a mechanical result; what the exercise contributes is the shape and the location of the cliffs, which a cost-per-expulsion term could be mapped onto. It is not evidence that a real platform should expel on the first report.

## C.5 Limitations

The threshold is an integer grid; the true response between grid points is unobserved, and the 'cliff' language describes the grid, not a continuous discontinuity. All 4,000 runs share the same baseline parameters, so nothing here generalises across N, a, p or T. Collapse times remain discrete and heavily tied, which is why the survival outcome is summarised by restricted means rather than by a hazard ratio. And the welfare comparisons ignore enforcement costs, so they are upper bounds on the net value of strictness.
