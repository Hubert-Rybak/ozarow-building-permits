"""Run the workflow's exact pre-commit allowlist without making any commits/pushes."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {'public/data/permits.json','public/data/parcels.geojson','public/data/metadata.json',
           'public/data/investments.json','scripts/uldk-cache.json'}


class SnapshotAllowlist(unittest.TestCase):
    def setUp(self):
        workflow=yaml.load((ROOT/'.github/workflows/daily-data.yml').read_text(),Loader=yaml.BaseLoader)
        command=next(s['run'] for s in workflow['jobs']['refresh']['steps'] if s.get('id') == 'snapshot')
        match=re.search(r"python - <<'PY'\n(.*?)\nPY",command,re.S)
        self.assertIsNotNone(match)
        self.code=match.group(1)
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        subprocess.run(['git','init','-q'],cwd=self.root,check=True,capture_output=True)

    def write(self,path):
        target=self.root/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('test-only snapshot fixture')

    def execute(self):
        return subprocess.run([sys.executable,'-c',self.code],cwd=self.root,text=True,capture_output=True)

    def test_accepts_exact_four_artifacts_and_evidence_initial_generation(self):
        for path in ALLOWED: self.write(path)
        result=self.execute()
        self.assertEqual(result.returncode,0,result.stderr)

    def test_rejects_unexpected_untracked_files(self):
        self.write('raw/source.json')
        result=self.execute()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Unexpected',result.stderr)

    def test_rejects_pre_staged_unexpected_files(self):
        self.write('scripts/unexpected.py')
        subprocess.run(['git','add','--','scripts/unexpected.py'],cwd=self.root,check=True)
        result=self.execute()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Unexpected',result.stderr)

    def test_rejects_tracked_worktree_changes(self):
        self.write('tracked-fixture.txt')
        subprocess.run(['git','add','--','tracked-fixture.txt'],cwd=self.root,check=True)
        (self.root/'tracked-fixture.txt').write_text('unexpected changed fixture')
        result=self.execute()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Unexpected',result.stderr)


if __name__ == '__main__':
    unittest.main()
