"""Verify grid, time alignment, accounting and run/step consistency."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.provenance import digest, model_version, now, write_json


def validate(folder):
    folder = Path(folder)
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert meta["status"] == "complete", "Incomplete run batch"
    assert model_version() == meta["model_version"], "Model source changed since simulation"
    for name, expected in meta["output_sha256"].items():
        assert digest(folder / name) == expected, f"Output hash mismatch: {name}"
    runs = pd.read_csv(folder / "run_level.csv")
    steps = pd.read_csv(folder / "step_level.csv")
    c = meta["config"]
    expected = set(itertools.product(c["rho"], c["seeds"], c["E"], c["B"]))
    actual = list(runs[["rho", "seed", "E", "B"]].itertuples(index=False, name=None))
    assert len(actual) == len(expected) and set(actual) == expected, "Grid missing or duplicate"
    assert runs.run_id.is_unique and len(runs) == meta["actual_runs"]
    assert set(steps.run_id) == set(runs.run_id)
    assert set(runs.model_version) == {meta["model_version"]}
    assert (runs.H0 + runs.C0 == c["N"]).all()
    assert np.allclose(runs.C0 / runs.N, runs.rho)
    assert (runs.c == 0).all() and (runs["T"] == c["T"]).all()
    for key in ("N", "a", "p", "q", "w_init"):
        assert np.allclose(runs[key], c[key]), f"Parameter mismatch: {key}"
    for key, value in c["payoffs"].items():
        assert np.allclose(runs[key], value), f"Payoff mismatch: {key}"
    assert len(steps) == len(runs) * (c["T"] + 1)
    assert (steps.N_active == steps.H_active + steps.C_active).all()
    assert (steps.n_edges == steps.n_HH + steps.n_HC + steps.n_CC).all()
    pay = c["payoffs"]
    assert np.allclose(steps.surplus_t, 2*pay["g_HH"]*steps.n_HH
                       + (pay["g_HP_H"]+pay["g_HP_P"])*steps.n_HC + 2*pay["g_PP"]*steps.n_CC)
    assert (steps.exited_total + steps.N_active == c["N"]).all()
    assert (steps.labelled_exited_total == steps.exited_total).all()
    assert (steps.bankrupt_total + steps.evicted_total - steps.both_total == steps.exited_total).all()
    assert np.allclose(steps.W_all - c["N"]*c["w_init"], steps.cumulative_welfare)
    by_id = runs.set_index("run_id")
    for run_id, s in steps.groupby("run_id", sort=False):
        r = by_id.loc[run_id]
        assert np.array_equal(s.t.to_numpy(), np.arange(c["T"] + 1))
        assert (s.H_active.diff().dropna() <= 0).all()
        assert (s.N_active.diff().dropna() <= 0).all()
        assert (s.converted_total.diff().dropna() >= 0).all()
        assert np.allclose(s.cumulative_welfare, s.surplus_t.cumsum())
        initial = s.iloc[0]
        assert initial.H_active == r.H0 and initial.C_active == r.C0
        if c["p"] == 3 and c["w_init"] == 10 and c["payoffs"] == {"g_HH": 2.0, "g_HP_H": -2.0, "g_HP_P": 2.0, "g_PP": -1.0}:
            assert (s.H_active == r.H0-s.converted_total).all(), "Honest-base conversion identity"
        hits = s.loc[10*s.H_active <= r.H0, "t"]
        event = int(len(hits) > 0)
        time = int(hits.iloc[0]) if event else int(r["T"])
        assert r.collapse_event == event and r.right_censored == 1-event
        assert r.collapse_time == time and r.rmst_T == time
        assert np.isclose(r.welfare_T, s.surplus_t.sum())
        for suffix in ("HH", "HC", "CC"):
            assert r[f"total_{suffix}"] == s[f"n_{suffix}"].sum()
        assert r.total_trades == s.n_edges.sum()
        assert r.no_trade_steps == (s.loc[s.t > 0, "n_edges"] == 0).sum()
        end = s.iloc[-1]
        for k in ("H_active", "C_active", "N_active", "W_all", "W_active"):
            assert np.isclose(r[f"{k}_T"], end[k])
    edge_rows = None
    if (folder / "edge_level.csv.gz").exists():
        edges = pd.read_csv(folder / "edge_level.csv.gz")
        edge_rows = len(edges)
        assert (edges.t == edges.t_end).all() and (edges.t_end == edges.t_start + 1).all()
        assert (edges.i < edges.j).all()
        assert not edges.duplicated(["run_id", "t", "i", "j"]).any()
        assert edges.t.between(1, c["T"]).all()
        assert set(edges.run_id) <= set(runs.run_id)
        edges["net"] = edges.delta_w_i + edges.delta_w_j
        totals = edges.groupby(["run_id", "t"]).agg(edge_count=("i", "size"), surplus=("net", "sum"))
        aligned = steps.set_index(["run_id", "t"]).join(totals).fillna({"edge_count": 0, "surplus": 0})
        assert np.array_equal(aligned.n_edges, aligned.edge_count)
        assert np.allclose(aligned.surplus_t, aligned.surplus)
    result = {"status": "passed", "checked_at": now(), "run_rows": len(runs),
              "step_rows": len(steps), "distinct_seeds": int(runs.seed.nunique()),
              "checks": ["hashes", "complete factorial grid", "unique run IDs", "all state times",
                         "population monotonicity", "exit labels", "wealth/surplus conservation",
                         "event/censoring", "run/step aggregation", "honest-base conversion identity"],
              "edge_rows_if_exported": edge_rows,
              "data_sha256": meta["output_sha256"]}
    write_json(folder / "validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return runs, steps, meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/processed"))
    validate(parser.parse_args().data)
