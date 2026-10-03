"""Execute the workflow's actual Bash transaction in an isolated fixture tree.

External test/build tools are deliberately stubbed here to inject failure at each
boundary. The real data/application test suites are run separately by CI.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class CandidateTransaction(unittest.TestCase):
    def setUp(self):
        workflow = yaml.load((ROOT / ".github/workflows/daily-data.yml").read_text(), Loader=yaml.BaseLoader)
        self.command = next(s["run"] for s in workflow["jobs"]["refresh"]["steps"] if s.get("id") == "validate")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runner = self.root / "runner"
        self.runner.mkdir()
        self.data = self.root / "public/data"
        self.data.mkdir(parents=True)
        self.candidate = self.runner / "data-candidate"
        self.candidate.mkdir()
        (self.root / "scripts").mkdir()
        self.evidence = self.root / "scripts/uldk-cache.json"
        self.evidence.write_text("original-evidence-fixture")
        (self.runner / "uldk-cache-candidate.json").write_text("candidate-evidence-fixture")
        for filename in ("permits.json", "parcels.geojson", "metadata.json"):
            (self.data / filename).write_text("original-fixture:" + filename)
            (self.candidate / filename).write_text("candidate-fixture:" + filename)
        tools = self.root / "bin"
        tools.mkdir()
        for name in ("python", "npm"):
            path = tools / name
            path.write_text('#!/bin/sh\ncase "$*" in\n  "$FAIL_COMMAND") exit 23 ;;\nesac\nexit 0\n')
            path.chmod(0o700)
        self.env = dict(os.environ, RUNNER_TEMP=str(self.runner), PATH=str(tools) + os.pathsep + os.environ["PATH"])

    def execute(self, failure):
        return subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", self.command], cwd=self.root, env=dict(self.env, FAIL_COMMAND=failure), capture_output=True, text=True, check=False)

    def test_candidate_is_kept_only_when_all_gates_pass(self):
        result = self.execute("no matching command")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.evidence.read_text(), "candidate-evidence-fixture")
        for filename in ("permits.json", "parcels.geojson", "metadata.json"):
            self.assertEqual((self.data / filename).read_text(), "candidate-fixture:" + filename)
        self.assertTrue((self.runner / "original-public-data").is_dir())

    def test_data_validation_failure_restores_all_three_original_files(self):
        self.assert_rollback("-m unittest discover -s tests/data -v")

    def test_application_test_failure_restores_all_three_original_files(self):
        self.assert_rollback("test")

    def test_build_failure_restores_all_three_original_files(self):
        self.assert_rollback("run build")

    def test_artifact_privacy_failure_restores_all_three_original_files(self):
        self.assert_rollback("tests/workflows/check_dist.py")

    def assert_rollback(self, failure):
        result = self.execute(failure)
        self.assertNotEqual(result.returncode, 0, "The transaction must fail, not swallow the gate's error")
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.evidence.read_text(), "original-evidence-fixture")
        for filename in ("permits.json", "parcels.geojson", "metadata.json"):
            self.assertEqual((self.data / filename).read_text(), "original-fixture:" + filename)
        self.assertFalse((self.runner / "original-public-data").exists())


if __name__ == "__main__":
    unittest.main()
