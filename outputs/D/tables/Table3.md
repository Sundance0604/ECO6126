# Table 3 Out of sample CATE comparison

| Test | Model | Cell MAE | Cell RMSE | Paired RMSE | MAE bootstrap SD |
|---|---|---:|---:|---:|---|
| New seeds | OLS interaction | 40.64 | 46.85 | 54.93 | 0.69 |
| Unseen configurations | OLS interaction | 36.84 | 43.72 | 54.17 | 1.28 |
| New seeds | OLS quadratic | 40.62 | 46.83 | 54.91 | 0.69 |
| Unseen configurations | OLS quadratic | 37.07 | 43.67 | 54.13 | 1.30 |
| New seeds | Segmented regression | 32.04 | 38.91 | 48.33 | 0.78 |
| Unseen configurations | Segmented regression | 31.82 | 39.50 | 50.83 | 1.75 |
| New seeds | Random Forest | 1.98 | 4.58 | 29.03 | 0.63 |
| Unseen configurations | Random Forest | 6.06 | 15.49 | 35.55 | 1.99 |
| New seeds | Gradient Boosting | 2.06 | 4.66 | 29.04 | 0.62 |
| Unseen configurations | Gradient Boosting | 4.71 | 12.77 | 34.45 | 1.57 |
| New seeds | R-learner | 2.15 | 4.74 | 29.05 | 0.63 |
| Unseen configurations | R-learner | 5.46 | 14.97 | 35.32 | 1.61 |

Bankruptcy is enabled (B = 1), q = 3, and the outcome is restricted survival through T = 200. Cell errors compare predictions with independent test seed mean paired effects. Paired RMSE includes individual simulation noise. Bootstrap SD resamples the 16 test seeds for a fixed fitted model; it excludes training uncertainty. Percentile ranges in the CSV describe the bootstrap distribution and are not confidence intervals for population prediction error. Hyperparameters and the primary ML model are selected exclusively on validation seeds.