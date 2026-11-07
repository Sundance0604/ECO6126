from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np

from src.market import MarketModel, Params, original, HONEST, CHEAT
from src.metrics import fixed_horizon_rows, summarize_run


class ModelTests(unittest.TestCase):
    def compare_state(self, a, b):
        for key in ("theta", "w", "m", "r", "active", "alive", "flag_bankrupt", "flag_evict",
                    "exit_w", "exit_t", "death_t", "death_cause"):
            np.testing.assert_equal(getattr(a, key), getattr(b, key), err_msg=key)
        self.assertEqual(a.blacklist, b.blacklist)
        self.assertEqual(a.t, b.t)

    def test_adapter_matches_original_every_step(self):
        # Economic behavior must agree across both switches and two consumptions.
        for B in (False, True):
            for E in (False, True):
                for c in (0, 0.5):
                    for seed in (0, 7):
                        p = Params(H=14, C=6, seed=seed, c=c, max_steps=25,
                                   enable_bankrupt=B, enable_evict=E)
                        raw = original.MarketModel(p)
                        adapted = MarketModel(p, keep_edges=True, keep_individuals=True)
                        for _ in range(25):
                            x, y = raw.step(), adapted.step()
                            self.assertEqual(x, y)
                            self.compare_state(raw, adapted)
                            self.assertEqual(len(raw.edge_history), len(adapted.edge_history))
                            if not x:
                                break
                        for e, f in zip(raw.edge_history, adapted.edge_history):
                            self.assertEqual(e["t"], f["t_start"])
                            self.assertEqual(f["t"], e["t"]+1)
                            for key in ("i", "j", "theta_i", "theta_j", "type", "delta_w_i", "delta_w_j"):
                                self.assertEqual(e[key], f[key])

    def test_matching_and_monotonicity(self):
        for seed in range(5):
            m = MarketModel(Params(H=16, C=8, a=7, seed=seed), keep_edges=True)
            previous_h, previous_n = 16, 24
            for _ in range(20):
                before_bl = [set(s) for s in m.blacklist]
                before_active = m.active.copy()
                count = len(m.edge_history)
                if not m.step():
                    break
                events = m.edge_history[count:]
                pairs = [(e["i"], e["j"]) for e in events]
                self.assertEqual(len(pairs), len(set(pairs)))
                degrees = np.zeros(m.p.N, int)
                for i, j in pairs:
                    self.assertLess(i, j)
                    self.assertTrue(before_active[i] and before_active[j])
                    self.assertNotIn(j, before_bl[i]); self.assertNotIn(i, before_bl[j])
                    degrees[i] += 1; degrees[j] += 1
                self.assertTrue((degrees <= m.p.a).all())
                row = m.agg_history[-1]
                self.assertLessEqual(row["H_active"], previous_h)
                self.assertLessEqual(row["N_active"], previous_n)
                previous_h, previous_n = row["H_active"], row["N_active"]
                for a, b in zip(before_bl, m.blacklist):
                    self.assertTrue(a <= b)

    def test_one_sided_blacklist_blocks_both_directions(self):
        m = MarketModel(Params(H=2, C=0, a=99))
        m.blacklist[0].add(1)
        self.assertEqual(m._draw_edges(), [])

    def test_sync_settlement_then_conversion(self):
        m = MarketModel(Params(H=2, C=1, p=1, q=99, seed=0, enable_bankrupt=False))
        m.theta[:] = [HONEST, CHEAT, HONEST]
        m._draw_edges = lambda: [(0, 1), (0, 2)]
        m.step()
        np.testing.assert_array_equal(m.w, [10, 12, 12])
        np.testing.assert_array_equal(m.theta, [CHEAT, CHEAT, HONEST])
        self.assertEqual(m.converted_total, 1)
        m._draw_edges = lambda: []
        m.step()
        self.assertEqual(m.theta[0], CHEAT)

    def test_default_payoffs_and_full_wealth_identity(self):
        for B in (False, True):
            for E in (False, True):
                m = MarketModel(Params(H=12, C=8, seed=3, enable_bankrupt=B, enable_evict=E), keep_edges=True)
                for _ in range(30):
                    before = m.w.sum()
                    if not m.step():
                        break
                    row = m.agg_history[-1]
                    surplus = 4*row["n_HH"]-2*row["n_CC"]
                    self.assertEqual(m.w.sum()-before, surplus)
                    self.assertEqual(row["surplus_t"], surplus)
                    self.assertEqual(m.w.sum()-200, row["cumulative_welfare"])
                    self.assertEqual(row["H_active"], m.p.H-row["converted_total"])
                    events = [e for e in m.edge_history if e["t"] == m.t]
                    self.assertEqual(sum(e["delta_w_i"]+e["delta_w_j"] for e in events), surplus)

    def test_exit_switches_and_simultaneous_labels(self):
        for B in (False, True):
            for E in (False, True):
                m = MarketModel(Params(H=2, C=0, c=0, enable_bankrupt=B, enable_evict=E))
                m.w[0] = -2; m.r[0] = 3
                m._check_exit_and_death(0, np.array([True, False]))
                self.assertEqual(bool(m.flag_bankrupt[0]), B)
                self.assertEqual(bool(m.flag_evict[0]), E)
                self.assertEqual(bool(m.active[0]), not (B or E))
                self.assertEqual(bool(m.alive[0]), not B)
                self.assertEqual(m.w[0], -2)
                if B or E:
                    self.assertEqual(m.exit_w[0], -2)
                    self.assertEqual(m.exit_t[0], 1)

    def test_consumption_exit_without_bankruptcy_is_counted(self):
        m = MarketModel(Params(H=2, C=0, w_init=1, c=2,
                               enable_bankrupt=False, enable_evict=False))
        m._draw_edges = lambda: []
        m.step()
        self.assertEqual(m.agg_history[-1]["exited_total"], 2)
        self.assertEqual(m.agg_history[-1]["labelled_exited_total"], 0)

    def test_evict_wealth_is_frozen_only_without_consumption(self):
        for c in (0, 1):
            m = MarketModel(Params(H=2, C=0, c=c, enable_bankrupt=False))
            m.r[0] = 3
            m._check_exit_and_death(0, np.zeros(2, bool))
            exit_w = m.exit_w[0]
            m._draw_edges = lambda: []
            m.step()
            self.assertEqual(m.exit_w[0], exit_w)
            self.assertEqual(m.w[0], exit_w-c)

    def test_reproducible_and_seed_changes_legal(self):
        p = Params(H=14, C=6, max_steps=20, seed=11)
        a = MarketModel(p, keep_edges=True).run()
        b = MarketModel(p, keep_edges=True).run()
        self.compare_state(a, b)
        self.assertEqual(a.agg_history, b.agg_history)
        self.assertEqual(a.edge_history, b.edge_history)
        other = MarketModel(replace(p, seed=12)).run()
        self.assertEqual(other.t, 20)
        self.assertNotEqual(a.agg_history, other.agg_history)

    def test_all_honest_all_cheaters_large_a_q1_and_no_edges(self):
        h = MarketModel(Params(H=5, C=0, a=99, q=1, max_steps=3)).run()
        self.assertEqual(h.agg_history[-1]["H_active"], 5)
        self.assertEqual(h.agg_history[-1]["n_edges"], 10)
        self.assertEqual(h.agg_history[-1]["cumulative_welfare"], 120)
        c = MarketModel(Params(H=0, C=5, a=99, q=1, w_init=100, max_steps=4)).run()
        self.assertEqual([r["n_edges"] for r in c.agg_history], [0, 10, 0, 0, 0])
        self.assertEqual(c.agg_history[-1]["cumulative_welfare"], -20)
        with self.assertRaises(ValueError):
            summarize_run(c, fixed_horizon_rows(c))

    def test_censoring_event_at_T_and_absorption_padding(self):
        survivor = MarketModel(Params(H=2, C=0, max_steps=3)).run()
        s = summarize_run(survivor, fixed_horizon_rows(survivor))
        self.assertEqual((s["collapse_event"], s["collapse_time"], s["right_censored"]), (0, 3, 1))
        m = MarketModel(Params(H=1, C=1, p=1, q=1, w_init=1, max_steps=3))
        m._draw_edges = lambda: [(0, 1)] if m.t == 0 else []
        m.run()
        rows = fixed_horizon_rows(m)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["N_active"] == 0 for r in rows[1:]))
        self.assertEqual([r["surplus_t"] for r in rows], [0, 0, 0, 0])
        final_event = MarketModel(Params(H=1, C=1, p=1, q=1, max_steps=3))
        final_event._draw_edges = lambda: [(0, 1)] if final_event.t == 2 else []
        final_event.run()
        s = summarize_run(final_event, fixed_horizon_rows(final_event))
        self.assertEqual((s["collapse_event"], s["collapse_time"], s["right_censored"]), (1, 3, 0))

    def test_ledger_changes_after_exit_do_not_change_primary_outcomes(self):
        # Counterfactual bookkeeping only, never used in production.
        for B in (False, True):
            for E in (False, True):
                p = Params(H=8, C=12, w_init=1, seed=9, max_steps=20,
                           enable_bankrupt=B, enable_evict=E)
                models = [MarketModel(p, keep_edges=True) for _ in range(3)]
                for _ in range(20):
                    for mode, m in enumerate(models):
                        m.step()
                        if mode >= 1:
                            m.exit_w[m.flag_bankrupt] = 0
                        if mode == 2:
                            m.w[m.flag_bankrupt] = 0
                    for alt in models[1:]:
                        np.testing.assert_array_equal(models[0].active, alt.active)
                        np.testing.assert_array_equal(models[0].theta, alt.theta)
                        self.assertEqual(models[0].edge_history, alt.edge_history)
                        self.assertEqual(models[0].agg_history[-1]["cumulative_welfare"], alt.agg_history[-1]["cumulative_welfare"])


if __name__ == "__main__":
    unittest.main()
