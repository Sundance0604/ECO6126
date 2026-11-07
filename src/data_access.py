"""Shared B–F inputs. These functions prepare data, not fitted analysis results."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .market import ROOT
from .provenance import digest, model_version

CONTEXT = ["model_version", "N", "rho", "a", "p", "q", "c", "T", "w_init",
           "g_HH", "g_HP_H", "g_HP_P", "g_PP", "E", "B"]


@dataclass
class ExperimentData:
    runs: pd.DataFrame
    steps: pd.DataFrame | None
    sources: list[dict]


def load_experiment(path=ROOT / "data/processed", *, with_steps=False):
    """Load a batch folder or a completed extension manifest; verify source hashes."""
    path = Path(path).resolve()
    if path.is_file():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete":
            raise ValueError("Extension collection is not complete")
        batches = []
        for b in manifest["batches"]:
            batch_path = (path.parent / b["path"]).resolve()
            if not batch_path.is_relative_to(path.parent):
                raise ValueError("Batch path escapes its experiment collection")
            if digest(batch_path / "metadata.json") != b["metadata_sha256"]:
                raise ValueError("Batch metadata changed after collection completion")
            batches.append(load_experiment(batch_path, with_steps=with_steps))
        runs = pd.concat([b.runs for b in batches], ignore_index=True)
        steps = pd.concat([b.steps for b in batches], ignore_index=True) if with_steps else None
        if runs.run_id.duplicated().any():
            raise ValueError("Overlapping runs in collection; do not double-count baseline cells")
        return ExperimentData(runs, steps, [s for b in batches for s in b.sources])
    meta_path = path / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("schema_version") != "1.0" or meta.get("status") != "complete":
        raise ValueError("Expected a complete schema 1.0 batch")
    if meta["model_version"] != model_version():
        raise ValueError("Model code differs from this dataset; use its recorded Git/model version")
    required = ["run_level.csv"] + (["step_level.csv"] if with_steps else [])
    for name in required:
        if digest(path / name) != meta["output_sha256"].get(name):
            raise ValueError(f"Data hash mismatch: {name}")
    runs = pd.read_csv(path / "run_level.csv")
    if not runs.run_id.is_unique or len(runs) != meta["actual_runs"]:
        raise ValueError("Invalid run IDs/count")
    if set(runs.model_version) != {meta["model_version"]}:
        raise ValueError("Mixed model versions")
    steps = pd.read_csv(path / "step_level.csv") if with_steps else None
    if steps is not None:
        if steps.duplicated(["run_id", "t"]).any() or set(steps.run_id) != set(runs.run_id):
            raise ValueError("Invalid step keys")
    location = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    return ExperimentData(runs, steps, [{"folder": location, "metadata_sha256": digest(meta_path),
                                         "model_version": meta["model_version"],
                                         "output_sha256": meta["output_sha256"]}])


def select_runs(data, **filters):
    """Filter scalar/list parameter values; no implicit conditioning on outcomes."""
    runs = data.runs
    for key, value in filters.items():
        if key not in CONTEXT + ["seed", "run_id"]:
            raise ValueError(f"Not a parameter/key filter: {key}")
        choices = value if isinstance(value, (list, tuple, set)) else [value]
        runs = runs.loc[runs[key].isin(choices)]
    return runs.copy()


def survival_inputs(runs):
    return runs[["run_id", "seed", *CONTEXT, "collapse_time", "collapse_event", "right_censored", "rmst_T"]].rename(
        columns={"collapse_time": "duration", "collapse_event": "event"}).copy()


def paired_inputs(runs, outcome, *, treatment="E"):
    """Match 0/1 treatments within seed and ALL remaining model parameters."""
    if treatment not in ("E", "B") or outcome not in runs.columns:
        raise ValueError("Expected E/B treatment and a known outcome")
    keys = ["seed"] + [k for k in CONTEXT if k != treatment]
    if runs.duplicated(keys + [treatment]).any():
        raise ValueError("Duplicate matched units")
    left = runs.loc[runs[treatment] == 0, keys + ["run_id", outcome]].rename(
        columns={"run_id": "control_run_id", outcome: "control"})
    right = runs.loc[runs[treatment] == 1, keys + ["run_id", outcome]].rename(
        columns={"run_id": "treated_run_id", outcome: "treated"})
    matched = left.merge(right, on=keys, how="outer", validate="one_to_one", indicator=True)
    if not (matched["_merge"] == "both").all() or matched.empty:
        raise ValueError("Missing treatment counterpart; filter to a balanced comparison first")
    matched = matched.drop(columns="_merge")
    matched["difference"] = matched.treated-matched.control
    return matched


def step_flows(data):
    """Step timing is end-of-round; convert cumulative counts to current flows."""
    if data.steps is None:
        raise ValueError("Reload with with_steps=True")
    s = data.steps.sort_values(["run_id", "t"]).copy()
    for cumulative, flow in (("converted_total", "converted_step"), ("bankrupt_total", "bankrupt_step"),
                             ("evicted_total", "evicted_step"), ("exited_total", "exited_step")):
        s[flow] = s.groupby("run_id")[cumulative].diff().fillna(0).astype(int)
        if (s[flow] < 0).any():
            raise ValueError(f"Nonmonotonic cumulative count: {cumulative}")
    return s.merge(data.runs[["run_id", "seed", *CONTEXT]], on="run_id", validate="many_to_one")


def welfare_components(runs):
    result = runs[["run_id", "seed", *CONTEXT, "welfare_T", "W_all_T", "W_active_T"]].copy()
    result["surplus_HH"] = 2*runs.g_HH*runs.total_HH
    result["surplus_HC"] = (runs.g_HP_H+runs.g_HP_P)*runs.total_HC
    result["surplus_CC"] = 2*runs.g_PP*runs.total_CC
    if not np.allclose(result[["surplus_HH", "surplus_HC", "surplus_CC"]].sum(axis=1), result.welfare_T):
        raise ValueError("Welfare decomposition does not reconcile")
    return result
