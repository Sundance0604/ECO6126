"""Extract B–F inputs: python -m scripts.prepare_member --member B [--data ...]."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.data_access import load_experiment, survival_inputs, step_flows, welfare_components
from src.market import ROOT
from src.provenance import digest, now, source_hashes, write_json


def prepare(member, data_path, out):
    if member not in "BCDEF" or len(member) != 1:
        raise ValueError("Choose B, C, D, E or F")
    data = load_experiment(data_path, with_steps=member == "E")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Choose an empty member input directory")
    out.mkdir(parents=True, exist_ok=True)
    if member == "B":
        frames = {"survival_inputs.csv": survival_inputs(data.runs)}
    elif member in "CD":
        frames = {"run_inputs.csv": data.runs}
    elif member == "E":
        flows = step_flows(data)
        keep = ["run_id", "seed", "rho", "E", "B", "q", "t", "H_active", "C_active", "N_active",
                "n_edges", "n_HH", "n_HC", "n_CC", "converted_step", "bankrupt_step", "evicted_step",
                "exited_step", "surplus_t", "cumulative_welfare"]
        frames = {"mechanism_runs.csv": data.runs, "mechanism_steps.csv": flows[keep]}
    else:
        frames = {"welfare_inputs.csv": welfare_components(data.runs)}
    for name, frame in frames.items():
        frame.to_csv(out / name, index=False)
    write_json(out / "inputs_metadata.json", {
        "member": member, "generated_at": now(), "stage": "inputs_only_no_fitted_analysis",
        "sources": data.sources, "source_sha256": source_hashes(),
        "output_sha256": {name: digest(out / name) for name in frames},
        "rows": {name: len(frame) for name, frame in frames.items()},
        "inference_block": "seed jointly across all matched configurations and institutions",
    })
    print(f"{member} inputs saved: {out}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--member", choices=list("BCDEF"), required=True)
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    prepare(args.member, args.data, args.out or ROOT / "outputs" / args.member / "inputs")
