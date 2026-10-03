"""Offline data contracts. Fixtures below are test-only, never published."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("import_data", ROOT / "scripts/import_data.py")


def row(**changes):
    data = {"numer_gunb": "TEST/WNIOSEK/1/2025", "data_wplywu_wniosku": "2025-01-09 00:00:00", "data_wydania_decyzji": "", "numer_decyzji_urzedu": "", "terc": "1432065", "miasto": "Duchnice", "jednosta_numer_ew": "143206_5", "obreb_numer": "0003", "numer_dzialki": "20/2", "numer_arkusza_dzialki": "", "nazwa_zam_budowlanego": "Budowa budynku", "nazwa_zamierzenia_bud": "budowa", "kategoria": "I", "ulica": "Testowa", "nazwa_inwestor": "PRIVATE NAME", "projektant_imie": "PRIVATE"}
    data.update(changes)
    return data


class ImportContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / "scripts/import_data.py").exists(), "Importer does not exist yet: expected RED")
        assert SPEC is not None and SPEC.loader is not None
        self.m = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(self.m)

    def test_iso_and_polish_dates(self):
        self.assertEqual(self.m.parse_date("2025-01-09 00:00:00"), "2025-01-09")
        self.assertEqual(self.m.parse_date("31.12.2025"), "2025-12-31")
        self.assertIsNone(self.m.parse_date("2025-02-30"))
        self.assertIsNone(self.m.parse_date(""))

    def test_rural_unit_not_city_name_defines_scope(self):
        self.assertTrue(self.m.in_scope(row(terc="", miasto="Kaputy")))
        self.assertTrue(self.m.in_scope(row(jednosta_numer_ew="", terc="1432064")))
        self.assertFalse(self.m.in_scope(row(jednosta_numer_ew="142807_2", terc="1428072", miasto="Ożarów")))

    def test_unit_is_not_guessed_or_repaired(self):
        self.assertEqual(self.m.parcel_reference(row()), "143206_5.0003.20/2")
        self.assertIsNone(self.m.parcel_reference(row(jednosta_numer_ew="143206_2")))
        self.assertIsNone(self.m.parcel_reference(row(obreb_numer="3")))
        self.assertIsNone(self.m.parcel_reference(row(numer_dzialki="20/2, 20/3")))
        self.assertIsNone(self.m.parcel_reference(row(jednosta_numer_ew="")))

    def test_sheet_identifier_preserved(self):
        self.assertEqual(self.m.parcel_reference(row(numer_arkusza_dzialki="10")), "143206_5.0003.AR_10.20/2")
        self.assertEqual(self.m.parcel_reference(row(numer_arkusza_dzialki="AR_10")), "143206_5.0003.AR_10.20/2")
        self.assertIsNone(self.m.parcel_reference(row(numer_arkusza_dzialki="?")))

    def test_deduplicate_rows_into_parcel_join(self):
        records, stats = self.m.normalize_rows([row(), row(), row(numer_dzialki="20/3")], "permit", "2025-01-01", "2026-12-31")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["parcelNumbers"], ["20/2", "20/3"])
        self.assertEqual(records[0]["parcelIds"], [])
        self.assertNotIn("PRIVATE", json.dumps(records))
        self.assertEqual(records[0]["kind"], "application")

    def test_decision_never_implies_approval(self):
        records, _ = self.m.normalize_rows([row(data_wydania_decyzji="2025-02-01", numer_decyzji_urzedu="D/1")], "permit", "2025-01-01", "2026-12-31")
        self.assertEqual(records[0]["kind"], "decision")
        self.assertIn("nieudostępniony", records[0]["status"])
        self.assertEqual(records[0]["decisionDate"], "2025-02-01")

    def test_notification_status_not_transformed_to_permit(self):
        r = row(numer_ewidencyjny_system="TEST/ZGLOSZENIE/2/2025", data_wplywu_wniosku_do_urzedu="2025-01-14", jednostki_numer="143206_5", stan="Brak sprzeciwu")
        records, _ = self.m.normalize_rows([r], "notification", "2025-01-01", "2026-12-31")
        self.assertEqual(records[0]["kind"], "notification")
        self.assertEqual(records[0]["status"], "Brak sprzeciwu")

    def test_year_filter_uses_dates(self):
        records, _ = self.m.normalize_rows([row(data_wplywu_wniosku="2024-12-31"), row(data_wplywu_wniosku="2027-01-01")], "permit", "2025-01-01", "2026-12-31")
        self.assertEqual(records, [])

    def test_invalid_date_excluded_and_reported(self):
        records, stats = self.m.normalize_rows([row(data_wplywu_wniosku="31.02.2025")], "permit", "2025-01-01", "2026-12-31")
        self.assertEqual(records, [])
        self.assertEqual(stats["invalidDateRows"], 1)

    def test_csv_detects_live_semicolon_and_documented_hash(self):
        for sep in (";", "#"):
            with tempfile.TemporaryDirectory() as directory:
                p = Path(directory) / "a.zip"
                names = sorted(self.m.REQUIRED_COLUMNS['permit'])
                values = dict.fromkeys(names, '')
                values.update(numer_gunb='A', terc='1432065', numer_dzialki='20/2', obreb_numer='0003')
                buffer = io.StringIO()
                writer = __import__('csv').DictWriter(buffer, fieldnames=names, delimiter=sep)
                writer.writeheader()
                writer.writerow(values)
                with zipfile.ZipFile(p, "w") as z:
                    z.writestr("a.csv", buffer.getvalue())
                self.assertEqual(list(self.m.read_csv_zip(p))[0]["terc"], "1432065")

    def test_incomplete_csv_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "a.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("a.csv", "numer_gunb;terc\nA;1432065\n")
            with self.assertRaises(ValueError):
                list(self.m.read_csv_zip(p))

    def test_wrong_csv_schema_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "a.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("a.csv", "garbage\nfoo\n")
            with self.assertRaises(ValueError):
                list(self.m.read_csv_zip(p))

    def test_geometry_requires_exact_returned_id(self):
        text = "0\nSRID=4326;POLYGON((20.8 52.2,20.81 52.2,20.81 52.21,20.8 52.2))|143206_5.0003.20/2\n"
        geometry = self.m.parse_uldk(text, "143206_5.0003.20/2")
        self.assertEqual(geometry["type"], "Polygon")
        self.assertEqual(geometry["coordinates"][0][0], [20.8, 52.2])
        with self.assertRaises(ValueError):
            self.m.parse_uldk(text, "143206_5.0003.20/3")

    def test_geometry_rejects_wrong_srid_and_axis(self):
        for geom in ("SRID=2180;POLYGON((20.8 52.2,20.81 52.2,20.81 52.21,20.8 52.2))", "SRID=4326;POLYGON((52.2 20.8,52.2 20.81,52.21 20.81,52.2 20.8))"):
            with self.assertRaises(ValueError):
                self.m.parse_uldk(f"0\n{geom}|143206_5.0003.20/2", "143206_5.0003.20/2")

    def test_geometry_rejects_service_error_and_multiple_results(self):
        for text in ("-1 brak wyników", "0\n", "0\nfoo|wrong\nbar|wrong", "<html>error</html>"):
            with self.assertRaises(ValueError):
                self.m.parse_uldk(text, "143206_5.0003.20/2")

    def test_partial_join_and_unresolved_visible(self):
        records, _ = self.m.normalize_rows([row(), row(numer_dzialki="20/3")], "permit", "2025-01-01", "2026-12-31")
        geom = {"type": "Polygon", "coordinates": [[[20.8,52.2],[20.81,52.2],[20.81,52.21],[20.8,52.2]]]}
        features = self.m.attach_geometry(records, {"143206_5.0003.20/2": geom}, {})
        self.assertEqual(records[0]["geometryStatus"], "partial")
        self.assertEqual(records[0]["parcelIds"], ["143206_5.0003.20/2"])
        self.assertEqual(features[0]["properties"]["permitIds"], [records[0]["id"]])
        self.assertEqual(features[0]["properties"]["region"], "0003")
        self.assertIn("1/2", records[0]["geometryNote"])
        self.assertNotIn("_parcelRefs", records[0])

    def test_invalid_reference_prevents_false_fully_matched(self):
        records, _ = self.m.normalize_rows([row(), row(numer_dzialki="20/3", jednosta_numer_ew="143206_2")], "permit", "2025-01-01", "2026-12-31")
        features = self.m.attach_geometry(records, {"143206_5.0003.20/2": {"type":"Polygon","coordinates":[]}}, {})
        self.assertEqual(records[0]["geometryStatus"], "partial")
        self.assertIn("niejednoznacz", records[0]["geometryNote"])

    def test_atomic_failure_preserves_previous_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "data"
            self.m.atomic_publish(target, {"permits.json": {"old": True}, "metadata.json": {"old": True}})
            before = (target / "permits.json").read_bytes()
            with self.assertRaises((TypeError, ValueError)):
                self.m.atomic_publish(target, {"permits.json": {"new": True}, "metadata.json": {"bad": object()}})
            self.assertEqual((target / "permits.json").read_bytes(), before)
            self.assertEqual(json.loads((target / "metadata.json").read_text()), {"old": True})

    def test_cache_retries_then_reuses_only_valid_response(self):
        from unittest.mock import patch, Mock
        responses = []
        for text in ("-1 no result", "0\nconfirmed"):
            response = Mock(content=text.encode(), text=text, headers={})
            response.raise_for_status.return_value = None
            responses.append(response)
        def validate(text):
            if not text.startswith("0\n"):
                raise ValueError("Not a successful response")
            return text
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(Path(directory), retries=2, delay=0)
            with patch.object(self.m.requests, "get", side_effect=responses) as get:
                first = client.text("https://uldk.gugik.gov.pl/?test", validate)
                self.assertEqual(get.call_count, 2)
                self.assertEqual(get.call_args.kwargs["timeout"], (10, 30))
            with patch.object(self.m.requests, "get", side_effect=AssertionError("must use cache")):
                self.assertEqual(client.text("https://uldk.gugik.gov.pl/?test", validate), first)

    def test_failed_requests_do_not_cache_errors(self):
        from unittest.mock import patch, Mock
        response = Mock(content=b"-1 no result", text="-1 no result", headers={})
        response.raise_for_status.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(Path(directory), retries=2, delay=0)
            def validate(text):
                raise ValueError("no geometry")
            with patch.object(self.m.requests, "get", return_value=response) as get:
                with self.assertRaises(ValueError):
                    client.text("https://uldk.gugik.gov.pl/?missing", validate)
                self.assertEqual(get.call_count, 2)
            self.assertEqual(list(Path(directory).rglob("*.json")), [])

    def test_free_text_removes_private_names(self):
        records, _ = self.m.normalize_rows([row(nazwa_zam_budowlanego="Budowa domu PRIVATE NAME", projektant_nazwisko="PERSON")], "permit", "2025-01-01", "2026-12-31")
        self.assertNotIn("PRIVATE", json.dumps(records))
        self.assertEqual(records[0]["title"], "Budowa — obiekt budowlany")
        self.assertIn("Swobodny opis GUNB pominięto", records[0]["description"])

    def test_multipolygon_preserved(self):
        text = "0\nSRID=4326;MULTIPOLYGON(((20.8 52.2,20.81 52.2,20.81 52.21,20.8 52.2)))|143206_5.0003.20/2"
        self.assertEqual(self.m.parse_uldk(text, "143206_5.0003.20/2")["type"], "MultiPolygon")

    def test_cli_requires_iso_dates_before_any_network_or_cache(self):
        from argparse import Namespace
        from unittest.mock import patch
        args = Namespace(since="01.01.2025", until="2026-10-02", cache=Path("unused"), refresh=False, offline=True)
        with patch.object(self.m, "CachedHTTP", side_effect=AssertionError("date validation must precede I/O")):
            with self.assertRaises(ValueError):
                self.m.run(args)

    def test_offline_requires_verified_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(Path(directory), offline=True)
            with self.assertRaises(ValueError):
                client.text("https://uldk.gugik.gov.pl/?uncached", lambda text: text)
            with self.assertRaises(ValueError):
                client.download("https://wyszukiwarka.gunb.gov.pl/missing.zip")

    def test_commune_and_region_verification_refuse_other_municipality(self):
        self.assertTrue(self.m.verify_commune("0\n143206_3|Ożarów Mazowiecki|powiat warszawski zachodni"))
        for text in ("0\n143206_3|Wrong|powiat warszawski zachodni", "-1 no result"):
            with self.assertRaises(ValueError):
                self.m.verify_commune(text)
        validate = self.m.region_validator("143206_5.0003")
        self.assertEqual(validate("0\n143206_5.0003|Duchnice|Ożarów Mazowiecki")["name"], "Duchnice")
        with self.assertRaises(ValueError):
            validate("0\n143206_4.0003|0003|Ożarów Mazowiecki")
        with self.assertRaises(ValueError):
            validate("0\n143206_5.0003|Duchnice|Wrong")

    def test_repeatable_cli_defaults_to_full_parcel_coverage(self):
        from unittest.mock import patch
        received = []
        with patch('sys.argv', ['import_data.py', '--offline']), patch.object(self.m, 'run', side_effect=lambda args: received.append(args)):
            self.m.main()
        self.assertEqual(received[0].max_parcels, 0)

    def test_artifact_schema_required_fields(self):
        records, _ = self.m.normalize_rows([row()], "permit", "2025-01-01", "2026-12-31")
        self.m.attach_geometry(records, {}, {})
        required = {"id","kind","title","description","applicationDate","decisionDate","decisionNumber","status","locality","street","municipality","cadastralRegion","parcelNumbers","parcelIds","category","sourceUrl","geometryStatus","geometryNote"}
        self.assertEqual(set(records[0]), required)
        self.assertEqual(records[0]["geometryStatus"], "unresolved")


if __name__ == "__main__":
    unittest.main()
