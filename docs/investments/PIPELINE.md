# Radar Ożarów — pipeline inwestycji i kontrakt publikacji

## Artefakty i API

Publiczny build zawiera dokładnie cztery pliki: `permits.json`, `parcels.geojson`, `metadata.json` i `investments.json`. Trzy pierwsze zachowują istniejący kontrakt i wspólne `generatedAt`. Inwestycje mają niezależne `generatedAt`; rekordy i geometrie inline w **jednym JSON** eliminują mieszanie generacji po stronie przeglądarki. Poza buildem można śledzić wyłącznie istniejący, zweryfikowany `scripts/uldk-cache.json` jako dowód ULDK. Surowe archiwa historyczne `data/full/` nie są codziennie odświeżane i nigdy nie trafiają do `dist/`.

Każdy z modułów `scripts/investment_sources/{municipal,public,private}.py` musi implementować:

```python
def collect(cache: pathlib.Path, prior: dict | None = None) -> dict:
    return {'records': [...], 'sources': [...], 'warnings': [...]}
```

`prior` jest **pełnym poprzednim zweryfikowanym artefaktem inwestycji**, nie częścią jednego źródła i nie snapshotem GUNB. Importer podaje każdemu adapterowi osobną kopię, więc adapter nie może zmienić podstawy porównania innemu źródłu. Brak modułu/`collect` blokuje import. Nie ma produkcyjnych stubów, sztucznych świeżych pustych źródeł ani niezweryfikowanej flagi `--offline`.

Schema v1 i semantyka każdego pola są w [../INVESTMENT_CONTRACT.md](../INVESTMENT_CONTRACT.md). Wspólny moduł `scripts/investment_validation.py` udostępnia `validate_record`, `validate_dataset`, `load_dataset` i bezpieczny parser `loads`. Walidator jest czysty: nie pobiera dokumentów ani nie naprawia identyfikatorów.

## Walidacja fail-closed

- Wszystkie pola są wymagane; dokładne allowlisty obejmują dataset, rekord, źródło, koszty, daty, zdarzenia, fakty, Feature, geometrię, jej properties i liczniki. Dodatkowe pola kontaktowe/techniczne/sekretne są błędem, także głęboko zagnieżdżone.
- Typy są ścisłe: boolean nie jest liczbą; enumy `recordType`, `investor`, `status`, `accuracy` i zakres kosztu nie dopuszczają alternatywnych etykiet. Koszt to finite nieujemna liczba lub null; null nie jest zerem. Money-kind pozostaje źródłowym stringiem, nie zgadywaną kategorią.
- Daty to rzeczywiste `YYYY-MM-DD`, znaczniki czasu mają strefę; `generatedAt` jest UTC. Nie tworzymy 1 stycznia dla informacji zawierającej wyłącznie rok.
- Każdy URL używa http/https, bez userinfo, znaków kontrolnych, unsafe schematu i parametrów zawierających sekrety. Parser JSON odrzuca powtórzone klucze i NaN/Infinity.
- Sześć dozwolonych geometrii GeoJSON musi być niepustych, poprawnych topologicznie i 2D WGS84. Polygon ma zamknięte ringi; współrzędne nie są naprawiane przez Shapely. `accuracy=parcel` wymaga wielokąta i dokładnego literalnego lokalnego ID, zadeklarowanego w `parcelIds`. Dowód pobrania ULDK nadal jest odpowiedzialnością adaptera — zgodność samej geometrii z formatem nie dowodzi pochodzenia.
- Globalne ID rekordów/źródeł oraz pary `(sourceId, sourceRecordId)` są unikalne. Feature ID i event ID są unikalne **wewnątrz rekordu**, nie globalnie. `relatedIds`, jeśli niepuste, muszą wskazywać dokładne istniejące inne rekordy; importer nie tworzy takich relacji sam.
- Counts są obliczane z rekordów/geometrii, z jawnym zerem dla zadeklarowanego niedostępnego źródła; `source.recordCount` musi odpowiadać joinowi. Jedno rosnące źródło nie ukrywa zaniku innego.
- Poprzednie źródło nie może zniknąć. Spadek jego rekordów **lub geometrii większy niż 20%** blokuje publikację; dokładnie 20% jest dozwolone. Adapter może zamiast tego jawnie zachować poprzednie zweryfikowane dane jako retained.

## Świeżość i błędy źródeł

`fresh` oznacza rzeczywiste udane pobranie i niepusty, zweryfikowany wkład. `static` jest właściwe dla kuratorowanego dokumentu z rzeczywistą datą dowodu, gdy nie wdrożono aktualnego odkrywania kolejnych wersji. `retained` wymaga ostrzeżenia, dokładnie poprzednich rekordów i zachowanych dowodowych dat/metadata; nowy opis nie jest aktualizacją zatrzymanych danych. `unavailable` bez wcześniejszych rekordów ma zero, null `fetchedAt` i ostrzeżenie. Pełny import bez żadnych zweryfikowanych rekordów jest błędem, nie inicjalizuje pustej produkcji.

Błędy schematu, truncation, duplikaty i utrata pokrycia nie są cichymi optional skips. Adapter ma rozpoznać je i zachować zweryfikowany prior lub zgłosić błąd. Importer nie przechwytuje dowolnego wyjątku adaptera, aby produkować fikcyjne źródło sukcesu. Testy prawdziwego `public/data/investments.json` są obowiązkowe i failują przy jego braku; fixtures adapterów pozostają tylko w testach.

Pełne pokrycie inwestycji w gminie nie jest ustalone. Pokrycie konkretnego katalogu/dokumentu trzeba opisać w `coverage` i ostrzeżeniach. Aktualny stan fazy budowy, budżetowanie, grant, przetarg, propozycja BO i realizacja są odrębnymi informacjami. Nie sumować kwot różnych typów ani globalnej kwoty projektu wielogminnego jako lokalnego kosztu.

## CLI i zapis

```bash
python3 -m venv .cache/venv
.cache/venv/bin/python -m pip install -r requirements-data.txt
.cache/venv/bin/python -m pip check

# Katalog roboczy poza repo/public/dist; prywatne dowody źródłowe, nigdy cookies/credentials.
.cache/venv/bin/python scripts/import_investments.py \
  --cache "${TMPDIR:?}/radar-ozarow-investments" --output public/data

# Sam odczyt/walidacja, bez sieci i zapisu:
.cache/venv/bin/python scripts/import_investments.py --validate public/data/investments.json
```

`--output` jest katalogiem; importer zapisuje **wyłącznie** `investments.json`, nie rusza innych plików. `--cache` nie może być pod repozytorium, outputem ani przez symlink. Cache jest prywatnym katalogiem 0700 dla pracy adapterów. Może zawierać rzeczywiste surowe odpowiedzi JSON/HTML/PDF/XLSX/WKT oraz sumy kontrolne i znaczniki pobrania potrzebne do audytu proweniencji; te dowody pozostają poza repozytorium i artefaktami publicznymi. Nie wolno zachowywać cookies, nagłówków uwierzytelnienia ani credentials. W Actions prywatny cache znajduje się wyłącznie w `$RUNNER_TEMP`, bez uploadu lub współdzielonego cache. `--prior /path/investments.json` wskazuje istniejący, oddzielnie zachowany poprzedni artefakt podczas wspólnego odświeżania.

Kandydat jest walidowany, serializowany deterministycznie (records/sources według ID, warnings bez duplikatów), zapisany do tymczasowego pliku w tym samym output, flush/fsync, ponownie odczytany i walidowany przed `os.replace`. Błąd walidacji, zapisu lub zamiany pozostawia poprzednie bajty artefaktu. Nie ma okna z osobną publikacją geometrii. Nie deklarujemy odporności na utratę zasilania: fsync pliku + atomowe zastąpienie nie gwarantuje trwałości wpisu katalogowego na każdym filesystemie.

## Codzienny refresh — kolejność ma znaczenie

1. Checkout niezmiennego `github.sha`; Node 22 i Python 3.12; `npm ci`, dokładnie przypięte zależności Python. Jeden wspólny workflow-level lock main, least permissions i brak prywatnego Actions cache.
2. Kopia całego prior `public/data/` do `$RUNNER_TEMP/data-candidate` i kopia dowodów ULDK. **Oddzielna kopia prior investments przed GUNB**: importer GUNB zastępuje cały katalog output i usunąłby sąsiedni JSON.
3. GUNB: rzeczywiste źródła, cały zakres od `2025-01-01` do zamrożonej daty UTC, wszystkie poprawne działki, pierwotne guards zachowane. Output i evidence są stagingiem.
4. Inwestycje: trzy rzeczywiste adaptery, ten sam candidate output, oddzielny zachowany prior dla source-loss/retention guards. Każda awaria przed swapem publicznym pozostawia repozytoryjny snapshot i evidence niezmienione.
5. Przeniesienie starego `public/data/` do runner backup, trap ERR, candidate/evidence do celów. Testy GUNB, walidacja inwestycji, wszystkie testy inwestycji/workflow, frontend, build i check_dist. Obsługiwany błąd przywraca **cały** stary katalog i poprzedni evidence. Jest to rollback dwóch celów, nie transakcja odporna na kill/power loss; dotychczasowy hosting nie jest modyfikowany przez nieudany run.
6. Allowlista commitu: dokładnie cztery publiczne pliki i `scripts/uldk-cache.json`. Odmowa dla nieoczekiwanych tracked/staged/untracked zmian. Explicit `git add` tylko allowlisty, fast-forward push, weryfikacja remote SHA.
7. `check_dist` wymaga dokładnie czterech plików i zgodności bajtowej każdego z verified public source. Dotychczasowe zakazy raw/cache, hidden paths, symlinków/hardlinków, nieznanych rootów i typów assets pozostają aktywne.
8. Pages gated przez main i `PAGES_ENABLED=true`; configure nie włącza hostingu samodzielnie. Deploy w **tym samym runie** po pushu GITHUB_TOKEN i tylko jeżeli main nadal odpowiada verified snapshot SHA. Nie polegamy na drugim push-workflow.

Harmonogram: **03:23 UTC**, `23 3 * * *`, plus ręczny `workflow_dispatch`. Nazwa workflow opisuje refresh wszystkich źródeł Radaru. Lokalne zmiany kodu nie zmieniają nazwy repo, remote, opisu/homepage ani konfiguracji Pages. Docelowy Vite prefix: `/radar-ozarow/`; publikacja i smoke tego prefixu są osobnymi bramkami rodzica.

## Testy i zależności

```bash
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/data -v
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/investments -v
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/workflows -v
npm test
npm run build
.cache/venv/bin/python tests/workflows/check_dist.py
```

Testy workflow wykonują rzeczywisty Bash ze stubami boundary tools: GUNB usuwa cały staging directory, inwestycje otrzymują zachowany prior, awarie walidacji/inwestycji/frontend/build/dist odtwarzają wszystkie cztery pliki i evidence. Te boundary fixtures nie zastępują osobnych rzeczywistych parserów, produkcyjnego datasetu ani prawdziwego builda.

`requirements-data.txt` przypina requests/Shapely/PyMuPDF/PyYAML i zależności transitives do konkretnych wersji. PyMuPDF **1.28.2** jest wersją wykorzystywaną w lokalnych dowodach PDF, nie odgadniętym „latest”; metadata i dostępność wheels potwierdzono na pierwotnym PyPI endpoint `https://pypi.org/pypi/PyMuPDF/1.28.2/json`. Pozostałe wersje oparto na rzeczywistym sprawdzonym środowisku danych i potwierdzono na endpointach PyPI `.../<name>/<version>/json`. Lock wymaga Python 3.12+ przez numpy 2.5.3. HTML można parsować biblioteką standardową; nie dodano zbędnych parserów ani openpyxl (XLSX = ZIP/XML). Zmiana dependency wymaga ponownej czystej instalacji/`pip check`, parser tests i builda, nie tylko edycji numeru.
