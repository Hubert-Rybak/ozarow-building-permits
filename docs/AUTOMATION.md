# Automatyzacja danych, CI i GitHub Pages

## Workflowy i ręczne uruchamianie

| Plik | Uruchomienie | Zakres |
|---|---|---|
| `.github/workflows/ci-pages.yml` | `push` na `main`, PR do `main`, `workflow_dispatch` | Testy aplikacji, importer/dane, kontrakty workflowów, build; opcjonalne Pages |
| `.github/workflows/daily-data.yml` | **codziennie 03:23 UTC** (`23 3 * * *`), `workflow_dispatch` | Świeże oficjalne CSV GUNB, inkrementalna geometria ULDK, walidacja, jeden commit generacji, opcjonalne Pages w tym samym uruchomieniu |

Cron oznacza 05:23 podczas polskiego czasu letniego i 04:23 podczas czasu zimowego. GitHub może opóźnić wykonanie harmonogramu; harmonogram działa na domyślnej gałęzi i nie jest gwarancją startu o konkretnej sekundzie.[3]

Po umieszczeniu workflowów na `main` można je wywołać w Actions → odpowiedni workflow → Run workflow, albo:

```sh
gh workflow run ci-pages.yml --ref main
gh workflow run daily-data.yml --ref main
```

Ręczne uruchomienie `daily-data.yml` na gałęzi innej niż `main` pomija job odświeżania. `ci-pages.yml` sprawdza inne gałęzie, ale nigdy ich nie publikuje.

## Najpierw prywatne CI; Pages dopiero po świadomym włączeniu

Nie jest potrzebny PAT ani nowy sekret. Workflow używa wyłącznie krótkotrwałego `GITHUB_TOKEN`. Uprawnienia domyślne to `contents: read`; tylko job dziennego importu dostaje `contents: write`. Job publikacji ma `contents: read`, `pages: write` i `id-token: write`; to ostatnie jest wymagane przez oficjalny mechanizm wdrożenia Pages.[1]

Konfiguracja, upload i wdrożenie Pages wymagają równocześnie:

- `github.ref == 'refs/heads/main'`;
- zmiennej repozytorium **`PAGES_ENABLED` o wartości tekstowej `true`**;
- sukcesu wszystkich wcześniejszych testów i buildu.

Brak zmiennej albo inna wartość pomija wszystkie kroki Pages, ale **nie pomija CI ani importu danych**. Prywatne repozytorium bez dostępnego Pages nie powoduje błędu publikacji, bo publikacja nie zostaje uruchomiona. `configure-pages` ma jawnie `enablement: false`: żaden workflow nie zmienia ustawień repozytorium.

Kolejność wdrożenia przez administratora, poza tymi workflowami:

1. Wgrać kod i workflowy; przeprowadzić prywatne CI.
2. Dopiero po sprawdzeniu prywatnego CI i zgody właściciela zmienić widoczność repozytorium.
3. Skonfigurować Pages ze źródłem **GitHub Actions** (`build_type: workflow` w API Pages).[5]
4. Ustawić `PAGES_ENABLED=true` i ręcznie uruchomić `ci-pages.yml` na `main`.

Ta dokumentacja opisuje wymagania, nie potwierdza zmiany ustawień ani zdalnego deploymentu. Lokalne dodanie plików nie rejestruje jeszcze workflowów w GitHub.

## Dzienne dane: kontrakt CLI i granica prywatności

Workflow zamraża `until` przez `date -u +%F` raz na początku importu. Kod, trzy wcześniejsze pliki danych i publiczny cache ULDK pochodzą z jednego niezmiennego `github.sha`; checkout nie pozostawia poświadczeń w konfiguracji Git.

Wywołanie importera:

```sh
python scripts/import_data.py \
  --since 2025-01-01 --until "$until" \
  --max-parcels 0 --workers 4 --refresh-sources \
  --cache "$RUNNER_TEMP/gunb-private-cache" \
  --uldk-public-cache "$RUNNER_TEMP/uldk-cache-candidate.json" \
  --output "$RUNNER_TEMP/data-candidate"
```

- `--refresh-sources` wymusza nowe ZIP/CSV z oficjalnych źródeł GUNB, bez wymuszania ponownego pobrania nadal ważnej geometrii ULDK. Nie używa `--offline`, sztucznego limitu działek ani `--refresh` odświeżającego całą geometrię.
- `--max-parcels 0` oznacza wszystkie poprawne odwołania, nie zero wyników; `--workers 4` ogranicza równoległość ULDK.
- `--uldk-public-cache` jest **zweryfikowanym interfejsem importera**, a nie Actions cache. Na początku workflow kopiuje do niego, o ile istnieje, `scripts/uldk-cache.json`. Importer ponownie sprawdza exact ID, SRID/geometrię, hash odpowiedzi i TTL ≤30 dni. Nowe lub wygasłe odpowiedzi pobiera z ULDK. Błędów usług nie zamienia w fikcyjne obrysy.
- `scripts/uldk-cache.json` zawiera wyłącznie allowlistowane, pozytywne odpowiedzi publicznego ULDK oraz daty/hash; **nie zawiera CSV, ZIP ani pól inwestora/projektanta**. Utrwalenie tego pliku razem z danymi pozwala korzystać z geometrii także na nowym, efemerycznym runnerze.
- Surowe CSV/ZIP i robocze odpowiedzi zostają wyłącznie w `$RUNNER_TEMP/gunb-private-cache`. Nie są wrzucane do Git ani uploadowane jako artifacts. Wyłączono także automatyczny cache `setup-node`; nie ma `actions/cache` ani cache pip.
- Hashy pobranych źródeł, dat pobrania, rzeczywistego zakresu, liczników i braków należy szukać w `public/data/metadata.json`. Same daty i hash nie odtwarzają CSV: oryginalne archiwa pozostają prywatne.

## Transakcja, bramki i rollback

1. Kopia wcześniejszego `public/data/` jest wejściem katalogu stagingowego. Dzięki temu importer zachowuje kontrolę zawężenia zakresu i podejrzanej utraty danych względem poprzedniej generacji, mimo innego `--output`.
2. Importer buduje komplet w stagingu i zwraca błąd przy nieprawidłowym źródle/schemacie. Nie rusza wcześniejszego `public/data/` ani tracked cache ULDK.
3. Po sukcesie importu workflow zachowuje wcześniejszy katalog jako `$RUNNER_TEMP/original-public-data` i wcześniejszy publiczny cache ULDK jako `$RUNNER_TEMP/original-uldk-cache.json`, po czym instaluje oba kandydaty na czas testów. To pozwala sprawdzić także dowody nowo dodanych lub odświeżonych geometrii. Bash `trap ERR` przywraca **wszystkie trzy** wcześniejsze pliki oraz wcześniejszy publiczny cache, jeżeli testy danych, testy aplikacji, build lub kontrola publikowanego katalogu zawiodą.
4. Dopiero po wszystkich bramkach stagingowane są konkretne ścieżki:
   - `public/data/permits.json`;
   - `public/data/parcels.geojson`;
   - `public/data/metadata.json`;
   - `scripts/uldk-cache.json` jako dodatkowy publiczny dowód/cache geometrii.
5. Jeden commit obejmuje spójną generację i publiczny cache. Nie ma `git add .`, `git add -A`, force-push ani commita przy nieudanym teście. Push jest wyłącznie na `HEAD:refs/heads/main`, a jego SHA jest odczytywane ponownie z GitHub API przed zgłoszeniem sukcesu.

Testy danych sprawdzają też kompletność gminy, geometrię, prywatną allowlistę pól i powiązania rekord↔działka. Test porównania z prywatnym `.cache/responses` jest pomijany, jeżeli tego prywatnego cache nie ma na runnerze; pozostałe testy nadal działają.

## Wdrożenie i wyścigi

Oba workflowy mają tę samą blokadę całego workflowu `main-data-and-pages`, `cancel-in-progress: false` i `queue: max`. Nie ma kolejnej blokady na jobach ani zagnieżdżonych wywołań workflowu. Oficjalny `queue: max` pozwala kolejkować do 100 oczekujących uruchomień zamiast zastępować pojedyncze oczekujące uruchomienie; kolejność zależy od wejścia do kolejki, nie wyłącznie od czasu zdarzenia.[4]

Blokada nie blokuje ręcznych pushów spoza Actions. Dlatego dzienny push jest tylko fast-forward; konflikt oznacza niepowodzenie, nie nadpisanie cudzych zmian. Przed `deploy-pages` oba workflowy ponownie porównują aktualne `main` z SHA sprawdzonej generacji; nieaktualny snapshot jest pomijany. Jest to kontrola tuż przed deploymentem, nie atomowa blokada zewnętrznych pushów.

**Dzienny workflow wdraża w tym samym runie, w którym zrobił commit danych.** Nie oczekuje kolejnego workflowu `push`: push wykonany przez `GITHUB_TOKEN` nie uruchamia standardowego nowego workflowu push.[2] W API Pages identyfikator runu/zdarzenia pozostaje identyfikatorem uruchomienia sprzed automatycznego commita; zawartość artifactu jest jednak dokładnie generacją, którą ten run przetestował, zbudował i utrwalił.

Jedyny artifact to oficjalny Pages artifact utworzony z **`dist/`**, z retencją 1 dnia. `tests/workflows/check_dist.py` wymaga dokładnie `index.html`, `assets/` i trzech plików `data/`; sprawdza byte-for-byte kopię zwalidowanych plików źródłowych. Odrzuca raw ZIP/CSV, dodatkowe JSON-y danych, ukryte ścieżki, symlinki i hardlinki. `scripts/uldk-cache.json` nie wchodzi do Pages artifactu.

## Weryfikacja lokalna

```sh
python -m pip install -r requirements-data.txt PyYAML==6.0.3
python -m unittest discover -s tests/workflows -v
python -m unittest discover -s tests/data -v
npm ci
npm test
npm run build
python tests/workflows/check_dist.py
```

Kontrakty workflowów parsują rzeczywiste YAML i sprawdzają zdarzenia, cron, main/Pages guardy, kolejność commitów, wspólną concurrency, uprawnienia i SHAs. Testy transakcji uruchamiają **rzeczywisty blok Bash z workflowu** w izolowanych fixtures, z kontrolowanym błędem każdej z czterech bramek; nie są zastępstwem rzeczywistych testów danych/aplikacji.

Lokalną próbę CI wykonano 3 października 2026 na odizolowanej kopii bez `.cache` i `.git`, używając Node **22.23.3** oraz Python **3.12.15**: `npm ci`, testy workflowów, 63 testy danych (1 prawidłowy skip prywatnego cache), 39 testów UI, produkcyjny build i weryfikacja `dist/` zakończyły się sukcesem. Po końcowej korekcie transakcji ponownie uruchomiono 20 testów workflowów, w tym rollback danych i publicznego dowodu ULDK.

`actionlint` 1.7.12 poprawnie sprawdza pozostałą składnię, lecz nie obsługuje jeszcze udokumentowanego klucza `concurrency.queue`. Pełne pliki są parsowane i testowane przez PyYAML; dodatkowe sprawdzenie actionlint wykonano na kopiach usuwających tylko wiersz `queue: max`. Nie jest to potwierdzenie zdalnego uruchomienia Actions. Przy aktualizacji lintera należy powrócić do lintowania plików bez normalizacji.

## Oficjalne Actions przypięte do zweryfikowanych commitów

Wersje i SHAs sprawdzono w oficjalnym GitHub Releases API oraz API `git/ref/tags`; `action.yml` odczytano z tych samych commitów. Stan weryfikacji: **3 października 2026**.

| Action | Wersja | Commit SHA |
|---|---|---|
| `actions/checkout`[6] | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-node`[7] | `v7.0.0` | `820762786026740c76f36085b0efc47a31fe5020` |
| `actions/setup-python`[8] | `v7.0.0` | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `actions/configure-pages`[9] | `v6.0.0` | `45bfe0192ca1faeb007ade9deae92b16b8254a0d` |
| `actions/upload-pages-artifact`[10] | `v5.0.0` | `fc324d3547104276b827a68afc52ff2a11cc49c9` |
| `actions/deploy-pages`[11] | `v5.0.1` | `368f82528645a54fb793d4d04e342629a3f51346` |

Node aplikacji: 22; Python importera/testów: 3.12; runner: `ubuntu-24.04`. Prywatne materiały wejściowe nie są zależnością CI sprawdzającego już opublikowany snapshot.

## Sources

[1] https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
[2] https://docs.github.com/en/actions/concepts/security/github_token
[3] https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
[4] https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
[5] https://docs.github.com/en/rest/pages/pages
[6] https://github.com/actions/checkout/releases/tag/v7.0.1
[7] https://github.com/actions/setup-node/releases/tag/v7.0.0
[8] https://github.com/actions/setup-python/releases/tag/v7.0.0
[9] https://github.com/actions/configure-pages/releases/tag/v6.0.0
[10] https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0
[11] https://github.com/actions/deploy-pages/releases/tag/v5.0.1
