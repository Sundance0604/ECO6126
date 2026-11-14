"""Concatenate the eight extension batches into data/q_grid_run_level.csv.

The extension runner writes one directory per threshold; this script stacks them
and checks that the resulting grid is complete before anything is analysed.
"""
from __future__ import annotations

import glob
import os
import shutil

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "extensions", "C")
OUT = os.path.join(ROOT, "data", "processed", "q_grid_run_level.csv")


def main() -> None:
    batches = sorted(glob.glob(os.path.join(SRC, "*_grid")))
    if not batches:
        raise SystemExit(f"no batches under {SRC}; run run_extensions first")
    frames = [pd.read_csv(os.path.join(b, "run_level.csv")) for b in batches]
    df = pd.concat(frames, ignore_index=True)

    n_q, n_rho, n_seed = df.q.nunique(), df.rho.nunique(), df.seed.nunique()
    expected = n_q * n_rho * n_seed
    print(f"{len(batches)} batches, {len(df)} runs "
          f"({n_q} q x {n_rho} rho x {n_seed} seeds = {expected})")
    if len(df) != expected or df.duplicated(["q", "rho", "seed"]).any():
        raise SystemExit("grid is incomplete or has duplicate runs")
    if df.E.nunique() != 1 or df.B.nunique() != 1:
        raise SystemExit("extension should hold one institution")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    shutil.copy(os.path.join(SRC, "manifest.json"),
                os.path.join(ROOT, "data", "processed", "manifest.json"))
    print("wrote", OUT, f"{os.path.getsize(OUT)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
