"""Small end-to-end checks of observation time, output schema and corruption detection."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from scripts.run_baseline import run
from scripts.validate_outputs import validate
from src.market import ROOT
from src.provenance import digest, write_json


class PipelineTests(unittest.TestCase):
    def test_export_validate_and_reject_logical_corruption(self):
        config = json.loads((ROOT / "configs/baseline.json").read_text())
        config.update(N=10, T=4, rho=[.1, .3], seeds=[0, 1])
        with tempfile.TemporaryDirectory(prefix="eco6126_test_") as temp:
            folder = Path(temp)
            config_path = folder / "config.json"
            write_json(config_path, config)
            with redirect_stdout(io.StringIO()):
                run(config_path, folder / "outputs")
                runs, steps, meta = validate(folder / "outputs")
            self.assertEqual(len(runs), 16)
            self.assertEqual(len(steps), 80)
            # Update the file digest as well: semantic validation must still fail.
            path = folder / "outputs/run_level.csv"
            runs.loc[0, "collapse_event"] = 1-int(runs.loc[0, "collapse_event"])
            runs.to_csv(path, index=False)
            meta["output_sha256"]["run_level.csv"] = digest(path)
            write_json(folder / "outputs/metadata.json", meta)
            with self.assertRaises(AssertionError):
                validate(folder / "outputs")


if __name__ == "__main__":
    unittest.main()
