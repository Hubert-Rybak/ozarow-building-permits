# Radar Ożarów

Polskojęzyczny radar inwestycji gminnych, publicznych i prywatnych oraz mapa publicznych wpisów budowlanych GUNB RWDZ dla **całej gminy Ożarów Mazowiecki — miasta i obszaru wiejskiego**. React + TypeScript + Vite + Leaflet, statyczne JSON/GeoJSON, bez serwera aplikacyjnego i bez kluczy API w przeglądarce.

## Co przedstawiają dane

- Wpisy wniosków, odnotowanych decyzji i zgłoszeń, z opisem inwestycji, datami, adresem, odwołaniami do działek i źródłami.
- Rzeczywiste obrysy działek z publicznej usługi **ULDK GUGiK**, weryfikowane po pełnym identyfikatorze i obrębie — nie geokodowane punkty ani sztuczne prostokąty.
- Lista, mapa, wyszukiwanie, filtry i szczegóły oraz eksport wyników.
- Jawne statusy pokrycia geometrią: pełne, częściowe i nierozwiązane; zakres i czas pobrania są zapisane w metadanych.

**Odnotowana decyzja nie oznacza pozytywnego pozwolenia.** CSV nie podaje wyniku rozstrzygnięcia. Zgłoszenie nie jest pozwoleniem. Brak wpisów typu „sam wniosek” w eksporcie nie dowodzi braku nierozpatrzonych wniosków w gminie.

Domyślny zakres importu obejmuje daty **wpływu wniosków od 1 stycznia 2025 roku**, a nie wszystkie decyzje wydane od tej daty. Źródło może zawierać błędy TERC, nieaktualne numery działek i sprzeczne etykiety miejscowości. Takie odwołania nie są automatycznie „naprawiane”. Obrysy opisują stan ULDK z chwili pobrania, nie historyczne granice z daty wniosku.

Aplikacja domyślnie pokazuje **ostatnie 3 miesiące kalendarzowe** względem dzisiejszej daty w strefie Europe/Warsaw, według daty decyzji lub — przy jej braku — daty wniosku. Filtr „Okres → Wszystkie daty” udostępnia cały załadowany zbiór, także wpisy bez daty. Mapa, lista, liczniki i eksport CSV korzystają z tych samych filtrów; „Wyczyść filtry” przywraca ostatnie 3 miesiące.

Pełna metodologia, oficjalne źródła, weryfikacja TERYT, zakres i ograniczenia: **[docs/SOURCES.md](docs/SOURCES.md)**.

## Interfejs: mapa z panelem (runda 2, kierunek B)

Jedna mapa na cały ekran pokazuje obie warstwy: **budowy** (kwadraty, kolor = rodzaj wpisu: decyzja / zgłoszenie — nie wynik) i **inwestycje** (koła, kolor = etap: zapowiedziane / w realizacji / ukończone / inne). Przy oddaleniu bliskie obiekty łączą się w klastry z liczbą i udziałem kolorów; od przybliżenia ~17 widać obrysy działek. Legenda liczy wyłącznie obiekty obecne na mapie. Markery nie są osobnymi przystankami Tab — dostępną alternatywą jest lista.

Na desktopie wyniki i karta wpisu są w pływającym panelu po lewej (zakładki Budowy / Inwestycje), a mapa kadruje wybór z uwzględnieniem panelu. Na telefonie panel jest arkuszem od dołu (podgląd / połowa / pełny; uchwyt można stuknąć lub przeciągnąć); wybór z listy lub mapy ustawia arkusz na połowę i centruje działkę **nad** arkuszem. Fokus po zamknięciu (przycisk „Lista” albo Escape) wraca do wiersza listy lub do przycisku mapy.

Karta wpisu budowlanego: zdanie o statusie (decyzja odnotowana bez wyniku, brak sprzeciwu, wniosek ≠ pozwolenie), przebieg wniosek → decyzja, „Sprawdź u źródła” (wyszukiwarka GUNB + kopiowanie numeru, działka w Geoportalu, opisany plik ZIP GUNB), obiekty w pobliżu (do 300 m / inwestycje do 1 km) i zwinięte dane techniczne (TERYT, odpowiedź ULDK). Karta inwestycji: etap z oryginalnym zdaniem statusu, ważne daty, kwoty bez sumowania, lokalizacja lub jej brak, udokumentowane powiązania i rekordy o podobnej nazwie (nie łączone automatycznie).

Filtry to przyciski z liczbami: okres i rodzaj wpisu dla budów; etap (ukończone domyślnie ukryte), 11 grup zamiast 28 kategorii źródłowych i miejscowość (także „bez miejscowości”) dla inwestycji; reszta w „Więcej filtrów”. Wyszukiwanie toleruje odmianę („boisko” znajduje „boiska”). „Nowe od ostatniej wizyty” zapamiętuje tylko przeglądarka (localStorage). Każdy wpis ma link (`#wpis=…`, `#inwestycja=…`). Ograniczenia i pokrycie źródeł są w oknie „O danych”. Tekst ma bazowo 15 px, pola na telefonie 16 px, cele dotyku ≥ 40–44 px; czcionka IBM Plex Sans jest serwowana lokalnie z buildu.

```bash
npm test -- --maxWorkers=1
npm run build
# Ograniczony lokalny preview (zakończ po sprawdzeniu):
npm run preview -- --host 127.0.0.1 --port 4182 --strictPort
```

## Atlas inwestycji

Zakładka **Inwestycje** udostępnia filtry etapu, grupy kategorii, miejscowości, źródła, typu inwestora, roku oraz dostępności geometrii, sortowanie, wyszukiwanie i CSV z tego samego zbioru wyników. Domyślnie pokazuje wszystkie lata i ukrywa rekordy ukończone (jeden przycisk je przywraca). Inspektor rozdziela czas pobrania, datę edycji źródła i daty zdarzeń; pokazuje typ/zakres kosztu, źródła, historię i ostrzeżenia bez zgadywania braków.

Zweryfikowany snapshot z **3 października 2026, 13:52:56 UTC** zawiera **792 rekordy źródłowe z 10 źródeł**, w tym **469 z geometrią i 755 obiektów GeoJSON**. MultiPoint pozostaje jednym obiektem z wieloma punktami: łącznie renderowane są 762 elementy SVG; BO obejmuje 16 obiektów / 23 punkty. To nie jest liczba unikalnych budów ani deklaracja pełnego pokrycia gminy. Aktualne liczniki i statusy źródeł zawsze wynikają z załadowanego artefaktu, nie z tych historycznych liczb.

Finalny snapshot przeszedł niezależną bramkę DATA (rzeczywiste źródła i dowody ULDK/PDF/XLSX, prawidłowe daty pobrania/edycji, awarie i retencja), a UI SPEC obejmuje niezmienione regresje GUNB/mobile, wszystkie dzieci rzeczywistych MultiPoint, kliknięcie/dotyk/Enter/Space, pojedynczy callback, mapę/fokus/kamerę, filtry/CSV i krótkie viewporty przy breakpointach. Zestaw testów URL wykorzystuje wspólny korpus w Pythonie i TypeScript oraz rzeczywisty zapis fail-closed. Lokalne raporty, surowe dowody, screenshoty i logi pozostają poza publicznym buildem. Publikacja wymaga oddzielnej pozytywnej bramki QUALITY/security, CI dokładnego SHA oraz sprawdzenia czterech plików i interfejsu na Pages; sam lokalny wynik nie potwierdza wdrożenia.

## Repozytorium i hosting

Repozytorium wydania Radar: **[Hubert-Rybak/radar-ozarow](https://github.com/Hubert-Rybak/radar-ozarow)**.

Adres aplikacji wydania: **[hubert-rybak.github.io/radar-ozarow/](https://hubert-rybak.github.io/radar-ozarow/)**. Weryfikując konkretne wdrożenie, sprawdź poprawny run Pages, jego SHA oraz rzeczywistą stronę i payloady; lokalny prefix i nazwa pakietu nie są dowodem publikacji.

Historyczny Atlas/GUNB pod nazwą `ozarow-building-permits` upubliczniono 3 października 2026 po pozytywnych niezależnych przeglądach, 79 testach danych, 55 testach UI, 20 testach workflow oraz rzeczywistych CI/importach. Pierwszy wdrożony snapshot zawiera 447 wpisów i 842 obrysy; trzy pliki na Pages porównano bajtowo z repo, a przeglądarkowy smoke desktop/mobile potwierdził filtry, mapę i CSV bez błędów JS. Publikację kontroluje `PAGES_ENABLED=true`. Sam workflow nie dowodzi poprawnego wdrożenia — zawsze sprawdzaj run i rzeczywistą stronę.

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

Konfiguracja produkcyjna uwzględnia prefiks projektu GitHub Pages `/radar-ozarow/`. Podczas sprawdzania preview używaj adresu wypisanego przez Vite i właściwego prefiksu, a nie zakładaj konkretnego portu.

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
- `public/data/metadata.json` — daty pobrania/generacji, statystyki, źródła, sumy kontrolne i ostrzeżenia;
- `public/data/investments.json` — oddzielny, samowystarczalny snapshot inwestycji: rekordy źródłowe, metadane pokrycia, koszty z typem/zakresem, zdarzenia i geometrie inline. Nie wymaga wspólnej daty generacji z GUNB.

Źródła i geometrie są walidowane przed publikacją. Import nie nadpisuje poprzedniego zestawu pustymi lub częściowo zapisanymi plikami po błędzie. Trzy artefakty GUNB należą do jednej generacji i należy je commitować razem; inwestycje mają osobną generację. Wspólny workflow commituje wszystkie cztery pliki razem.

## Inwestycje: agregacja i walidacja

Każdy adapter `scripts/investment_sources/{municipal,public,private}.py` dostarcza rzeczywiste dane i jawne metadane źródła. Nie scala się projektów po podobnym tytule; liczniki pokazują rekordy źródłowe, a nie liczbę unikalnych budów. Budżet, grant, propozycja BO, wiadomość i postępowanie nie dowodzą rozpoczęcia budowy. Koszty różnych typów i projekty wielogminne nie są automatycznie sumowane ani przypisywane w całości gminie. Brak geometrii pozostaje brakiem; nie tworzymy pinezek w centrum miasta.

```bash
# Cache inwestycji MUSI być poza repozytorium oraz public/dist:
.cache/venv/bin/python scripts/import_investments.py --cache "$TMPDIR/radar-ozarow-investments"
.cache/venv/bin/python scripts/import_investments.py --validate public/data/investments.json
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/investments -v
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/workflows -v
```

Brak adaptera lub pierwszego rzeczywistego artefaktu jest błędem integracji, nigdy pomijanym testem. Po awarii źródło może zachować wcześniejsze zweryfikowane dane wyłącznie jako `retained` z ostrzeżeniem i oryginalnymi datami; bez wcześniejszych danych ma status `unavailable`. Dokumenty kuratorowane są jawnie `static`, nie udają codziennego pobrania. Procedura, kontrakt artefaktów i ograniczenia transakcji: **[docs/investments/PIPELINE.md](docs/investments/PIPELINE.md)**.

## Codzienna automatyzacja

Workflow `daily-data.yml` odświeża GUNB/ULDK i inwestycje codziennie o **03:23 UTC** (`23 3 * * *`) oraz na `workflow_dispatch`. Zachowuje poprzednie inwestycje przed całokatalogową zamianą GUNB, waliduje wszystkie cztery pliki, uruchamia testy/build i przy błędzie przywraca całe `public/data/` oraz dowody ULDK. Commit obejmuje wyłącznie cztery artefakty i `scripts/uldk-cache.json`; build sprawdza ich zgodność bajtową. Deploy po pushu `GITHUB_TOKEN` jest w tym samym runie, tylko dla nieprzestarzałego main i `PAGES_ENABLED=true`.

Aktualny kontrakt: **[docs/investments/PIPELINE.md](docs/investments/PIPELINE.md)**. Historyczny opis bazowego GUNB/ULDK: **[docs/AUTOMATION.md](docs/AUTOMATION.md)**.

Aktualizacja odbywa się po stronie GitHub Actions, nie w przeglądarce użytkownika. Źródłowa usługa może publikować dane z opóźnieniem; data uruchomienia zadania nie jest datą najnowszego wpisu. Wyświetlane daty pochodzą z faktycznych danych i metadanych. Przy błędzie poprzedni poprawny zestaw pozostaje dostępny.

## Prywatność i bezpieczeństwo publikacji

- W warstwie **GUNB** pola inwestorów oraz imiona/nazwiska/uprawnienia projektantów nie są częścią kontraktu JSON. Warstwa inwestycji zawiera nazwy instytucji/przedsiębiorstw ze sprawdzonych źródeł, nie kontakty osobiste ani techniczne Creator/Editor.
- JSON warstwy GUNB zawiera deterministyczne skróty rodzaju inwestycji ze stałego słownika zamiast swobodnych tytułów/opisów źródłowych. To ogranicza szczegółowość opisu i możliwość ujawniania danych osobowych. Tę regułę zastosowano również do historycznego snapshotu aplikacji.
- Na wyraźne polecenie właściciela pełne oficjalne archiwa GUNB oraz oryginalne wiersze gminy bez ograniczenia dat i redakcji zachowano w `data/full/`. Po udanej walidacji repo stało się publiczne, więc ten snapshot również jest dostępny w repo. Nie trafia do statycznego builda ani `public/`. Czasy pobrania i sumy SHA-256 podaje `data/full/manifest.json`; szczegóły eksportu opisuje `data/full/README.md`.
- Cache, środowiska Python, logi, cookies, sekrety i lokalne pliki konfiguracyjne pozostają poza repo. Nie wysyłaj `.cache/` ani `.env` do repo lub artefaktów Actions. Codzienny workflow aplikacji aktualizuje wyłącznie jej JSON/GeoJSON i zweryfikowane dowody ULDK, nie surowy snapshot `data/full/`.
- Strona statyczna nie wymaga sekretów do pobrania opublikowanych danych. Workflow używa ograniczonych uprawnień GitHub i publikuje tylko zweryfikowaną produkcyjną kompilację.

Plan i kryteria ukończenia: [docs/PLAN.md](docs/PLAN.md).
