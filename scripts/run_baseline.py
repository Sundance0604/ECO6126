"""python -m scripts.run_baseline [--smoke] [--edges]"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import itertools
import json
from pathlib import Path
import time

import numpy as np

from src.market import MarketModel, Params, ROOT
from src.metrics import fixed_horizon_rows, summarize_run
from src.provenance import canonical_hash, environment, model_version, now, source_hashes, write_json, digest


def simulate_unit(job):
    config, version, rho, seed, E, B, edges = job
    n = config["N"]
    C = round(n * rho)
    p = Params(H=n-C, C=C, a=config["a"], p=config["p"], q=config["q"],
               w_init=config["w_init"], c=0, max_steps=config["T"], seed=seed,
               enable_evict=bool(E), enable_bankrupt=bool(B), **config["payoffs"])
    unit = {"N": n, "H0": n-C, "C0": C, "rho": rho, "a": p.a, "p": p.p,
            "q": p.q, "E": E, "B": B, "c": p.c, "T": p.max_steps,
            "w_init": p.w_init, "seed": seed, **config["payoffs"]}
    run_id = version + "-" + canonical_hash(unit)[:24]
    model = MarketModel(p, keep_edges=edges).run()
    rows = fixed_horizon_rows(model)
    summary = summarize_run(model, rows)
    expected_surplus = (2*p.g_HH*summary["total_HH"]
                        + (p.g_HP_H+p.g_HP_P)*summary["total_HC"]
                        + 2*p.g_PP*summary["total_CC"])
    if not np.isclose(summary["welfare_T"], expected_surplus):
        raise AssertionError("Payoff identity failed")
    if not np.isclose(summary["W_all_T"] - n*p.w_init, summary["welfare_T"]):
        raise AssertionError("State wealth accounting failed")
    return {"run_id": run_id, "model_version": version, **unit, **summary}, rows, model.edge_history


def simulate_units(jobs, workers):
    if workers == 1:
        yield from map(simulate_unit, jobs)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Ordered output, independent RNG per run, identical results to serial.
            yield from executor.map(simulate_unit, jobs, chunksize=1)


def run(config_path, out, *, smoke=False, edges=False, overwrite=False, workers=1):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if smoke:
        config = dict(config, rho=[0.10, 0.30], seeds=config["seeds"][:3])
    if workers < 1:
        raise ValueError("workers must be positive")
    if config["c"] != 0 or config["wealth_ledger"] != "original_raw_confirmed_A":
        raise ValueError("A baseline requires c=0 and the confirmed raw ledger")
    n = config["N"]
    for rho in config["rho"]:
        if not np.isclose(n * rho, round(n * rho)):
            raise ValueError("N*rho must be integer; no implicit rounding")
    units = list(itertools.product(config["rho"], config["seeds"], config["E"], config["B"]))
    if len(units) != len(set(units)) or not units:
        raise ValueError("Duplicate or empty experimental grid")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "run_level.csv").exists() and not overwrite:
        raise FileExistsError("Existing results: choose another --out or use --overwrite")
    version = model_version()
    config_hash = canonical_hash(config)
    metadata = {"schema_version": "1.0", "model_version": version, "config": config,
                "config_sha256": config_hash, "source_sha256": source_hashes(),
                "environment": environment(), "started_at": now(), "smoke": smoke,
                "expected_runs": len(units), "status": "running", "workers": workers,
                "wealth_decision": "A confirmed by user: state and exit record retain raw negative values",
                "event_time": "edge t=t_end=t_start+1; step t is end-of-round state",
                "seed_interpretation": "shared-seed blocks, not identical per-step shocks"}
    write_json(out / "metadata.json", metadata)
    started = time.perf_counter()
    edge_file = gzip.open(out / "edge_level.csv.gz", "wt", encoding="utf-8", newline="") if edges else None
    edge_writer = None
    try:
        with (out / "run_level.csv").open("w", encoding="utf-8", newline="") as rf, \
                (out / "step_level.csv").open("w", encoding="utf-8", newline="") as sf:
            rw = sw = None
            jobs = ((config, version, rho, seed, E, B, edges) for rho, seed, E, B in units)
            for index, (runrow, rows, events) in enumerate(simulate_units(jobs, workers), 1):
                run_id = runrow["run_id"]
                if rw is None:
                    rw = csv.DictWriter(rf, fieldnames=list(runrow)); rw.writeheader()
                rw.writerow(runrow)
                for row in rows:
                    steprow = {"run_id": run_id, **row}
                    if sw is None:
                        sw = csv.DictWriter(sf, fieldnames=list(steprow)); sw.writeheader()
                    sw.writerow(steprow)
                if edges:
                    for event in events:
                        erow = {"run_id": run_id, **event}
                        if edge_writer is None:
                            edge_writer = csv.DictWriter(edge_file, fieldnames=list(erow)); edge_writer.writeheader()
                        edge_writer.writerow(erow)
                if index == 1 or index % 50 == 0 or index == len(units):
                    print(f"{index}/{len(units)} runs; elapsed={time.perf_counter()-started:.1f}s", flush=True)
        metadata.update(status="complete", actual_runs=len(units), finished_at=now(),
                        elapsed_seconds=round(time.perf_counter()-started, 3))
    except BaseException as error:
        metadata.update(status="failed", error=repr(error), finished_at=now())
        raise
    finally:
        if edge_file:
            edge_file.close()
        metadata["output_sha256"] = {p.name: digest(p) for p in sorted(out.glob("*.csv*"))}
        write_json(out / "metadata.json", metadata)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/baseline.json")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--edges", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    output = args.out or ROOT / "data" / ("smoke" if args.smoke else "processed")
    run(args.config, output, smoke=args.smoke, edges=args.edges, overwrite=args.overwrite, workers=args.workers)
