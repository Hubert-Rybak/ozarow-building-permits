"""Tests for the actual deployable directory, not an arbitrary upload path."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name("check_dist.py")


class DistributionSafety(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), "Missing distribution privacy validator")
        spec = importlib.util.spec_from_file_location("check_dist", MODULE)
        assert spec is not None and spec.loader is not None
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.public = self.root / "public/data"
        self.dist = self.root / "dist"
        self.public.mkdir(parents=True)
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "data").mkdir()
        (self.dist / "index.html").write_text("<!doctype html><script src='./assets/app.js'></script>")
        (self.dist / "assets/app.js").write_text("console.log('fixture')")
        (self.dist / "assets/app.css").write_text("body { color: black }")
        for filename, document in {
            "permits.json": {"records": [], "generatedAt": "2026-01-01T00:00:00Z"},
            "parcels.geojson": {"type": "FeatureCollection", "features": []},
            "metadata.json": {"recordCount": 0, "generatedAt": "2026-01-01T00:00:00Z"},
        }.items():
            text = json.dumps(document)
            (self.public / filename).write_text(text)
            (self.dist / "data" / filename).write_text(text)

    def test_accepts_only_the_validated_snapshot(self):
        self.module.validate(self.dist, self.public)

    def test_rejects_raw_archives_even_in_assets(self):
        (self.dist / "assets" / "source.zip").write_bytes(b"private fixture")
        with self.assertRaises(ValueError):
            self.module.validate(self.dist, self.public)

    def test_rejects_private_cache_tree(self):
        (self.dist / ".cache").mkdir()
        (self.dist / ".cache" / "response.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.module.validate(self.dist, self.public)

    def test_rejects_non_allowlisted_data_file(self):
        (self.dist / "data" / "raw.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.module.validate(self.dist, self.public)

    def test_rejects_source_snapshot_mismatch(self):
        (self.dist / "data" / "metadata.json").write_text('{"wrongGeneration": true}')
        with self.assertRaises(ValueError):
            self.module.validate(self.dist, self.public)

    def test_rejects_symlink_dereferencing_outside_dist(self):
        (self.dist / "assets" / "private.js").symlink_to(self.public / "permits.json")
        with self.assertRaises(ValueError):
            self.module.validate(self.dist, self.public)

    def test_rejects_hard_links(self):
        (self.dist / "assets" / "hard.js").hardlink_to(self.dist / "assets" / "app.js")
        with self.assertRaises(ValueError):
            self.module.validate(self.dist, self.public)


if __name__ == "__main__":
    unittest.main()
