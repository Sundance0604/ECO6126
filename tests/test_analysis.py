from __future__ import annotations

import unittest
import json
import numpy as np
import pandas as pd

from analysis.A_baseline import block_weights, design_matrix, fit_ols, label_feasibility
from scripts.run_baseline import simulate_units
from src.market import ROOT


class AnalysisTests(unittest.TestCase):
    def test_process_count_does_not_change_results(self):
        config = json.loads((ROOT / "configs/baseline.json").read_text())
        config.update(N=10, T=5)
        jobs = [(config, "test", .3, s, E, B, False)
                for s, E, B in ((0, 0, 0), (1, 1, 1), (2, 0, 1))]
        self.assertEqual(list(simulate_units(jobs, 1)), list(simulate_units(jobs, 2)))

    def synthetic(self):
        rows = []
        for seed in range(6):
            for rho in (0.1, 0.3):
                for E in (0, 1):
                    for B in (0, 1):
                        rows.append(dict(seed=seed, rho=rho, E=E, B=B,
                                         y=10+seed+2*E+3*B+4*E*B+5*(rho == .3)+seed*E))
        return pd.DataFrame(rows)

    def test_ols_known_coefficients_and_conditional_effect(self):
        f = self.synthetic()
        weights = block_weights(6, 100, 11)
        result, diagnostics = fit_ols(f, "y", weights)
        estimates = result.set_index("term").estimate
        self.assertAlmostEqual(estimates["E"], 4.5)
        self.assertAlmostEqual(estimates["B"], 3)
        self.assertAlmostEqual(estimates["E:B"], 4)
        self.assertAlmostEqual(estimates["E|B=1"], 8.5)
        self.assertAlmostEqual(estimates["rho[0.30]"], 5)
        self.assertEqual(diagnostics["rank"], 5)

    def test_block_bootstrap_matches_explicit_refit(self):
        f = self.synthetic()
        weights = block_weights(6, 25, 99)
        X, names = design_matrix(f)
        seeds = f.seed.to_numpy()
        y = f.y.to_numpy()
        linear_boot = weights @ np.array([X[seeds == s].T @ y[seeds == s] for s in range(6)]) @ np.linalg.inv(X.T @ X)
        for draw, counts in enumerate(weights.astype(int)):
            selected = np.concatenate([np.tile(np.flatnonzero(seeds == s), count)
                                       for s, count in enumerate(counts) if count])
            explicit = np.linalg.lstsq(X[selected], y[selected], rcond=None)[0]
            np.testing.assert_allclose(linear_boot[draw], explicit, atol=1e-10)
        self.assertTrue((weights.sum(axis=1) == 6).all())

    def test_labels_exclude_prevalent_and_keep_non_events_negative(self):
        frame = pd.DataFrame({"collapse_event": [1, 1, 0, 1], "collapse_time": [1, 3, 200, 30],
                              "T": [200]*4, "rho": [.3]*4, "E": [1]*4, "B": [1]*4})
        row = label_feasibility(frame).query("group == 'pooled' and t0 == 2 and horizon == 20").iloc[0]
        self.assertEqual(row.n_prevalent_excluded, 1)
        self.assertEqual(row.n_at_risk, 3)
        self.assertEqual(row.n_positive, 1)
        self.assertEqual(row.n_negative, 2)
        self.assertEqual(row.n_unknown_window, 0)


if __name__ == "__main__":
    unittest.main()
