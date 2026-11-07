"""Preview a member experiment plan; execution requires --execute.

Reuses the same simulator, metrics, seed protocol and batch schema as A.
No B–F statistical analyses are fitted here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import itertools
import json
from pathlib import Path
import re

from scripts.run_baseline import run
from src.market import ROOT
from src.provenance import canonical_hash, digest, now, write_json


def patch_config(base, changes):
    result = deepcopy(base)
    for key, value in changes.items():
        if key not in base:
            raise ValueError(f"Unknown config field: {key}")
        if key == "payoffs":
            if set(value)-set(base["payoffs"]):
                raise ValueError("Unknown payoff field")
            result[key].update(value)
        else:
            result[key] = value
    if result["c"] != 0 or result["wealth_ledger"] != "original_raw_confirmed_A":
        raise ValueError("Extensions retain c=0 and the approved ledger")
    return result


def expand_plan(plan_path, *, smoke=False):
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    base_path = (plan_path.parent / plan["base_config"]).resolve()
    base = patch_config(json.loads(base_path.read_text(encoding="utf-8")), plan.get("common", {}))
    grid = plan.get("grid", {})
    if set(grid)-{"N", "a", "p", "q", "T", "w_init"}:
        raise ValueError("Grid varies scalar parameters; put E/B/rho/seeds lists in common")
    if any(not isinstance(v, list) or not v for v in grid.values()):
        raise ValueError("Each grid dimension needs a nonempty list")
    names = list(grid)
    cells = []
    for scenario in plan.get("scenarios", [{"name": "grid", "overrides": {}}]):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", scenario["name"]):
            raise ValueError("Scenario names must be simple directory-safe identifiers")
        for values in itertools.product(*(grid[k] for k in names)):
            config = patch_config(patch_config(base, scenario.get("overrides", {})), dict(zip(names, values)))
            if smoke:
                config["seeds"] = config["seeds"][:2]
                config["rho"] = config["rho"][:2]
            count = len(config["seeds"])*len(config["rho"])*len(config["E"])*len(config["B"])
            cells.append({"name": f"{len(cells):03d}_{scenario['name']}", "config": config, "runs": count})
    if smoke:
        cells = cells[:2]
    if not cells or len({canonical_hash(c["config"]) for c in cells}) != len(cells):
        raise ValueError("Empty or duplicate experiment cells")
    return plan, cells


def execute(plan_path, out, *, smoke=False, workers=1):
    plan_path, out = Path(plan_path).resolve(), Path(out).resolve()
    plan, cells = expand_plan(plan_path, smoke=smoke)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Use an empty extension output directory; baseline is never overwritten")
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "1.0", "member": plan["member"], "status": "running",
                "smoke": smoke, "started_at": now(), "plan_sha256": digest(plan_path),
                "plan": plan, "batches": [], "expected_runs": sum(c["runs"] for c in cells)}
    write_json(out / "manifest.json", manifest)
    try:
        for cell in cells:
            batch = out / cell["name"]
            batch.mkdir()
            write_json(batch / "config.json", cell["config"])
            run(batch / "config.json", batch, workers=workers)
            manifest["batches"].append({"path": cell["name"], "runs": cell["runs"],
                                         "metadata_sha256": digest(batch / "metadata.json")})
            write_json(out / "manifest.json", manifest)
        manifest.update(status="complete", finished_at=now())
    except BaseException as error:
        manifest.update(status="failed", error=repr(error), finished_at=now())
        raise
    finally:
        write_json(out / "manifest.json", manifest)
    return out / "manifest.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    plan, cells = expand_plan(args.plan, smoke=args.smoke)
    print(json.dumps({"member": plan["member"], "cells": len(cells), "runs": sum(c["runs"] for c in cells),
                      "mode": "execute" if args.execute else "preview_only",
                      "settings": [{"name": c["name"], "N": c["config"]["N"], "q": c["config"]["q"],
                                    "a": c["config"]["a"], "p": c["config"]["p"], "T": c["config"]["T"],
                                    "runs": c["runs"]} for c in cells]}, ensure_ascii=False, indent=2))
    if args.execute:
        suffix = "_smoke" if args.smoke else ""
        execute(args.plan, args.out or ROOT / "data/extensions" / (plan["member"]+suffix),
                smoke=args.smoke, workers=args.workers)
