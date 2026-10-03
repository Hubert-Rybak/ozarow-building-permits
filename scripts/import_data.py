#!/usr/bin/env python3
"""Import public GUNB CSV records + exact-ID ULDK geometries. No CAPTCHA scraping.

python scripts/import_data.py --help
Raw CSVs are private cache inputs; only allowlisted, redacted fields are published.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import ctypes
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import zipfile

import requests
from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
GUNB = "https://wyszukiwarka.gunb.gov.pl/"
DOWNLOADS = {
    "permit": GUNB + "pliki_pobranie/wynik_mazowieckie.zip",
    "notification": GUNB + "pliki_pobranie/wynik_zgloszenia_2022_up.zip",
}
ULDK = "https://uldk.gugik.gov.pl/"
UNITS = frozenset({"143206_4", "143206_5"})
TERCS = frozenset({"1432063", "1432064", "1432065"})
PUBLIC_ULDK_CACHE = ROOT / "scripts/uldk-cache.json"
GEOMETRY_TTL_SECONDS = 30 * 86400
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
# Every used source column is mandatory; the live export may duplicate only 'cecha'.
COMMON_COLUMNS = frozenset({"terc", "miasto", "ulica", "ulica_dalej", "nr_domu", "kategoria",
                            "nazwa_zam_budowlanego", "obreb_numer", "numer_dzialki", "numer_arkusza_dzialki"})
REQUIRED_COLUMNS = {
    "permit": COMMON_COLUMNS | {"numer_gunb", "data_wplywu_wniosku", "data_wydania_decyzji",
                                "numer_decyzji_urzedu", "jednosta_numer_ew", "nazwa_zamierzenia_bud",
                                "nazwa_inwestor", "projektant_imie", "projektant_nazwisko", "projektant_numer_uprawnien"},
    "notification": COMMON_COLUMNS | {"numer_ewidencyjny_system", "data_wplywu_wniosku_do_urzedu",
                                      "jednostki_numer", "rodzaj_zam_budowlanego", "stan",
                                      "imie_projektanta", "nazwisko_projektanta", "projektant_pozostali", "projektant_numer_uprawnien"},
}


def valid_timestamp(value, ttl):
    """Use real downloadedAt evidence, never checkout/file modification times."""
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return False
        age = time.time() - timestamp.timestamp()
        return 0 <= age < ttl
    except (AttributeError, TypeError, ValueError):
        return False


SUMMARY_SUBJECTS = (
    (r"jednorodzinn", "budynek mieszkalny jednorodzinny"),
    (r"wielorodzinn", "budynek mieszkalny wielorodzinny"),
    (r"mieszkal", "budynek mieszkalny"),
    (r"gazow", "infrastruktura gazowa"),
    (r"elektroenerget|elektrycz|energetycz", "infrastruktura elektroenergetyczna"),
    (r"wodociąg|wodociag|kanaliz|wodno", "infrastruktura wodno-kanalizacyjna"),
    (r"telekomunik|światłow|swiatlow", "infrastruktura telekomunikacyjna"),
    (r"magazyn|produkcyjn|przemysł|przemysl", "obiekt magazynowy lub przemysłowy"),
    (r"usług|uslug|handlow", "obiekt usługowy lub handlowy"),
    (r"drog|drogi|drogow|zjazd", "infrastruktura drogowa"),
    (r"garaż|garaz|gospodarcz", "obiekt garażowy lub gospodarczy"),
    (r"fotowolta|słonecz|slonecz", "instalacja fotowoltaiczna"),
    (r"budyn|budow", "obiekt budowlany"),
)
SUMMARY_OPERATIONS = ((r"rozbiór|rozbior", "Rozbiórka"), (r"przebudow", "Przebudowa"),
                      (r"rozbudow", "Rozbudowa"), (r"nadbudow", "Nadbudowa"),
                      (r"remont", "Remont"), (r"budow", "Budowa"), (r"instal|montaż|montaz", "Instalacja"))
PUBLIC_DESCRIPTION = "Bezpieczny skrót rodzaju inwestycji. Swobodny opis GUNB pominięto ze względu na możliwość występowania danych osobowych."
PUBLIC_TITLES = frozenset(f"{operation} — {subject}"
                         for operation in [label for _, label in SUMMARY_OPERATIONS] + ["Zamierzenie"]
                         for subject in [label for _, label in SUMMARY_SUBJECTS] + ["zamierzenie budowlane"])
NOTIFICATION_STATUSES = frozenset({"Brak sprzeciwu", "Sprzeciw", "Zgłoszenie wycofane", "Wycofanie zgłoszenia",
                                  "W trakcie rozpatrywania", "Do uzupełnienia", "Zgłoszenie przyjęte",
                                  "Wniesiono sprzeciw", "Nie wniesiono sprzeciwu"})
UNKNOWN_STATUS = "Inny status źródłowy — tekst pominięto ze względu na prywatność"
MUNICIPALITY = "Ożarów Mazowiecki (miasto i obszar wiejski)"
PARCEL_PATTERN = r"143206_[45]\.[0-9]{4}\.(?:AR_[0-9]+\.)?[0-9]+(?:/[0-9]+)?"
REGION_PATTERN = r"143206_[45]\.[0-9]{4}"
RECORD_FIELDS = frozenset({"id", "kind", "title", "description", "applicationDate", "decisionDate", "decisionNumber",
                           "status", "locality", "street", "municipality", "cadastralRegion", "parcelNumbers", "parcelIds",
                           "category", "sourceUrl", "geometryStatus", "geometryNote"})


def public_summary(rows):
    """Never copy source free text; generation and validation share one vocabulary."""
    text = " ".join((r.get("nazwa_zam_budowlanego") or "") for r in rows).casefold()
    subject = next((label for pattern, label in SUMMARY_SUBJECTS if re.search(pattern, text)), "zamierzenie budowlane")
    operation = next((label for pattern, label in SUMMARY_OPERATIONS if re.search(pattern, text)), "Zamierzenie")
    return f"{operation} — {subject}", PUBLIC_DESCRIPTION



def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(value):
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def unit_of(row):
    return row.get("jednostki_numer", row.get("jednosta_numer_ew", "")) or ""


def in_scope(row):
    # Cadastral unit catches rural localities and wrongly encoded city-name rows.
    # TERC catches missing/bad parcel references, which remain explicitly unresolved.
    return unit_of(row) in UNITS or row.get("terc", "") in TERCS


def parcel_reference(row):
    unit = unit_of(row)
    region = row.get("obreb_numer", "") or ""
    parcel = row.get("numer_dzialki", "") or ""
    sheet = row.get("numer_arkusza_dzialki", "") or ""
    if unit not in UNITS or not re.fullmatch(r"[0-9]{4}", region) or not re.fullmatch(r"[0-9]+(?:/[0-9]+)?", parcel):
        return None
    if sheet:
        if not re.fullmatch(r"(?:AR_)?[0-9]+", sheet):
            return None
        sheet = (sheet if sheet.startswith("AR_") else "AR_" + sheet) + "."
    return f"{unit}.{region}.{sheet}{parcel}"


def redact(value, rows):
    value = re.sub(r"\s+", " ", value or "").strip()
    private = set()
    for row in rows:
        for key in ("nazwa_inwestor", "projektant_imie", "projektant_nazwisko", "imie_projektanta", "nazwisko_projektanta", "projektant_pozostali"):
            token = re.sub(r"\s+", " ", row.get(key, "") or "").strip()
            if len(token) >= 3:
                private.add(token)
    for token in sorted(private, key=len, reverse=True):
        value = re.sub(r"(?<!\w)" + re.escape(token) + r"(?!\w)", "[dane osobowe pominięte]", value, flags=re.I)
    return value


def normalize_rows(rows, source_kind, since, until):
    groups = defaultdict(list)
    stats = Counter(totalRows=0, scopedRows=0, dateFilteredRows=0, invalidDateRows=0, missingIdRows=0, invalidParcelRows=0)
    date_key = "data_wplywu_wniosku_do_urzedu" if source_kind == "notification" else "data_wplywu_wniosku"
    id_key = "numer_ewidencyjny_system" if source_kind == "notification" else "numer_gunb"
    for row in rows:
        stats["totalRows"] += 1
        if not in_scope(row):
            continue
        stats["scopedRows"] += 1
        date = parse_date(row.get(date_key))
        if not date:
            stats["invalidDateRows"] += 1
            continue
        if not since <= date <= until:
            stats["dateFilteredRows"] += 1
            continue
        identity = row.get(id_key)
        if not identity:
            stats["missingIdRows"] += 1
            continue
        groups[identity].append(row)
    records = []
    for identity, group in sorted(groups.items()):
        # Pick the latest recorded decision, while keeping its original application date.
        r = max(group, key=lambda x: parse_date(x.get("data_wydania_decyzji")) or "")
        notification = source_kind == "notification"
        decision_date = None if notification else parse_date(r.get("data_wydania_decyzji"))
        decision_number = None if notification else (r.get("numer_decyzji_urzedu") or None)
        kind = "notification" if notification else ("decision" if decision_date or decision_number else "application")
        refs = sorted(set(filter(None, (parcel_reference(x) for x in group))))
        # Count unknown references separately: never turn a bad source token into an ID.
        unknown = len({(unit_of(x), x.get("obreb_numer", ""), x.get("numer_dzialki", ""), x.get("numer_arkusza_dzialki", "")) for x in group if not parcel_reference(x)})
        stats["invalidParcelRows"] += sum(not parcel_reference(x) for x in group)
        title, description = public_summary(group)
        if notification:
            # Status is another free-text source field: only known nonpersonal labels.
            source_status = r.get("stan") or ""
            status = source_status if source_status in NOTIFICATION_STATUSES else (UNKNOWN_STATUS if source_status else "Brak statusu w CSV")
            if source_status and source_status not in NOTIFICATION_STATUSES:
                stats["unknownNotificationStatusRows"] += len(group)
        else:
            status = "Decyzja odnotowana — wynik nieudostępniony w CSV" if kind == "decision" else "Wniosek — brak decyzji w CSV"
        regions = sorted({f"{unit_of(x)}.{x.get('obreb_numer', '')}" for x in group if unit_of(x) in UNITS and re.fullmatch(r"[0-9]{4}", x.get("obreb_numer", ""))})
        records.append({
            "id": source_kind + ":" + identity,
            "kind": kind,
            "title": title,
            "description": description,
            "applicationDate": parse_date(r.get(date_key)),
            "decisionDate": decision_date,
            "decisionNumber": decision_number,
            "status": status,
            "locality": ", ".join(sorted({x.get("miasto", "") for x in group if x.get("miasto")})),
            "street": " ".join(filter(None, (r.get("ulica", ""), r.get("ulica_dalej", ""), r.get("nr_domu", "")))).strip(),
            "municipality": "Ożarów Mazowiecki (miasto i obszar wiejski)",
            "cadastralRegion": ", ".join(regions) or "Brak wiarygodnego obrębu w CSV",
            "parcelNumbers": sorted({x.get("numer_dzialki", "") for x in group if x.get("numer_dzialki")}),
            "parcelIds": [],
            "category": r.get("kategoria", "") or "",
            "sourceUrl": DOWNLOADS[source_kind],
            "geometryStatus": "unresolved",
            "geometryNote": "Nie potwierdzono geometrii.",
            "_parcelRefs": refs,
            "_unknownRefs": unknown,
        })
    records.sort(key=lambda r: (r["applicationDate"], r["id"]), reverse=True)
    return records, dict(stats)


def read_csv_zip(path, source_kind=None):
    with zipfile.ZipFile(path) as archive:
        files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(files) != 1:
            raise ValueError("Expected exactly one CSV in official ZIP")
        if archive.getinfo(files[0]).file_size > 1024 * 1024 * 1024:
            raise ValueError("Expanded CSV exceeds 1 GiB safety limit")
        with archive.open(files[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            header = text.readline()
            delimiter = ";" if header.count(";") > header.count("#") else "#"
            names = next(csv.reader([header], delimiter=delimiter))
            detected_kind = "notification" if "numer_ewidencyjny_system" in names else "permit"
            source_kind = source_kind or detected_kind
            if source_kind != detected_kind or not REQUIRED_COLUMNS[source_kind].issubset(names):
                raise ValueError("CSV schema changed: required source columns missing or wrong source kind")
            if any(count > 1 and name != "cecha" for name, count in Counter(names).items()):
                raise ValueError("CSV schema changed: ambiguous duplicate column")
            # Reject truncated/extra-field rows rather than silently losing source data.
            for row in csv.DictReader(text, fieldnames=names, delimiter=delimiter, strict=True):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("CSV row has wrong field count")
                yield row


def parse_uldk(text, expected_id):
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) != 2 or lines[0] != "0":
        raise ValueError("ULDK: missing, failed or ambiguous exact-ID response")
    pieces = lines[1].split("|")
    if len(pieces) != 2 or pieces[1] != expected_id:
        raise ValueError("ULDK: returned identifier does not exactly match requested ID")
    if not pieces[0].startswith("SRID=4326;"):
        raise ValueError("ULDK: response must explicitly declare EPSG:4326")
    try:
        geom = wkt.loads(pieces[0].split(";", 1)[1])
    except GEOSException as exc:
        raise ValueError("ULDK: malformed WKT geometry") from exc
    if geom.geom_type not in ("Polygon", "MultiPolygon") or geom.is_empty or not geom.is_valid:
        raise ValueError("ULDK: invalid/nonpolygon geometry")
    west, south, east, north = geom.bounds
    # Broad Poland bounds detect wrong units/axis without inventing a gmina boundary.
    if not (14 <= west <= east <= 25 and 49 <= south <= north <= 55):
        raise ValueError("ULDK: out-of-range WGS84 longitude/latitude")
    return json.loads(json.dumps(mapping(geom)))


def uldk_url(request, identity, result="geom_wkt,id"):
    return ULDK + "?" + urlencode({"request": request, "id": identity, "result": result, "srid": "4326"})


def attach_geometry(records, geometries, errors):
    joins = defaultdict(list)
    for r in records:
        refs = r.pop("_parcelRefs")
        unknown = r.pop("_unknownRefs")
        r["parcelIds"] = [ref for ref in refs if ref in geometries]
        total = len(refs) + unknown
        resolved = len(r["parcelIds"])
        r["geometryStatus"] = "matched" if total and resolved == total else ("partial" if resolved else "unresolved")
        r["geometryNote"] = f"Potwierdzone obrysy ULDK: {resolved}/{total}."
        if unknown:
            r["geometryNote"] += f" Niejednoznaczne lub nieprawidłowe odwołania w CSV: {unknown}.".replace("Niejednoznaczne", "niejednoznaczne")
        omitted = [ref for ref in refs if ref not in geometries and ref not in errors]
        if omitted:
            r["geometryNote"] += f" Poza limitem bieżącego importu geometrii: {len(omitted)}."
        failed = [ref for ref in refs if ref in errors]
        if failed:
            r["geometryNote"] += f" Brak wiarygodnej odpowiedzi ULDK: {len(failed)} (możliwy podział działki, błąd źródła lub usługi)."
        for ref in r["parcelIds"]:
            joins[ref].append(r["id"])
    return [{"type": "Feature", "geometry": geometries[ref], "properties": {
        "id": ref, "parcelNumber": ref.split(".")[-1], "region": ref.split(".")[1],
        "permitIds": sorted(set(joins[ref])), "sourceUrl": uldk_url("GetParcelById", ref),
    }} for ref in sorted(joins)]


def atomic_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".partial-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class CachedHTTP:
    """Successful/validated replies only; max three timed attempts per URL."""
    def __init__(self, cache, retries=3, delay=0.5, refresh=False, offline=False, refresh_sources=False):
        self.cache = Path(cache)
        self.retries = retries
        self.delay = delay
        self.refresh = refresh
        self.refresh_sources = refresh_sources
        self.offline = offline
        self.cache_hits = set()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.cache.chmod(0o700)

    def response_path(self, url):
        return self.cache / "responses" / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def entry(self, url):
        value = json.loads(self.response_path(url).read_text())
        if not isinstance(value, dict) or value.get("url") != url or not valid_timestamp(value.get("downloadedAt"), GEOMETRY_TTL_SECONDS):
            raise ValueError("Expired or invalid response evidence")
        text = value.get("text")
        if not isinstance(text, str) or ("sha256" in value and value["sha256"] != hashlib.sha256(text.encode()).hexdigest()):
            raise ValueError("Response cache content checksum failed")
        return value

    def seed_public_cache(self, path):
        """Revalidate privacy-safe exact ULDK responses from a tracked repository file."""
        if self.refresh or not Path(path).exists():
            return 0
        try:
            payload = json.loads(Path(path).read_text())
            if payload.get("schemaVersion") != 1 or not isinstance(payload.get("responses"), list):
                return 0
        except (OSError, ValueError, AttributeError):
            return 0
        accepted = 0
        for item in payload["responses"]:
            try:
                entry = verify_public_cache_entry(item)
                url = entry["url"]
                # Prefer newer locally verified evidence; never turn seeding into a download.
                try:
                    local = self.entry(url)
                    public_cache_validator(url)(local["text"])
                    if local["downloadedAt"] >= entry["downloadedAt"]:
                        continue
                except (OSError, ValueError, KeyError):
                    pass
                atomic_file(self.response_path(url), json.dumps(entry, ensure_ascii=False).encode())
                accepted += 1
            except (ValueError, TypeError, KeyError):
                continue
        return accepted

    def public_cache_payload(self, urls):
        """Build evidence in memory so validation precedes every publication write."""
        entries = []
        for url in sorted(set(urls)):
            try:
                entry = self.entry(url)
                entry["sha256"] = hashlib.sha256(entry["text"].encode()).hexdigest()
                entries.append(verify_public_cache_entry(entry))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return {"schemaVersion": 1, "responses": entries}

    def export_public_cache(self, path, urls):
        payload = self.public_cache_payload(urls)
        atomic_file(Path(path), (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())
        return len(payload["responses"])

    def text(self, url, validator):
        path = self.response_path(url)
        if not self.refresh:
            try:
                entry = self.entry(url)
                validator(entry["text"])
                self.cache_hits.add(url)
                return entry["text"]
            except (OSError, ValueError, KeyError):
                pass
        if self.offline:
            raise ValueError("Offline: no verified unexpired cache for " + url)
        for attempt in range(self.retries):
            try:
                response = requests.get(url, timeout=(10, 30), headers={"User-Agent": "Ozarow-Permits-Data/1.0"})
                response.raise_for_status()
                text = response.content.decode("utf-8-sig")
                validator(text)
                entry = {"url": url, "downloadedAt": utc_now(), "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest()}
                atomic_file(path, json.dumps(entry, ensure_ascii=False).encode())
                return text
            except (requests.RequestException, ValueError) as exc:
                if attempt == self.retries - 1:
                    raise ValueError("Failed validated GET: " + url) from exc
                time.sleep(self.delay * (attempt + 1))
        raise ValueError("No GET attempts configured")

    def archive_evidence(self, url, path):
        entry = json.loads(Path(str(path) + ".evidence.json").read_text())
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if entry.get("url") != url or entry.get("sha256") != digest or entry.get("byteCount") != Path(path).stat().st_size:
            raise ValueError("Source ZIP provenance/checksum failed")
        if not valid_timestamp(entry.get("downloadedAt"), float("inf")):
            raise ValueError("Source ZIP has no valid download timestamp")
        return {key: entry[key] for key in ("url", "downloadedAt", "sha256", "byteCount", "httpLastModified", "httpETag")}

    def download(self, url):
        if url not in DOWNLOADS.values():
            raise ValueError("Source archive URL is not allowlisted")
        path = self.cache / url.rsplit("/", 1)[-1]
        if path.exists() and not (self.refresh or self.refresh_sources):
            try:
                evidence = self.archive_evidence(url, path)
                if self.offline or valid_timestamp(evidence["downloadedAt"], 86400):
                    with zipfile.ZipFile(path) as z:
                        if z.testzip() is not None:
                            raise ValueError("Invalid cached ZIP")
                    return path
            except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                pass
        if self.offline:
            raise ValueError("Offline: no verified source archive " + str(path))
        for attempt in range(self.retries):
            try:
                response = requests.get(url, timeout=(15, 150), headers={"User-Agent": "Ozarow-Permits-Data/1.0", "Cache-Control": "no-cache"})
                response.raise_for_status()
                if len(response.content) > MAX_ARCHIVE_BYTES:
                    raise ValueError("Source archive exceeds 200 MiB safety limit")
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    if z.testzip() is not None:
                        raise ValueError("Downloaded ZIP failed CRC validation")
                evidence = {"url": url, "downloadedAt": utc_now(), "sha256": hashlib.sha256(response.content).hexdigest(),
                            "byteCount": len(response.content), "httpLastModified": response.headers.get("Last-Modified"),
                            "httpETag": response.headers.get("ETag")}
                atomic_file(path, response.content)
                atomic_file(Path(str(path) + ".evidence.json"), json.dumps(evidence, ensure_ascii=False).encode())
                return path
            except (requests.RequestException, ValueError, zipfile.BadZipFile) as exc:
                if attempt == self.retries - 1:
                    raise ValueError("Could not download valid CSV archive: " + url) from exc
                time.sleep(self.delay * (attempt + 1))
        raise ValueError("No source download attempts configured")


def stage_artifacts(stage, artifacts):
    """Write/fsync a complete candidate without touching its publication target."""
    stage = Path(stage)
    stage.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        if Path(name).name != name:
            raise ValueError("Artifact names cannot contain directories")
        atomic_file(stage / name, (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


def atomic_publish(target, artifacts, *, prepared_stage=None):
    """Serialize/fsync all artifacts before a directory exchange; retain prior data on failure."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(prepared_stage) if prepared_stage is not None else Path(tempfile.mkdtemp(prefix=".data-stage-", dir=target.parent))
    backup = None
    try:
        if prepared_stage is None:
            stage_artifacts(stage, artifacts)
        elif {path.name: json.loads(path.read_text()) for path in stage.iterdir()} != artifacts:
            raise ValueError("Prepared artifacts changed before publication")
        if not target.exists():
            os.replace(stage, target)
            return
        # Linux RENAME_EXCHANGE swaps directories atomically (no mixed JSON generations).
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is not None:
            result = renameat2(-100, os.fsencode(stage), -100, os.fsencode(target), 2)
            if result == 0:
                return
            error = ctypes.get_errno()
            if error not in (22, 38, 95):
                raise OSError(error, "atomic directory exchange failed")
        # Portable fallback with rollback (brief gap, but never mixed generations).
        backup = target.parent / (stage.name + "-previous")
        os.replace(target, backup)
        try:
            os.replace(stage, target)
        except BaseException:
            os.replace(backup, target)
            backup = None
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if backup and backup.exists():
            shutil.rmtree(backup)


def verify_commune(text):
    lines = text.strip().splitlines()
    if len(lines) != 2 or lines[0] != "0" or lines[1] != "143206_3|Ożarów Mazowiecki|powiat warszawski zachodni":
        raise ValueError("Cannot verify municipality against official ULDK PRG")
    return True


def region_validator(expected):
    def validate(text):
        lines = text.strip().splitlines()
        if len(lines) != 2 or lines[0] != "0":
            raise ValueError("ULDK region lookup failed")
        fields = lines[1].split("|")
        if len(fields) != 3 or fields[0] != expected or fields[2] != "Ożarów Mazowiecki":
            raise ValueError("ULDK region not in verified municipality")
        return {"id": fields[0], "name": fields[1], "municipality": fields[2]}
    return validate


def public_cache_validator(url):
    """Allow only exact known ULDK URLs and privacy-safe result contracts."""
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    if parts.scheme != "https" or parts.netloc != "uldk.gugik.gov.pl" or parts.path != "/" or parts.fragment:
        raise ValueError("Public evidence must come from official ULDK")
    if set(query) != {"request", "id", "result", "srid"} or any(len(values) != 1 for values in query.values()):
        raise ValueError("Noncanonical ULDK evidence URL")
    request, identity, result = query["request"][0], query["id"][0], query["result"][0]
    if query["srid"] != ["4326"] or url != uldk_url(request, identity, result):
        raise ValueError("Noncanonical exact-ID ULDK evidence")
    if request == "GetCommuneById" and identity in UNITS and result == "id,commune,county":
        return verify_commune
    if request == "GetRegionById" and re.fullmatch(r"143206_[45]\.[0-9]{4}", identity) and result == "id,region,commune":
        return region_validator(identity)
    if request == "GetParcelById" and re.fullmatch(r"143206_[45]\.[0-9]{4}\.(?:AR_[0-9]+\.)?[0-9]+(?:/[0-9]+)?", identity) and result == "geom_wkt,id":
        return lambda text: parse_uldk(text, identity)
    raise ValueError("ULDK evidence request is not allowlisted")


def verify_public_cache_entry(entry):
    if not isinstance(entry, dict) or set(entry) != {"url", "downloadedAt", "text", "sha256"}:
        raise ValueError("Unexpected public evidence fields")
    text = entry["text"]
    if not isinstance(text, str) or entry["sha256"] != hashlib.sha256(text.encode()).hexdigest():
        raise ValueError("Public evidence checksum failed")
    if not valid_timestamp(entry["downloadedAt"], GEOMETRY_TTL_SECONDS):
        raise ValueError("Public evidence timestamp expired or invalid")
    public_cache_validator(entry["url"])(text)
    return {key: entry[key] for key in ("url", "downloadedAt", "text", "sha256")}


def validate_artifacts(candidate, *, evidence=None):
    """Validate the entire public contract, not just regression totals.

    Evidence is optional for inspecting archived artifacts. Publication always
    supplies it: coordinates must equal the original exact-ID/SRID WKT response,
    with a validated hash and original unexpired timestamp. Never repair geometry.
    Error messages contain field labels, never rejected private values.
    """
    def require(condition, label):
        if not condition:
            raise ValueError("Invalid publication candidate: " + label)

    def fields(value, allowed, label):
        require(isinstance(value, dict) and set(value) == set(allowed), label + " fields")

    def text(value, label):
        require(isinstance(value, str) and len(value) <= 4096 and not re.search(r"[\x00-\x1f\x7f]", value), label + " text type")
        require(not re.search(r"[\w.+-]+@[\w.-]+|(?<!\w)\d{11}(?!\w)|(?:\+48[ -]?)?(?:\d{3}[ -]){2}\d{3}(?!\d)", value), label + " privacy")

    def integer(value, label):
        require(type(value) is int and value >= 0, label + " nonnegative integer")

    def iso_date(value, label):
        require(isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) and parse_date(value) == value, label + " ISO date")

    def timestamp(value, label):
        require(isinstance(value, str), label + " timestamp type")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Invalid publication candidate: " + label + " timestamp") from exc
        offset = parsed.utcoffset()
        require("T" in value and parsed.tzinfo is not None and offset is not None and offset.total_seconds() == 0, label + " UTC timestamp")
        return parsed.timestamp()

    def string_list(value, label, pattern=None):
        require(isinstance(value, list), label + " list type")
        for item in value:
            text(item, label)
            if pattern:
                require(re.fullmatch(pattern, item), label + " identifier")
        require(len(value) == len(set(value)), label + " duplicates")

    fields(candidate, {"permits.json", "parcels.geojson", "metadata.json"}, "artifacts")
    permits, parcels, meta = (candidate[name] for name in ("permits.json", "parcels.geojson", "metadata.json"))
    fields(permits, {"schemaVersion", "generatedAt", "source", "records"}, "permits")
    fields(parcels, {"type", "generatedAt", "features"}, "GeoJSON")
    fields(meta, {"generatedAt", "recordCount", "parcelCount", "matchedRecordCount", "partialRecordCount",
                  "unresolvedRecordCount", "coverage", "warnings", "sources", "dateRange", "kindCounts",
                  "localityCounts", "rawStatistics", "geometryCoverage", "cadastralRegions", "unverifiedRegions",
                  "failedParcelIds", "privacy", "refreshPolicy", "publicEvidenceResponseCount"}, "metadata")
    require(type(permits["schemaVersion"]) is int and permits["schemaVersion"] == 1, "schema version")
    require(parcels["type"] == "FeatureCollection", "GeoJSON type")
    generated = timestamp(meta["generatedAt"], "generation")
    require(permits["generatedAt"] == parcels["generatedAt"] == meta["generatedAt"], "shared generatedAt")
    require(generated <= time.time(), "future generation")
    fields(meta["dateRange"], {"requestedStart", "requestedEnd", "actualStart", "actualEnd"}, "date range")
    date_range = meta["dateRange"]
    for key, value in date_range.items():
        iso_date(value, key)
    require(date_range["requestedStart"] <= date_range["actualStart"] <= date_range["actualEnd"] <= date_range["requestedEnd"], "date coverage bounds")
    for key in ("recordCount", "parcelCount", "matchedRecordCount", "partialRecordCount", "unresolvedRecordCount", "publicEvidenceResponseCount"):
        integer(meta[key], key)
    require(isinstance(permits["records"], list) and permits["records"], "records list")
    require(isinstance(parcels["features"], list) and parcels["features"], "features list")
    records, features = permits["records"], parcels["features"]
    record_ids, feature_ids, joins = set(), set(), defaultdict(set)
    for record in records:
        fields(record, RECORD_FIELDS, "record")
        for key in RECORD_FIELDS - {"decisionDate", "decisionNumber", "parcelIds", "parcelNumbers"}:
            text(record[key], "record " + key)
        kind = record["kind"]
        require(kind in {"application", "decision", "notification"}, "record kind")
        source_kind = "notification" if kind == "notification" else "permit"
        require(re.fullmatch(source_kind + r":[^\s:]+", record["id"]), "record ID/kind")
        require(record["id"] not in record_ids, "duplicate record ID")
        record_ids.add(record["id"])
        require(record["title"] in PUBLIC_TITLES and record["description"] == PUBLIC_DESCRIPTION, "fixed-vocabulary summary")
        require(record["sourceUrl"] == DOWNLOADS[source_kind], "record source URL")
        require(record["municipality"] == MUNICIPALITY, "record municipality")
        iso_date(record["applicationDate"], "applicationDate")
        if record["decisionDate"] is not None:
            iso_date(record["decisionDate"], "decisionDate")
        if record["decisionNumber"] is not None:
            text(record["decisionNumber"], "decisionNumber")
            require(bool(record["decisionNumber"]), "empty decision number")
        if kind == "decision":
            require(record["decisionDate"] is not None or record["decisionNumber"] is not None, "decision evidence")
            require(record["status"] == "Decyzja odnotowana — wynik nieudostępniony w CSV", "decision status")
        else:
            require(record["decisionDate"] is None and record["decisionNumber"] is None, "nondecision fields")
            statuses = NOTIFICATION_STATUSES | {UNKNOWN_STATUS, "Brak statusu w CSV"} if kind == "notification" else {"Wniosek — brak decyzji w CSV"}
            require(record["status"] in statuses, "allowlisted status")
        string_list(record["parcelNumbers"], "parcelNumbers")
        string_list(record["parcelIds"], "parcelIds", PARCEL_PATTERN)
        require(record["cadastralRegion"] == "Brak wiarygodnego obrębu w CSV" or
                re.fullmatch(REGION_PATTERN + r"(?:, " + REGION_PATTERN + r")*", record["cadastralRegion"]), "cadastralRegion")
        require(record["geometryStatus"] in {"matched", "partial", "unresolved"}, "geometry status")
        require(bool(record["parcelIds"]) == (record["geometryStatus"] != "unresolved"), "geometry status/join")
        note = re.fullmatch(r"Potwierdzone obrysy ULDK: ([0-9]+)/([0-9]+)\."
                            r"(?: niejednoznaczne lub nieprawidłowe odwołania w CSV: ([0-9]+)\.)?"
                            r"(?: Poza limitem bieżącego importu geometrii: ([0-9]+)\.)?"
                            r"(?: Brak wiarygodnej odpowiedzi ULDK: ([0-9]+) \(możliwy podział działki, błąd źródła lub usługi\)\.)?", record["geometryNote"])
        require(note is not None, "geometry note vocabulary")
        assert note is not None
        resolved, total, unknown, omitted, failed = (int(value or 0) for value in note.groups())
        require(resolved == len(record["parcelIds"]) and resolved + unknown + omitted + failed == total, "geometry note counts")
        expected_status = "matched" if total and total == resolved else ("partial" if resolved else "unresolved")
        require(record["geometryStatus"] == expected_status, "geometry note status")
        for ref in record["parcelIds"]:
            require(ref.rsplit(".", 1)[-1] in record["parcelNumbers"] and ".".join(ref.split(".")[:2]) in record["cadastralRegion"].split(", "), "record parcel provenance")
            joins[ref].add(record["id"])
    require(len(records) == meta["recordCount"], "recordCount")
    dates = sorted(record["applicationDate"] for record in records)
    require((dates[0], dates[-1]) == (date_range["actualStart"], date_range["actualEnd"]), "actual date range")
    for key, field in (("kindCounts", "kind"), ("localityCounts", "locality")):
        require(isinstance(meta[key], dict), key + " map")
        for label, count in meta[key].items():
            text(label, key)
            integer(count, key)
        require(meta[key] == dict(Counter(record[field] for record in records)), key + " totals")
    counts = Counter(record["geometryStatus"] for record in records)
    for key, status in (("matchedRecordCount", "matched"), ("partialRecordCount", "partial"), ("unresolvedRecordCount", "unresolved")):
        require(meta[key] == counts[status], key + " total")
    require(isinstance(meta["cadastralRegions"], list), "cadastralRegions list")
    regions = {}
    for region in meta["cadastralRegions"]:
        fields(region, {"id", "name", "municipality"}, "region")
        for key, value in region.items():
            text(value, "region " + key)
        require(re.fullmatch(REGION_PATTERN, region["id"]) and region["id"] not in regions and region["municipality"] == "Ożarów Mazowiecki", "verified region")
        regions[region["id"]] = region
    string_list(meta["unverifiedRegions"], "unverifiedRegions", REGION_PATTERN)
    require(not set(regions).intersection(meta["unverifiedRegions"]), "conflicting region status")
    for feature in features:
        fields(feature, {"type", "properties", "geometry"}, "feature")
        require(feature["type"] == "Feature", "feature type")
        props = feature["properties"]
        fields(props, {"id", "parcelNumber", "region", "permitIds", "sourceUrl"}, "feature properties")
        for key in ("id", "parcelNumber", "region", "sourceUrl"):
            text(props[key], "feature " + key)
        ref = props["id"]
        require(re.fullmatch(PARCEL_PATTERN, ref) and ref not in feature_ids, "unique exact parcel ID")
        feature_ids.add(ref)
        require(props["sourceUrl"] == uldk_url("GetParcelById", ref), "canonical parcel URL")
        require(props["parcelNumber"] == ref.split(".")[-1] and props["region"] == ref.split(".")[1], "parcel components")
        require(".".join(ref.split(".")[:2]) in regions, "parcel verified region")
        string_list(props["permitIds"], "permitIds")
        require(bool(props["permitIds"]) and set(props["permitIds"]) <= record_ids and set(props["permitIds"]) == joins[ref], "bidirectional parcel join")
        geometry = feature["geometry"]
        fields(geometry, {"type", "coordinates"}, "geometry")
        require(geometry["type"] in {"Polygon", "MultiPolygon"}, "polygon type")
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        require(isinstance(polygons, list) and polygons, "polygon coordinates")
        for polygon in polygons:
            require(isinstance(polygon, list) and polygon, "polygon rings")
            for ring in polygon:
                require(isinstance(ring, list) and len(ring) >= 4 and ring[0] == ring[-1], "closed unmodified ring")
                for point in ring:
                    require(isinstance(point, list) and len(point) == 2 and all(type(axis) in (float, int) for axis in point), "2D WGS84 coordinate types")
                    require(14 <= point[0] <= 25 and 49 <= point[1] <= 55, "WGS84 bounds")
        try:
            geom = shape(geometry)
        except (TypeError, ValueError, GEOSException) as exc:
            raise ValueError("Invalid publication candidate: malformed polygon") from exc
        require(not geom.is_empty and geom.is_valid, "valid nonempty polygon")
    require(set(joins) == feature_ids, "bidirectional record join")
    require(meta["parcelCount"] == len(features), "parcelCount")
    gc = meta["geometryCoverage"]
    fields(gc, {"candidateParcelCount", "attemptedParcelCount", "confirmedParcelCount", "failedParcelCount",
                "unattemptedParcelCount", "strategy", "maxParcels", "reusedParcelCount", "freshParcelCount",
                "downloadedAtStart", "downloadedAtEnd"}, "geometry coverage")
    for key in set(gc) - {"strategy", "downloadedAtStart", "downloadedAtEnd"}:
        integer(gc[key], key)
    require(gc["strategy"] == "newest applications first; full exact-ID validation", "geometry strategy")
    require(gc["confirmedParcelCount"] == len(features) and
            gc["confirmedParcelCount"] + gc["failedParcelCount"] == gc["attemptedParcelCount"] and
            gc["attemptedParcelCount"] + gc["unattemptedParcelCount"] == gc["candidateParcelCount"] and
            gc["reusedParcelCount"] + gc["freshParcelCount"] == gc["confirmedParcelCount"], "geometry coverage sums")
    require(gc["attemptedParcelCount"] == (min(gc["maxParcels"], gc["candidateParcelCount"]) if gc["maxParcels"] else gc["candidateParcelCount"]), "geometry cap")
    require(timestamp(gc["downloadedAtStart"], "geometry start") <= timestamp(gc["downloadedAtEnd"], "geometry end") <= generated, "geometry timestamps")
    string_list(meta["failedParcelIds"], "failedParcelIds", PARCEL_PATTERN)
    require(len(meta["failedParcelIds"]) == gc["failedParcelCount"] and not feature_ids.intersection(meta["failedParcelIds"]), "failed parcel counts")
    fields(meta["rawStatistics"], {"permit", "notification"}, "raw statistics")
    stat_fields = {"totalRows", "scopedRows", "dateFilteredRows", "invalidDateRows", "missingIdRows", "invalidParcelRows"}
    for kind, stats in meta["rawStatistics"].items():
        require(isinstance(stats, dict) and stat_fields <= set(stats) <= stat_fields | {"unknownNotificationStatusRows"}, "statistics fields")
        for key, value in stats.items():
            integer(value, "statistic " + key)
        require(stats["invalidDateRows"] == stats["missingIdRows"] == 0, "source integrity")
        require(stats["totalRows"] >= stats["scopedRows"] >= stats["dateFilteredRows"] + stats["invalidParcelRows"] and
                stats["scopedRows"] - stats["dateFilteredRows"] >= sum(record["sourceUrl"] == DOWNLOADS[kind] for record in records), "source statistics totals")
    fields(permits["source"], {"name", "url", "downloadedAt", "coverage"}, "permit source")
    require(permits["source"]["name"] == "GUNB RWDZ" and permits["source"]["url"] == GUNB + "pobranie.html", "permit source identity")
    for key in ("coverage", "privacy"):
        text(meta[key], "metadata " + key)
    require(permits["source"]["coverage"] == meta["coverage"], "source coverage")
    require("fixed-vocabulary summaries only" in meta["privacy"], "privacy policy")
    require(isinstance(meta["warnings"], list) and meta["warnings"], "warnings list")
    for warning in meta["warnings"]:
        text(warning, "warning")
    expected_docs = {GUNB + "mapa-api/": "GUNB — mapa i dostęp do CSV", GUNB + "pobranie.html": "GUNB — pliki CSV", ULDK + "opis.html": "GUGiK — dokumentacja ULDK"}
    require(isinstance(meta["sources"], list) and len(meta["sources"]) == 5, "sources list")
    seen_sources, source_times = set(), []
    for source in meta["sources"]:
        require(isinstance(source, dict) and isinstance(source.get("url"), str), "source type")
        url = source["url"]
        require(url not in seen_sources and url in set(expected_docs) | set(DOWNLOADS.values()), "source URL")
        seen_sources.add(url)
        if url in expected_docs:
            fields(source, {"name", "url"}, "documentation source")
            require(source["name"] == expected_docs[url], "documentation name")
        else:
            fields(source, {"name", "url", "downloadedAt", "sha256", "byteCount", "httpLastModified", "httpETag"}, "archive source")
            kind = next(kind for kind, value in DOWNLOADS.items() if value == url)
            require(source["name"] == "GUNB " + kind, "archive name")
            text(source["sha256"], "archive hash")
            require(re.fullmatch(r"[a-f0-9]{64}", source["sha256"]), "archive SHA256")
            integer(source["byteCount"], "archive bytes")
            require(0 < source["byteCount"] <= MAX_ARCHIVE_BYTES, "archive size")
            source_times.append(source["downloadedAt"])
            require(timestamp(source["downloadedAt"], "source download") <= generated, "source timestamp")
            for key in ("httpLastModified", "httpETag"):
                if source[key] is not None:
                    text(source[key], "source " + key)
    require(permits["source"]["downloadedAt"] == max(source_times), "latest source timestamp")
    policy = meta["refreshPolicy"]
    fields(policy, {"sourcesForced", "uldkTTLSeconds", "publicEvidenceCache", "rawSourceCacheShared", "maximumLossFraction"}, "refresh policy")
    require(type(policy["sourcesForced"]) is bool and policy["rawSourceCacheShared"] is False and
            type(policy["uldkTTLSeconds"]) is int and policy["uldkTTLSeconds"] == GEOMETRY_TTL_SECONDS and
            policy["publicEvidenceCache"] == "scripts/uldk-cache.json" and policy["maximumLossFraction"] == 0.2, "refresh policy values")
    if evidence is not None:
        fields(evidence, {"schemaVersion", "responses"}, "evidence")
        require(type(evidence["schemaVersion"]) is int and evidence["schemaVersion"] == 1 and isinstance(evidence["responses"], list), "evidence schema")
        entries = {}
        for entry in evidence["responses"]:
            checked = verify_public_cache_entry(entry)
            require(checked["url"] not in entries, "duplicate evidence URL")
            require(timestamp(checked["downloadedAt"], "evidence timestamp") <= generated, "evidence after generation")
            entries[checked["url"]] = checked
        expected = {uldk_url("GetCommuneById", unit, "id,commune,county") for unit in UNITS}
        expected.update(uldk_url("GetRegionById", region, "id,region,commune") for region in regions)
        expected.update(uldk_url("GetParcelById", ref) for ref in feature_ids)
        require(set(entries) == expected and len(entries) == meta["publicEvidenceResponseCount"], "exact evidence coverage/count")
        geometry_times = []
        for feature in features:
            props = feature["properties"]
            entry = entries[props["sourceUrl"]]
            require(feature["geometry"] == parse_uldk(entry["text"], props["id"]), "geometry differs from exact ULDK evidence")
            geometry_times.append(entry["downloadedAt"])
        require((min(geometry_times), max(geometry_times)) == (gc["downloadedAtStart"], gc["downloadedAtEnd"]), "geometry evidence timestamps")
        for region, value in regions.items():
            entry = entries[uldk_url("GetRegionById", region, "id,region,commune")]
            require(region_validator(region)(entry["text"]) == value, "region evidence")
    return True


def publish_transaction(output, artifacts, client, evidence_path, evidence_urls, evidence):
    """Stage evidence; commit it and the generation with byte-exact rollback.

    Paths may live on different filesystems: each backup/stage stays beside its
    own target. This is rollback on caught failures, not cross-path crash atomicity.
    """
    validate_artifacts(artifacts, evidence=evidence)
    validate_publication(output, artifacts["metadata.json"])
    output, evidence_path = Path(output), Path(evidence_path)
    require_private_evidence_path(output, evidence_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".publication-", dir=output.parent) as data_temp, \
         tempfile.TemporaryDirectory(prefix=".evidence-", dir=evidence_path.parent) as cache_temp:
        data_backup = Path(data_temp) / "previous"
        cache_backup = Path(cache_temp) / "previous"
        cache_stage = Path(cache_temp) / evidence_path.name
        data_stage = Path(data_temp) / "candidate"
        had_data, had_cache = output.exists(), evidence_path.exists()
        if had_data:
            shutil.copytree(output, data_backup)
        if had_cache:
            shutil.copy2(evidence_path, cache_backup)
        # Export really writes the staged path; do not bypass the export contract.
        count = client.export_public_cache(cache_stage, evidence_urls)
        staged = json.loads(cache_stage.read_text())
        if staged != evidence or count != artifacts["metadata.json"]["publicEvidenceResponseCount"]:
            raise ValueError("Evidence changed during staging; previous publication retained")
        stage_artifacts(data_stage, artifacts)
        staged_artifacts = {path.name: json.loads(path.read_text()) for path in data_stage.iterdir()}
        validate_artifacts(staged_artifacts, evidence=staged)
        cache_started = data_started = False
        try:
            cache_started = True
            os.replace(cache_stage, evidence_path)
            data_started = True
            atomic_publish(output, staged_artifacts, prepared_stage=data_stage)
        except BaseException:
            if data_started:
                # Do not call the failing writer again to perform rollback.
                if output.exists():
                    os.replace(output, Path(data_temp) / "rejected")
                if had_data:
                    os.replace(data_backup, output)
            if cache_started:
                if had_cache:
                    if not evidence_path.exists() or evidence_path.read_bytes() != cache_backup.read_bytes():
                        os.replace(cache_backup, evidence_path)
                elif evidence_path.exists():
                    evidence_path.unlink()
            raise


def require_private_evidence_path(output, evidence_path):
    path = Path(evidence_path).resolve()
    if path.is_relative_to((ROOT / "public").resolve()) or path.is_relative_to(Path(output).resolve()):
        raise ValueError("Public ULDK evidence must stay outside the published dataset/assets")


def validate_publication(output, metadata):
    """Fail closed before replacing a generation on omissions or >20% data loss."""
    if any(stats.get("invalidDateRows", 0) or stats.get("missingIdRows", 0) for stats in metadata["rawStatistics"].values()):
        raise ValueError("Source integrity failure: scoped rows lack valid dates or system IDs")
    previous_path = Path(output) / "metadata.json"
    if not previous_path.exists():
        return
    previous = json.loads(previous_path.read_text())
    prior_range = previous["dateRange"]
    current_range = metadata["dateRange"]
    if current_range["requestedStart"] != prior_range["requestedStart"] or current_range["requestedEnd"] < prior_range["requestedEnd"]:
        raise ValueError("Refusing to narrow a published date range; use a separate --output")
    for key in ("recordCount", "parcelCount"):
        if metadata[key] < previous[key] * 0.8:
            raise ValueError(f"Suspicious data loss in {key}; previous generation retained")
    # A disappearing source category must not be hidden by growth in another.
    for group in ("notification", "permit"):
        kinds = ("notification",) if group == "notification" else ("application", "decision")
        old = sum(previous.get("kindCounts", {}).get(kind, 0) for kind in kinds)
        new = sum(metadata["kindCounts"].get(kind, 0) for kind in kinds)
        if new < old * 0.8:
            raise ValueError(f"Suspicious data loss in GUNB {group}; previous generation retained")


def run(args):
    if parse_date(args.since) != args.since or parse_date(args.until) != args.until or args.since > args.until:
        raise ValueError("Require valid ISO dates: since <= until")
    cache = Path(args.cache).resolve()
    if cache.is_relative_to((ROOT / "public").resolve()) or cache.is_relative_to(Path(args.output).resolve()):
        raise ValueError("Raw source cache must remain private, outside all public output/assets")
    require_private_evidence_path(args.output, args.uldk_public_cache)
    client = CachedHTTP(args.cache, refresh=args.refresh, offline=args.offline, refresh_sources=args.refresh_sources)
    seeded = client.seed_public_cache(args.uldk_public_cache)
    print(f"Seeded validated public ULDK evidence: {seeded} (TTL <= 30 days)", flush=True)
    # Units come from the source columns, not guessed from locality strings.
    for unit in sorted(UNITS):
        client.text(uldk_url("GetCommuneById", unit, "id,commune,county"), verify_commune)
    records = []
    statistics = {}
    archives = []
    for kind, url in DOWNLOADS.items():
        archive = client.download(url)
        extracted, stats = normalize_rows(read_csv_zip(archive, kind), kind, args.since, args.until)
        if not extracted:
            raise ValueError(f"No scoped {kind} records: refusing to overwrite prior data")
        records.extend(extracted)
        statistics[kind] = stats
        archives.append({"name": "GUNB " + kind, **client.archive_evidence(url, archive)})
    records.sort(key=lambda r: (r["applicationDate"], r["id"]), reverse=True)
    candidates = list(dict.fromkeys(ref for r in records for ref in r["_parcelRefs"]))
    # Keep full record coverage; cap only the expensive geometries, newest records first.
    chosen = candidates if args.max_parcels == 0 else candidates[:args.max_parcels]
    regions = {}
    region_errors = {}
    for region in sorted({ref.rsplit(".", 1)[0].split(".AR_")[0] for ref in chosen}):
        try:
            validator = region_validator(region)
            regions[region] = validator(client.text(uldk_url("GetRegionById", region, "id,region,commune"), validator))
        except ValueError as exc:
            region_errors[region] = str(exc)
    geometries = {}
    errors = {}
    def fetch(ref):
        region = ".".join(ref.split(".")[:2])
        if region not in regions:
            return ref, None, "Unverified cadastral region"
        url = uldk_url("GetParcelById", ref)
        try:
            text = client.text(url, lambda t: parse_uldk(t, ref))
            return ref, parse_uldk(text, ref), None
        except ValueError as exc:
            return ref, None, str(exc)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(fetch, ref) for ref in chosen]
        for completed, future in enumerate(as_completed(futures), 1):
            ref, geometry, error = future.result()
            if geometry is not None:
                geometries[ref] = geometry
            else:
                errors[ref] = error
            if completed % 25 == 0 or completed == len(chosen):
                print(f"ULDK {completed}/{len(chosen)}; confirmed={len(geometries)}; unresolved={len(errors)}", flush=True)
    if chosen and not geometries:
        raise ValueError("No verified parcel geometries; previous dataset retained")
    features = attach_geometry(records, geometries, errors)
    geometry_downloads = sorted(client.entry(uldk_url("GetParcelById", ref))["downloadedAt"] for ref in geometries)
    generated = utc_now()
    dates = sorted(r["applicationDate"] for r in records)
    coverage = f"Cała gmina Ożarów Mazowiecki (miasto i obszar wiejski): daty wpływu {args.since}–{args.until}; faktyczne wpisy {dates[0]}–{dates[-1]}. Wnioski/decyzje: CSV mazowieckie; zgłoszenia: CSV krajowy od 2022. Obrysy ze stanu ULDK podczas pobrania (cache do 30 dni), nie historyczne."
    warnings = [
        "Decyzja w CSV nie oznacza pozwolenia: eksport nie podaje wyniku rozstrzygnięcia. Wniosek i zgłoszenie są odrębnymi rodzajami wpisów.",
        "Powtarzające się wiersze działek połączono według identyfikatora systemowego GUNB; wniosek z odnotowaną decyzją to jeden wpis typu decyzja.",
        "CSV może zawierać błędy/nieaktualne numery działek; nie korygowano identyfikatorów według nazw miejscowości.",
        "Import obejmuje datę wpływu w wybranym zakresie, nie wszystkie decyzje wydane w tym okresie dla starszych wniosków; brak danych sprzed zakresu.",
    ]
    if not any(r["kind"] == "application" for r in records):
        warnings.append("W bieżącym wycinku CSV każdy wniosek ma odnotowaną decyzję; nie ma wpisów typu sam wniosek. Nie oznacza braku nierozpatrzonych wniosków w gminie — eksport CSV nie gwarantuje ich kompletności.")
    if len(chosen) < len(candidates):
        warnings.append(f"Limit importu obrysów: sprawdzono {len(chosen)} z {len(candidates)} unikalnych prawidłowych odwołań z CSV (najnowsze wpisy najpierw). Reszta nie jest udawana ani oznaczona jako dopasowana.")
    if errors:
        warnings.append(f"ULDK nie potwierdził {len(errors)} odwołań po ograniczonych próbach. Mogą to być zmienione działki, błędy CSV lub odpowiedzi usługi.")
    invalid = sum(s["invalidParcelRows"] for s in statistics.values())
    if invalid:
        warnings.append(f"Nieprawidłowe, obce lub niejednoznaczne odwołania katastralne: {invalid} wierszy CSV; zachowano wpisy wybrane po TERC bez zgadywania geometrii.")
    counts = Counter(r["geometryStatus"] for r in records)
    reused_geometry_count = sum(uldk_url("GetParcelById", ref) in client.cache_hits for ref in geometries)
    metadata = {
        "generatedAt": generated, "recordCount": len(records), "parcelCount": len(features),
        "matchedRecordCount": counts["matched"], "partialRecordCount": counts["partial"], "unresolvedRecordCount": counts["unresolved"],
        "coverage": coverage, "warnings": warnings,
        "sources": [{"name": "GUNB — mapa i dostęp do CSV", "url": GUNB + "mapa-api/"},
                    {"name": "GUNB — pliki CSV", "url": GUNB + "pobranie.html"},
                    {"name": "GUGiK — dokumentacja ULDK", "url": ULDK + "opis.html"}] + archives,
        "dateRange": {"requestedStart": args.since, "requestedEnd": args.until, "actualStart": dates[0], "actualEnd": dates[-1]},
        "kindCounts": dict(Counter(r["kind"] for r in records)),
        "localityCounts": dict(sorted(Counter(r["locality"] for r in records).items())),
        "rawStatistics": statistics,
        "geometryCoverage": {"candidateParcelCount": len(candidates), "attemptedParcelCount": len(chosen), "confirmedParcelCount": len(features),
                             "failedParcelCount": len(errors), "unattemptedParcelCount": len(candidates) - len(chosen),
                             "strategy": "newest applications first; full exact-ID validation", "maxParcels": args.max_parcels,
                             "reusedParcelCount": reused_geometry_count, "freshParcelCount": len(geometries) - reused_geometry_count,
                             "downloadedAtStart": geometry_downloads[0] if geometry_downloads else None,
                             "downloadedAtEnd": geometry_downloads[-1] if geometry_downloads else None},
        "cadastralRegions": list(regions.values()), "unverifiedRegions": sorted(region_errors),
        "failedParcelIds": sorted(errors),
        "privacy": "Investor/designer fields excluded. Source free-text titles/descriptions are never published; fixed-vocabulary summaries only. Raw ZIP/CSV private and excluded from Actions caches.",
        "refreshPolicy": {"sourcesForced": args.refresh_sources or args.refresh, "uldkTTLSeconds": GEOMETRY_TTL_SECONDS,
                          "publicEvidenceCache": "scripts/uldk-cache.json", "rawSourceCacheShared": False,
                          "maximumLossFraction": 0.2},
    }
    permits = {"schemaVersion": 1, "generatedAt": generated,
               "source": {"name": "GUNB RWDZ", "url": GUNB + "pobranie.html", "downloadedAt": max(a["downloadedAt"] for a in archives), "coverage": coverage},
               "records": records}
    evidence_urls = ([uldk_url("GetCommuneById", unit, "id,commune,county") for unit in sorted(UNITS)]
                     + [uldk_url("GetRegionById", region, "id,region,commune") for region in sorted(regions)]
                     + [uldk_url("GetParcelById", ref) for ref in sorted(geometries)])
    evidence = client.public_cache_payload(evidence_urls)
    metadata["publicEvidenceResponseCount"] = len(evidence["responses"])
    artifacts = {"permits.json": permits,
                 "parcels.geojson": {"type": "FeatureCollection", "generatedAt": generated, "features": features},
                 "metadata.json": metadata}
    publish_transaction(args.output, artifacts, client, args.uldk_public_cache, evidence_urls, evidence)
    print(json.dumps({key: metadata[key] for key in ("recordCount", "parcelCount", "matchedRecordCount", "partialRecordCount", "unresolvedRecordCount", "kindCounts", "geometryCoverage")}, ensure_ascii=False, indent=2))
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2025-01-01", help="Application receipt date inclusive")
    parser.add_argument("--until", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--max-parcels", type=int, default=0, help="Unique exact IDs to attempt; 0 (default) means all")
    parser.add_argument("--workers", type=int, default=4, help="ULDK concurrency, bounded 1–6")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--refresh", action="store_true", help="Refresh all source and successful ULDK caches from official services")
    parser.add_argument("--refresh-sources", action="store_true", help="Force fresh GUNB ZIPs; keep validated positive ULDK cache within 30-day TTL")
    parser.add_argument("--uldk-public-cache", type=Path, default=PUBLIC_ULDK_CACHE, help="Privacy-safe tracked exact ULDK response evidence; never raw CSV")
    parser.add_argument("--offline", action="store_true", help="Use verified cached source/ULDK responses only; geometry TTL still enforced")
    args = parser.parse_args()
    if not 1 <= args.workers <= 6 or args.max_parcels < 0 or (args.offline and (args.refresh or args.refresh_sources)):
        parser.error("workers must be 1–6; max-parcels >= 0; offline and refresh/refresh-sources are incompatible")
    try:
        run(args)
    except (ValueError, OSError, requests.RequestException, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Import failed; previous published artifacts preserved: {exc}\n")


if __name__ == "__main__":
    main()
