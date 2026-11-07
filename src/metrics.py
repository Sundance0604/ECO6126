"""Single definitions of fixed-horizon outputs; no economic state is modified."""
from __future__ import annotations

from .market import MarketModel


def fixed_horizon_rows(model: MarketModel):
    """Include initial state and carry a c=0 inactive absorbing state through T."""
    rows = [dict(row, absorbed_padding=0) for row in model.agg_history]
    if not rows or rows[0]["t"] != 0:
        raise ValueError("Initial state missing")
    if model.t < model.p.max_steps:
        if model.p.c != 0 or model.active.any():
            raise ValueError("Only inactive c=0 absorption can be padded")
        for t in range(model.t + 1, model.p.max_steps + 1):
            row = dict(rows[-1], t=t, absorbed_padding=1)
            for key in ("n_edges", "n_HH", "n_HC", "n_CC", "surplus_t"):
                row[key] = 0
            rows.append(row)
    if [row["t"] for row in rows] != list(range(model.p.max_steps + 1)):
        raise ValueError("Incomplete or duplicate observation times")
    return rows


def summarize_run(model: MarketModel, rows):
    p = model.p
    if p.H <= 0:
        raise ValueError("Collapse relative to H0 requires H0>0")
    hits = [r["t"] for r in rows if 10 * r["H_active"] <= p.H]
    event = int(bool(hits))
    time = hits[0] if hits else p.max_steps
    end = rows[-1]
    return {
        "collapse_event": event,
        "right_censored": 1 - event,
        "collapse_time": time,
        "rmst_T": time,
        "welfare_T": sum(r["surplus_t"] for r in rows[1:]),
        "total_HH": sum(r["n_HH"] for r in rows[1:]),
        "total_HC": sum(r["n_HC"] for r in rows[1:]),
        "total_CC": sum(r["n_CC"] for r in rows[1:]),
        "total_trades": sum(r["n_edges"] for r in rows[1:]),
        "no_trade_steps": sum(r["n_edges"] == 0 for r in rows[1:]),
        "simulated_steps": model.t,
        "padded_steps": p.max_steps - model.t,
        "H_active_T": end["H_active"],
        "C_active_T": end["C_active"],
        "N_active_T": end["N_active"],
        "W_all_T": end["W_all"],
        "W_active_T": end["W_active"],
        "W_evict_exit_raw_T": end["W_evict_exit_raw"],
        "W_bankrupt_exit_raw_T": end["W_bankrupt_exit_raw"],
        **{k: end[k] for k in ("converted_total", "bankrupt_total", "evicted_total", "both_total", "exited_total")},
    }
