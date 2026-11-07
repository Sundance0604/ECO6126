"""Record-only adapter around the unchanged original simulator."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "natural_consumption_HCtrading.py"
_NAME = "_eco6126_original_v15"
if _NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_NAME, SOURCE)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_NAME] = _module
    _spec.loader.exec_module(_module)
original = sys.modules[_NAME]
Params = original.Params
HONEST, CHEAT = original.HONEST, original.CHEAT


class MarketModel(original.MarketModel):
    """Only record names/times change. Matching, settlement and exits are inherited."""

    def __init__(self, params: Params, *, keep_edges=False, keep_individuals=False):
        self.keep_edges = keep_edges
        self.keep_individuals = keep_individuals
        super().__init__(params)

    def _record_individuals(self):
        if self.keep_individuals:
            super()._record_individuals()

    def _record_aggregate(self, n_edges, by_type):
        super()._record_aggregate(n_edges, by_type)
        row = self.agg_history[-1]
        row["C_active"] = row.pop("P_active")
        row["n_HC"] = row.pop("n_HP")
        row["n_CC"] = row.pop("n_PP")
        row["labelled_exited_total"] = row["exited_total"]
        row["exited_total"] = int((~self.active).sum())
        row["W_evict_current"] = row.pop("W_evict_frozen")
        row["W_evict_exit_raw"] = float(np.nansum(self.exit_w[self.flag_evict]))
        row["W_bankrupt_exit_raw"] = float(np.nansum(self.exit_w[self.flag_bankrupt]))
        row["W_all"] = float(self.w.sum())
        row["surplus_t"] = float(
            2 * self.p.g_HH * row["n_HH"]
            + (self.p.g_HP_H + self.p.g_HP_P) * row["n_HC"]
            + 2 * self.p.g_PP * row["n_CC"]
        )
        previous = self.agg_history[-2]["cumulative_welfare"] if self.t else 0.0
        row["cumulative_welfare"] = previous + row["surplus_t"]

    def step(self):
        old_count = len(self.edge_history)
        result = super().step()
        # Original event t=k is the transition from k to k+1.
        for event in self.edge_history[old_count:]:
            event["t_start"] = event["t"]
            event["t_end"] = event["t"] + 1
            event["t"] = event["t_end"]
        if not self.keep_edges:
            self.edge_history.clear()
        return result
