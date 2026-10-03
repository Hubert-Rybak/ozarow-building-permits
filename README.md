# Budowy · Ożarów Mazowiecki

Polskojęzyczna mapa publicznych wpisów budowlanych GUNB RWDZ dla **całej gminy Ożarów Mazowiecki — miasta i obszaru wiejskiego**. React + TypeScript + Vite + Leaflet, statyczne JSON/GeoJSON, bez serwera aplikacyjnego i bez kluczy API w przeglądarce.

## Co przedstawiają dane

- Wpisy wniosków, odnotowanych decyzji i zgłoszeń, z opisem inwestycji, datami, adresem, odwołaniami do działek i źródłami.
- Rzeczywiste obrysy działek z publicznej usługi **ULDK GUGiK**, weryfikowane po pełnym identyfikatorze i obrębie — nie geokodowane punkty ani sztuczne prostokąty.
- Lista, mapa, wyszukiwanie, filtry i szczegóły oraz eksport wyników.
- Jawne statusy pokrycia geometrią: pełne, częściowe i nierozwiązane; zakres i czas pobrania są zapisane w metadanych.

**Odnotowana decyzja nie oznacza pozytywnego pozwolenia.** CSV nie podaje wyniku rozstrzygnięcia. Zgłoszenie nie jest pozwoleniem. Brak wpisów typu „sam wniosek” w eksporcie nie dowodzi braku nierozpatrzonych wniosków w gminie.

Domyślny zakres importu obejmuje daty **wpływu wniosków od 1 stycznia 2025 roku**, a nie wszystkie decyzje wydane od tej daty. Źródło może zawierać błędy TERC, nieaktualne numery działek i sprzeczne etykiety miejscowości. Takie odwołania nie są automatycznie „naprawiane”. Obrysy opisują stan ULDK z chwili pobrania, nie historyczne granice z daty wniosku.

Aplikacja domyślnie pokazuje **ostatnie 3 miesiące kalendarzowe** względem dzisiejszej daty w strefie Europe/Warsaw, według daty decyzji lub — przy jej braku — daty wniosku. Filtr „Okres → Wszystkie daty” udostępnia cały załadowany zbiór, także wpisy bez daty. Mapa, lista, liczniki i eksport CSV korzystają z tych samych filtrów; „Wyczyść filtry” przywraca ostatnie 3 miesiące.

Pełna metodologia, oficjalne źródła, weryfikacja TERYT, zakres i ograniczenia: **[docs/SOURCES.md](docs/SOURCES.md)**.

## Repozytorium i hosting

Repozytorium: **[Hubert-Rybak/ozarow-building-permits](https://github.com/Hubert-Rybak/ozarow-building-permits)**.

Publiczna aplikacja: **[hubert-rybak.github.io/ozarow-building-permits/](https://hubert-rybak.github.io/ozarow-building-permits/)**.

Repo i Pages upubliczniono 3 października 2026 po pozytywnych niezależnych przeglądach, 79 testach danych, 55 testach UI, 20 testach workflow oraz rzeczywistych CI/importach. Pierwszy wdrożony snapshot zawiera 447 wpisów i 842 obrysy; trzy pliki na Pages porównano bajtowo z repo, a przeglądarkowy smoke desktop/mobile potwierdził filtry, mapę i CSV bez błędów JS. Publikację kontroluje `PAGES_ENABLED=true`. Sam workflow nie dowodzi poprawnego wdrożenia — zawsze sprawdzaj run i rzeczywistą stronę.

## Uruchomienie lokalne

Wymagane: Node.js 22+, Python 3.12+ i dostęp do publicznych usług podczas importu online.

```bash
npm ci
npm run dev

# Frontend testy i produkcyjny build:
node node_modules/vitest/vitest.mjs run
npm run build
npm run preview
```

Konfiguracja produkcyjna uwzględnia prefiks projektu GitHub Pages `/ozarow-building-permits/`. Podczas sprawdzania preview używaj adresu wypisanego przez Vite i właściwego prefiksu, a nie zakładaj konkretnego portu.

## Import i aktualizacja danych

GUNB jest pobierany przez oficjalne **HTTP endpoints eksportów ZIP/CSV**, a geometrie przez **API ULDK**. Nie używamy niezweryfikowanego „API GUNB JSON”, CAPTCHA ani niepublicznych danych.

```bash
python3 -m venv .cache/venv
.cache/venv/bin/python -m pip install -r requirements-data.txt

# Rzeczywisty import całego wybranego zakresu i wszystkich poprawnych odwołań działkowych:
.cache/venv/bin/python scripts/import_data.py

# Jawny zakres dat wpływu:
.cache/venv/bin/python scripts/import_data.py --since 2025-01-01 --until 2026-10-03

# Codzienny tryb: świeże ZIP/CSV, ponowne użycie zweryfikowanych obrysów do 30 dni:
.cache/venv/bin/python scripts/import_data.py --refresh-sources --max-parcels 0

# Pomoc, opcje cache i odświeżania:
.cache/venv/bin/python scripts/import_data.py --help

# Dane/testy offline; nie wypisuj bajtkodu do drzewa repo:
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/data -v
```

Artefakty:

- `public/data/permits.json` — rekordy zgodne ze schematem v1;
- `public/data/parcels.geojson` — zweryfikowane Polygon/MultiPolygon WGS84 i powiązania z rekordami;
- `public/data/metadata.json` — daty pobrania/generacji, statystyki, źródła, sumy kontrolne i ostrzeżenia.

Źródła i geometrie są walidowane przed publikacją. Import nie nadpisuje poprzedniego zestawu pustymi lub częściowo zapisanymi plikami po błędzie. Wszystkie trzy artefakty należą do jednej generacji i należy je commitować razem.

## Codzienna automatyzacja

Opis workflow, harmonogramu UTC, ręcznego uruchomienia, walidacji danych i wdrożenia: **[docs/AUTOMATION.md](docs/AUTOMATION.md)**.

Aktualizacja odbywa się po stronie GitHub Actions, nie w przeglądarce użytkownika. Źródłowa usługa może publikować dane z opóźnieniem; data uruchomienia zadania nie jest datą najnowszego wpisu. Wyświetlane daty pochodzą z faktycznych danych i metadanych. Przy błędzie poprzedni poprawny zestaw pozostaje dostępny.

## Prywatność i bezpieczeństwo publikacji

- Pola inwestorów oraz imiona/nazwiska/uprawnienia projektantów nie są częścią kontraktu JSON aplikacji w `public/data/`.
- JSON aplikacji zawiera deterministyczne skróty rodzaju inwestycji ze stałego słownika zamiast swobodnych tytułów/opisów źródłowych. To ogranicza szczegółowość opisu i możliwość ujawniania danych osobowych. Tę regułę zastosowano również do historycznego snapshotu aplikacji.
- Na wyraźne polecenie właściciela pełne oficjalne archiwa GUNB oraz oryginalne wiersze gminy bez ograniczenia dat i redakcji zachowano w `data/full/`. Po udanej walidacji repo stało się publiczne, więc ten snapshot również jest dostępny w repo. Nie trafia do statycznego builda ani `public/`. Czasy pobrania i sumy SHA-256 podaje `data/full/manifest.json`; szczegóły eksportu opisuje `data/full/README.md`.
- Cache, środowiska Python, logi, cookies, sekrety i lokalne pliki konfiguracyjne pozostają poza repo. Nie wysyłaj `.cache/` ani `.env` do repo lub artefaktów Actions. Codzienny workflow aplikacji aktualizuje wyłącznie jej JSON/GeoJSON i zweryfikowane dowody ULDK, nie surowy snapshot `data/full/`.
- Strona statyczna nie wymaga sekretów do pobrania opublikowanych danych. Workflow używa ograniczonych uprawnień GitHub i publikuje tylko zweryfikowaną produkcyjną kompilację.

Plan i kryteria ukończenia: [docs/PLAN.md](docs/PLAN.md).
