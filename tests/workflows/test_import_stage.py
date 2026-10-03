"""Execute the actual staging command, including GUNB's destructive directory swap."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
FILES = ('permits.json', 'parcels.geojson', 'metadata.json', 'investments.json')


class ImportStaging(unittest.TestCase):
    def test_investment_baseline_survives_gunb_swap(self):
        self.exercise(False)

    def test_investment_failure_cannot_change_published_data_or_evidence(self):
        self.exercise(True)

    def exercise(self, fail):
        workflow = yaml.load((ROOT/'.github/workflows/daily-data.yml').read_text(),Loader=yaml.BaseLoader)
        command = next(s['run'] for s in workflow['jobs']['refresh']['steps'] if s.get('id') == 'import')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); runner=root/'runner'; runner.mkdir()
            data=root/'public/data'; data.mkdir(parents=True)
            scripts=root/'scripts'; scripts.mkdir()
            evidence=scripts/'uldk-cache.json'; evidence.write_text('old verified evidence')
            for name in FILES: (data/name).write_text('old:'+name)
            bin_dir=root/'bin'; bin_dir.mkdir()
            tool=bin_dir/'python'
            tool.write_text('''#!/usr/bin/env python3
import os, sys, shutil
from pathlib import Path
args=sys.argv[1:]
output=Path(args[args.index('--output')+1])
if args[0] == 'scripts/import_data.py':
    assert (output/'permits.json').read_text() == 'old:permits.json', 'GUNB prior lost'
    shutil.rmtree(output)
    output.mkdir()
    for name in ('permits.json','parcels.geojson','metadata.json'):
        (output/name).write_text('new:'+name)
    Path(args[args.index('--uldk-public-cache')+1]).write_text('new verified evidence')
elif args[0] == 'scripts/import_investments.py':
    assert not (output/'investments.json').exists(), 'GUNB fixture did not swap directory'
    prior=Path(args[args.index('--prior')+1])
    assert prior.read_text() == 'old:investments.json', 'Investment full baseline lost'
    assert (output/'permits.json').read_text() == 'new:permits.json'
    if os.environ.get('FAIL_INVESTMENT') == 'true': sys.exit(23)
    (output/'investments.json').write_text('new:investments.json')
else:
    raise AssertionError('Unexpected command')
''')
            tool.chmod(0o700)
            env=dict(os.environ,RUNNER_TEMP=str(runner),PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],FAIL_INVESTMENT='true' if fail else 'false')
            result=subprocess.run(['bash','--noprofile','--norc','-e','-o','pipefail','-c',command],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,23 if fail else 0,result.stderr)
            for name in FILES: self.assertEqual((data/name).read_text(),'old:'+name)
            self.assertEqual(evidence.read_text(),'old verified evidence')
            self.assertEqual((runner/'prior-investments.json').read_text(),'old:investments.json')
            if not fail:
                candidate=runner/'data-candidate'
                self.assertEqual({p.name for p in candidate.iterdir()},set(FILES))
                for name in FILES: self.assertEqual((candidate/name).read_text(),'new:'+name)


if __name__ == '__main__':
    unittest.main()
