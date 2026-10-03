"""Operational rebrand must not touch archived prototypes or source snapshots."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RadarBrand(unittest.TestCase):
    def test_pages_prefix_title_and_package_are_radar(self):
        self.assertIn('base: "/radar-ozarow/"', (ROOT/'vite.config.ts').read_text())
        index=(ROOT/'index.html').read_text()
        self.assertIn('<title>Radar Ożarów',index)
        self.assertIn('inwestycj',index.lower())
        package=json.loads((ROOT/'package.json').read_text())
        lock=json.loads((ROOT/'package-lock.json').read_text())
        self.assertEqual(package['name'],'radar-ozarow')
        self.assertEqual(lock['name'],package['name'])
        self.assertEqual(lock['packages']['']['name'],package['name'])

    def test_readme_declares_target_not_unverified_deployment(self):
        readme=(ROOT/'README.md').read_text()
        self.assertTrue(readme.startswith('# Radar Ożarów'))
        self.assertIn('/radar-ozarow/',readme)
        self.assertIn('scripts/import_investments.py',readme)
        self.assertIn('public/data/investments.json',readme)
        self.assertIn('docs/investments/PIPELINE.md',readme)


if __name__ == '__main__':
    unittest.main()
