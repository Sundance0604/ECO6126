from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.prepare_member import prepare
from scripts.run_baseline import run
from scripts.run_extensions import execute, expand_plan
from scripts.validate_outputs import validate
from src.data_access import load_experiment, select_runs, survival_inputs, paired_inputs, step_flows, welfare_components
from src.market import ROOT
from src.provenance import write_json


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="eco6126_interfaces_")
        cls.root = Path(cls.temp.name)
        cls.config = json.loads((ROOT / "configs/baseline.json").read_text())
        cls.config.update(N=10, T=5, rho=[.1, .3], seeds=[0, 1])
        write_json(cls.root / "config.json", cls.config)
        with redirect_stdout(io.StringIO()):
            run(cls.root / "config.json", cls.root / "data")
        cls.data = load_experiment(cls.root / "data", with_steps=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_survival_and_complete_matching(self):
        r = select_runs(self.data, B=1)
        s = survival_inputs(r)
        np.testing.assert_array_equal(s.event, r.collapse_event)
        np.testing.assert_array_equal(s.duration, r.collapse_time)
        matched = paired_inputs(r, "rmst_T")
        self.assertEqual(len(matched), 4)
        self.assertTrue((matched.B == 1).all())
        with self.assertRaises(ValueError):
            paired_inputs(r.loc[r.E == 1], "rmst_T")
        with self.assertRaises(ValueError):
            paired_inputs(pd.concat([r, r.iloc[:1]]), "rmst_T")

    def test_mechanism_flows_and_welfare_reconcile(self):
        f = step_flows(self.data)
        totals = f.groupby("run_id").converted_step.sum()
        r = self.data.runs.set_index("run_id")
        np.testing.assert_array_equal(totals, r.loc[totals.index].converted_total)
        parts = welfare_components(self.data.runs)
        np.testing.assert_allclose(parts.surplus_HH+parts.surplus_HC+parts.surplus_CC, self.data.runs.welfare_T)

    def test_member_extracts_have_rows_and_provenance(self):
        for member in "BCDEF":
            output = self.root / ("member_"+member)
            with redirect_stdout(io.StringIO()):
                prepare(member, self.root / "data", output)
            meta = json.loads((output / "inputs_metadata.json").read_text())
            self.assertEqual(meta["stage"], "inputs_only_no_fitted_analysis")
            self.assertTrue(meta["sources"])
            self.assertTrue(all(count > 0 for count in meta["rows"].values()))
            with self.assertRaises(FileExistsError):
                prepare(member, self.root / "data", output)

    def test_plan_preview_does_not_execute(self):
        _, c = expand_plan(ROOT / "configs/experiments/C_thresholds.json")
        _, f = expand_plan(ROOT / "configs/experiments/F_robustness.json")
        self.assertEqual(sum(x["runs"] for x in c), 4000)
        self.assertEqual(sum(x["runs"] for x in f), 16000)
        self.assertEqual(len({x["config"]["q"] for x in c}), 8)

    def test_extensions_nondefault_payoffs_validate_and_load(self):
        plan = {"member": "F", "base_config": "config.json", "common": {"E": [1], "B": [1],
                "payoffs": {"g_HH": 1.8}}, "grid": {"q": [1, 2]}}
        write_json(self.root / "plan.json", plan)
        with redirect_stdout(io.StringIO()):
            manifest = execute(self.root / "plan.json", self.root / "extensions")
            for batch in json.loads(manifest.read_text())["batches"]:
                validate(manifest.parent / batch["path"])
        data = load_experiment(manifest, with_steps=True)
        self.assertEqual(len(data.runs), 8)
        self.assertEqual(set(data.runs.q), {1, 2})
        self.assertEqual(set(data.runs.g_HH), {1.8})
        parts = welfare_components(data.runs)
        self.assertTrue(np.allclose(parts.surplus_HC, 0))
        broken = json.loads(manifest.read_text())
        broken["status"] = "failed"
        write_json(self.root / "broken_manifest.json", broken)
        with self.assertRaises(ValueError):
            load_experiment(self.root / "broken_manifest.json")


if __name__ == "__main__":
    unittest.main()
