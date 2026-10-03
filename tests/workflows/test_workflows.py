"""Offline contracts for the Actions publication/privacy boundary."""
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
DATA = {"public/data/permits.json", "public/data/parcels.geojson", "public/data/metadata.json"}
MAIN = "github.ref == 'refs/heads/main'"
PAGES = "vars.PAGES_ENABLED == 'true'"


class WorkflowContracts(unittest.TestCase):
    def load(self, name):
        path = WORKFLOWS / name
        self.assertTrue(path.is_file(), f"Missing workflow: {name}")
        # GitHub uses YAML 1.2: BaseLoader preserves the event key 'on'.
        return yaml.load(path.read_text(), Loader=yaml.BaseLoader)

    def test_ci_covers_push_pull_requests_and_manual_runs(self):
        workflow = self.load("ci-pages.yml")
        self.assertEqual(workflow["on"]["push"]["branches"], ["main"])
        self.assertEqual(workflow["on"]["pull_request"]["branches"], ["main"])
        self.assertIn("workflow_dispatch", workflow["on"])
        self.assertNotIn("pull_request_target", workflow["on"])
        commands = "\n".join(s.get("run", "") for s in workflow["jobs"]["build"]["steps"])
        for command in ("npm ci", "npm test", "npm run build", "python -m unittest discover -s tests/data -v", "python -m unittest discover -s tests/workflows -v", "python tests/workflows/check_dist.py"):
            self.assertIn(command, commands)

    def test_daily_import_refreshes_sources_without_geometry_cap(self):
        workflow = self.load("daily-data.yml")
        self.assertEqual(workflow["on"]["schedule"], [{"cron": "23 3 * * *"}])
        self.assertIn("workflow_dispatch", workflow["on"])
        job = workflow["jobs"]["refresh"]
        self.assertIn(MAIN, job["if"])
        commands = "\n".join(s.get("run", "") for s in job["steps"])
        for value in ("scripts/import_data.py", "--refresh-sources", "--max-parcels 0", "--workers 4", "--since 2025-01-01", "--until", "date -u +%F", "$RUNNER_TEMP", "data-candidate", "--output"):
            self.assertIn(value, commands)
        self.assertNotIn("--offline", commands)
        self.assertNotIn("--refresh ", commands)

    def test_shared_main_lock_without_nested_job_lock(self):
        ci = self.load("ci-pages.yml")
        daily = self.load("daily-data.yml")
        self.assertEqual(ci["concurrency"], daily["concurrency"])
        self.assertIn(MAIN, ci["concurrency"]["group"])
        self.assertIn("main-data-and-pages", ci["concurrency"]["group"])
        self.assertEqual(ci["concurrency"]["cancel-in-progress"], "false")
        self.assertEqual(ci["concurrency"].get("queue"), "max", "Daily import must not replace/be replaced by a pending CI run")
        for workflow in (ci, daily):
            for job in workflow["jobs"].values():
                self.assertNotIn("concurrency", job)

    def test_only_successful_tests_and_build_can_commit(self):
        workflow = self.load("daily-data.yml")
        steps = workflow["jobs"]["refresh"]["steps"]
        imported = next(i for i, s in enumerate(steps) if s.get("id") == "import")
        validated = next(i for i, s in enumerate(steps) if s.get("id") == "validate")
        commit = next(i for i, s in enumerate(steps) if s.get("id") == "snapshot")
        self.assertLess(imported, validated)
        self.assertLess(validated, commit)
        validator = steps[validated]["run"]
        for value in ("trap", "original-public-data", "python -m unittest discover -s tests/data -v", "npm test", "npm run build", "check_dist.py"):
            self.assertIn(value, validator)
        step = steps[commit]
        self.assertIn(MAIN, step["if"])
        self.assertNotIn("always()", step["if"])
        command = step["run"]
        self.assertIn("git commit", command)
        self.assertIn("HEAD:refs/heads/main", command)
        self.assertNotIn("--force", command)
        self.assertNotRegex(command, r"git add\s+(?:-A|\.)\s")
        for filename in DATA:
            self.assertIn(filename, command)
        self.assertIn("gh api", command, "Push must be read back before publication")
        self.assertIn("refs/heads/main", command)

    def test_private_ci_does_not_configure_upload_or_deploy_pages(self):
        for name in ("ci-pages.yml", "daily-data.yml"):
            workflow = self.load(name)
            for job in workflow["jobs"].values():
                for step in job.get("steps", []):
                    action = step.get("uses", "").split("@", 1)[0]
                    if action in {"actions/configure-pages", "actions/upload-pages-artifact"}:
                        self.assertIn(MAIN, step["if"])
                        self.assertIn(PAGES, step["if"])
                    if action == "actions/configure-pages":
                        self.assertEqual(step["with"]["enablement"], "false")
                    if action == "actions/upload-pages-artifact":
                        self.assertEqual(step["with"]["path"], "dist/")
                        self.assertEqual(step["with"]["retention-days"], "1")
            deploy = workflow["jobs"]["deploy"]
            self.assertIn(MAIN, deploy["if"])
            self.assertIn(PAGES, deploy["if"])
            self.assertEqual(deploy["environment"]["name"], "github-pages")
            self.assertEqual(deploy["permissions"], {"contents": "read", "pages": "write", "id-token": "write"})
            self.assertIn("needs", deploy)
            steps = deploy["steps"]
            self.assertTrue(any(s.get("id") == "current" and "gh api" in s.get("run", "") for s in steps))
            publish = next(s for s in steps if s.get("uses", "").startswith("actions/deploy-pages@"))
            self.assertIn("steps.current.outputs.current == 'true'", publish["if"])

    def test_daily_deploy_is_in_the_same_run_as_data_commit(self):
        workflow = self.load("daily-data.yml")
        self.assertEqual(workflow["jobs"]["deploy"]["needs"], "refresh")
        commands = "\n".join(s.get("run", "") for s in workflow["jobs"]["deploy"]["steps"])
        self.assertIn("needs.refresh.outputs.snapshot", str(workflow["jobs"]["deploy"]))
        self.assertNotIn("workflow_dispatch", commands)
        self.assertNotIn("repository_dispatch", commands)

    def test_staging_preserves_baseline_checks_and_only_public_uldk_evidence(self):
        workflow = self.load("daily-data.yml")
        steps = workflow["jobs"]["refresh"]["steps"]
        importer = next(s for s in steps if s.get("id") == "import")["run"]
        self.assertIn('cp -a public/data "$RUNNER_TEMP/data-candidate"', importer)
        self.assertIn('scripts/uldk-cache.json', importer)
        self.assertIn('--uldk-public-cache "$RUNNER_TEMP/uldk-cache-candidate.json"', importer)
        snapshot = next(s for s in steps if s.get("id") == "snapshot")["run"]
        self.assertIn('scripts/uldk-cache.json', snapshot)
        validator = next(s for s in steps if s.get("id") == "validate")["run"]
        self.assertIn('cp "$RUNNER_TEMP/uldk-cache-candidate.json" scripts/uldk-cache.json', validator)
        self.assertLess(validator.index('cp "$RUNNER_TEMP/uldk-cache-candidate.json"'), validator.index('python -m unittest discover -s tests/data -v'))

    def test_actions_are_pinned_and_raw_inputs_never_cached_or_uploaded(self):
        expected = {
            "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",
            "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
            "actions/configure-pages": "45bfe0192ca1faeb007ade9deae92b16b8254a0d",
            "actions/upload-pages-artifact": "fc324d3547104276b827a68afc52ff2a11cc49c9",
            "actions/deploy-pages": "368f82528645a54fb793d4d04e342629a3f51346",
        }
        for name in ("ci-pages.yml", "daily-data.yml"):
            workflow = self.load(name)
            self.assertEqual(workflow["permissions"], {"contents": "read"})
            for job in workflow["jobs"].values():
                for step in job.get("steps", []):
                    if "uses" not in step:
                        continue
                    action, sha = step["uses"].split("@", 1)
                    self.assertRegex(sha, r"^[0-9a-f]{40}$")
                    self.assertEqual(expected[action], sha)
                    if action == "actions/checkout":
                        self.assertEqual(step["with"]["persist-credentials"], "false")
                        self.assertEqual(step["with"]["ref"], "${{ github.sha }}")
                    if action == "actions/setup-node":
                        self.assertEqual(step["with"]["package-manager-cache"], "false")
                        self.assertNotIn("cache", step["with"])
                    if action == "actions/setup-python":
                        self.assertNotIn("cache", step["with"])
                    self.assertNotIn(action, {"actions/cache", "actions/upload-artifact"})


if __name__ == "__main__":
    unittest.main()
