# Radar Ożarów — kontrakt rozszerzenia (v1)

## Cel i bramki

Użytkownik autoryzuje dodanie możliwie wszystkich dostępnych, sprawdzonych informacji o inwestycjach w całej gminie oraz zmianę nazwy repo/strony. Produkt: **Radar Ożarów**, repo `radar-ozarow`, prefix `/radar-ozarow/`. Zachować istniejący Atlas GIS, GUNB/ULDK, wszystkie regresje, CSV, telefon list→map i codzienne odświeżanie. Nie jest to ponowny turniej prototypów.

Zakres źródeł: (1) komplet gminnego ArcGIS, (2) pełne zastępujące tabele budżetu/WPF i ich źródła, (3) odkryte zamówienia i dokumenty, (4) wszystkie karty BO i wyniki, (5) aktualności o inwestycjach, (6) komplet rocznika BIP środowiskowego, (7) sprawdzone prospekty/inwestorzy i projekty ponadlokalne, (8) komplet lokalnych umów FE według miejsca realizacji. Pokrycie każdego źródła liczyć w kodzie i ujawnić niepokryte/niezlokalizowane dane.

Pre-flight: czyste, aktualne main; wspólny model i rozłączna własność plików. Revision: integracja i realne testy; błędy wracają do implementera. Publication: niezależne SPEC, potem QUALITY/security, niezmienne fingerprinty, PR CI, merge, rename, Pages i kontrola live. Abort: nie publikować niezweryfikowanych danych, sekretów, sztucznych geometrii lub zmiany z niespełnionymi bramkami.

## Artefakt przeglądarki

Samowystarczalny `public/data/investments.json`, bez zmiany kontraktu istniejących trzech plików GUNB. Dane i geometrie inwestycji w jednym JSON wykluczają połączenie różnych generacji. Nie wymaga zgodności daty generacji z niezależnym GUNB.

```ts
interface InvestmentDataset {
  schemaVersion: 1;
  generatedAt: string; // ISO8601 UTC
  records: InvestmentRecord[];
  sources: InvestmentSource[];
  warnings: string[];
  counts: { records: number; mapped: number; geometries: number; bySource: Record<string, number> };
}
interface InvestmentSource {
  id: string; name: string; url: string;
  fetchedAt: string | null; sourceUpdatedAt: string | null;
  status: 'fresh' | 'retained' | 'static' | 'unavailable';
  coverage: string; recordCount: number; warnings: string[];
  reuse: string; // fakty/atrybucja, bez nieustalonej licencji na opisy i zdjęcia
}
interface InvestmentRecord {
  id: string; // source-prefix + literal source record ID, unikalny globalnie
  sourceId: string; sourceRecordId: string; sourceUrl: string;
  title: string;
  recordType: 'project' | 'budget-task' | 'procurement' | 'funding' | 'planning-case' | 'proposal' | 'news' | 'regional';
  investor: 'municipal' | 'county' | 'national' | 'private' | 'mixed' | 'unknown';
  investorName: string | null;
  category: string; locality: string; address: string;
  status: string; statusAsOf: string | null; summary: string;
  years: number[];
  costs: { kind: string; amount: number | null; currency: string; label: string; year: number | null; scope: 'local' | 'multi-municipality' | 'unknown'; sourceUrl: string }[];
  dates: { kind: string; date: string; label: string; sourceUrl: string }[]; // prawdziwa data YYYY-MM-DD, nie guessed Jan 1 for year-only
  geometries: { type: 'Feature'; geometry: GeoJSON.Point | GeoJSON.MultiPoint | GeoJSON.Polygon | GeoJSON.MultiPolygon | GeoJSON.LineString | GeoJSON.MultiLineString; properties: { id: string; accuracy: 'source-point' | 'parcel' | 'project-footprint' | 'route' | 'marketing'; sourceUrl: string; parcelId: string | null; note: string; fetchedAt: string; sourceUpdatedAt: string | null } }[];
  parcelIds: string[]; // wyłącznie literalne poprawne identyfikatory; geometry tylko potwierdzone ULDK
  events: { id: string; title: string; date: string | null; sourceUrl: string }[];
  facts: { label: string; value: string; sourceUrl: string }[];
  relatedIds: string[]; // tylko udokumentowane powiązania, nigdy nearest/tentative match
  warnings: string[];
  fetchedAt: string; sourceUpdatedAt: string | null;
}
```

Wszystkie powyższe klucze wymagane; puste listy/puste stringi/null jako jawne braki, bez nadmiarowych kluczy. Prawidłowe URL tylko https/http bez userinfo, unsafe schemes i sekretów. Source metadata timestamps ISO; rekordowe `statusAsOf` data YYYY-MM-DD lub null. `sourceUpdatedAt` ISO lub null. Koszty nieujemne, finite; brak to null, nie zero. Zalecane money kinds: `reported`, `annual-plan`, `total-outlay`, `annual-limit`, `tender-financing`, `offer`, `contract`, `actual`, `project-total`, `eu-contribution`, `eligible`, `proposal-estimate`. Nie sumować różnego rodzaju kwot ani kosztów wielu źródeł tego samego przedsięwzięcia.

Liczniki oznaczają **rekordy źródłowe**, nie unikalne budowy. Jedna sprawa środowiskowa grupuje wiele publikacji w events. Między źródłami nie scalać na fuzzy title; używać udokumentowanych relatedIds. Nie wmawiać, że budżet, zgłoszenie BO, grant lub postępowanie oznacza rozpoczętą budowę. Prywatne B+R i projekty wielogminne są także informacją, niekoniecznie fizyczną inwestycją.

## API adapterów / rozłączna własność

Każdy adapter `scripts/investment_sources/{municipal,public,private}.py` udostępnia:

```python
def collect(cache: pathlib.Path, prior: dict | None = None) -> dict:
    # real retrieval + validation; return {'records': [...], 'sources': [...], 'warnings': [...]}
```

Każdy moduł sam rozróżnia błąd od pustego źródła. Błędy pojedynczego źródła: zachowaj zweryfikowane prior records tego sourceId, status retained i jawny warning bez udawania świeżego pobrania; brak previous → unavailable. Błędy truncation/schema/duplikatów/loss >20% nie zastępują pełnego snapshotu. Importer centralny odpowiada za walidację całości, counts i transakcyjny zapis pojedynczego artefaktu. Testować offline przez mock faktycznych fixtures; próba realnego importu osobno.

Agent municipal: `municipal.py`, testy `tests/investments/test_municipal.py`, własne fixtures/docs/evidence. Agent public: `public.py`, public-only fixtures/testy/docs; parser przyjętych PDF budżetu/WPF, BO, zamówienia, aktualności. Agent private: `private.py`, private-only fixtures/testy/docs; FE, środowisko, prospekt, projekty ponadlokalne, exact ULDK. Agent UI: `src/Investments*.{ts,tsx}`, `src/investments*.ts`, App/ParcelMap/styles i własne nowe UI testy. Agent pipeline: importer/validator/CLI, `__init__.py`, dependency lists, workflows/dist/new pipeline testy, index/vite/package/README/source doc rebranding. Rodzic: kontrakt, integracja, dowody, git/API/PR/publikacja; nie nadpisuje cudzej implementacji podczas pracy.

## Semantyka i ekspozycja

- ArcGIS: raw versus retained counts, exclusion Kolejnosc=-1 zgodnie z frontendem; bounded pagination/count/IDs/transfer limits; real point, border outlier warning.
- `fetchedAt` nie zastępuje daty źródła; czerwcowy status nie jest potwierdzeniem w październiku. Nowy news zachować jako dowód/zdarzenie, nie wymazywać źródłowej historii.
- BO: edition2026 versus implementation2027; markers only z karty, zero city-center fallbacks; wybrany/propozycja/wykonany odrębne.
- BIP: complete list pagination/total; typed costs i event identities; literal region tokens, bez naprawiania 001/011. ULDK odpowiedź exact ID/region/municipality/SRID4326/valid geometry z oryginalnym download timestamp.
- FE: local place of implementation, nie siedziba; contract ID unikalny; multi-municipality koszt total wyraźnie opisany i nieprzypisany cały do gminy; bez guessed points.
- Nie publikować technicznych Creator/Editor, kontaktów osobistych, cookies/tokens, private cache, PDF descriptions/photos/marketing geometry bez ustalonych praw. Faktyczne tytuły/nazwy/kwoty/daty i krótkie własne streszczenia z attribution; dokumenty i zdjęcia linkowane do źródła, nie mirrorowane.
- Brak geometrii pozostaje na liście; pinezka źródłowa, działka ULDK i trasa zawsze jawnie rozróżnione. Działka nie równa się project-footprint.

## UX / automatyzacja

Czytelny przełącznik Pozwolenia / Inwestycje w istniejącym Atlas; zachować działającą mapę Leaflet i focus. Inwestycje: wyszukiwanie nazwa/adres/działka/numer sprawy, filtry source/investor/category/status/year/mapping, jeden zestaw wyników dla mapy/listy/count/CSV. Domyślnie wszystkie lata dla inwestycji (stare mapa/plany nie mogą zniknąć przez filtr recent GUNB). Szczegóły: status i data, źródłowa aktualność, koszty z typem/zakresem, daty, fakty, zdarzenia, dokumenty, geometria i ostrzeżenia. Pozwolenia zachowują domyślny rolling3months. Nawigacja telefon: geolocated list→map + framing; unmapped list→detail; same-ID reselect, close/Escape focus i mapę przywrócić. CSV bez formuł i zgodny z listą, bez globalnie sumowanej mylącej kwoty.

Codzienny workflow odświeża GUNB i inwestycje, commit wszystkich zadeklarowanych artefaktów i walidowanego ULDK evidence; raw/cache poza repo/dist. Utrzymać least permissions, concurrency, immutable SHA, baseline guards, rollback i deploy w tym samym run po GITHUB_TOKEN push. Rok menu BIP oraz FE snapshot odkrywać z aktualnych oficjalnych stron lub oznaczać static z rzeczywistą datą, nigdy zgadywać URL/ID. Dokumenty kuratorowane mogą być static, ale jawnie i z procedurą ponownej kontroli.
