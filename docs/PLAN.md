# Ożarów Building Permits — plan i kontrakt integracji

## Cel i zgoda na publikację

Polskojęzyczna aplikacja do przeglądania publicznych wpisów RWDZ GUNB dla całej gminy Ożarów Mazowiecki (miasto i obszar wiejski), interaktywna mapa i rzeczywiste obrysy działek. Nie utożsamiać wniosku/odnotowanej decyzji ze zgodą na budowę. Brak geometrii oraz niejednoznaczne dane muszą być jawne.

3 października 2026 użytkownik zlecił dokończenie wieloagentowe, push do repo, codzienne pobieranie nowych danych i GitHub Pages. Zgoda na publiczne repo była warunkowa: **po działających testach i weryfikacji aplikacji**. Następnie wyraźnie polecił przesłać wszystkie dane bez dalszego zajmowania się prywatnością. Pełne oficjalne ZIP-y i oryginalne wiersze gminy zachowano w osobnym `data/full/`; nie są częścią builda aplikacji. Sekrety, poświadczenia i cookies nadal pozostają poza repo. Lokalny smoke i CI wykonano najpierw w prywatnym repo, a następnie włączono publiczną widoczność i Pages po pozytywnej weryfikacji.

## Równoległe zadania i własność plików

A. Agent UI: `src/`, `index.html`, `package.json`, `package-lock.json`, `tsconfig*`, `vite.config.*`, `tests/ui/`, `.gitignore`. Dokończenie UI i responsywności, rzeczywiste powiązania lista–mapa–szczegóły, filtracja, eksport, ostrzeżenia źródłowe, poprawny BASE_URL GitHub Pages, testy TDD i build. Nie edytuje importerów, danych ani workflows.

B. Agent automatyzacji: `.github/workflows/`, `tests/workflows/`, `docs/AUTOMATION.md`. CI i codzienny harmonogram UTC + workflow_dispatch; aktualizacja wszystkich trzech artefaktów razem po walidacji, budowa i Pages deployment. Publikacja tylko na main, po fladze `PAGES_ENABLED`. Nie uploaduje/cache'uje surowych CSV na GitHub. Nie polega na uruchomieniu drugiego workflow przez commit z GITHUB_TOKEN. Nie edytuje UI ani importerów.

C. Agent danych: `scripts/`, `tests/data/`, `public/data/`, `docs/SOURCES.md`, `requirements-data.txt`. Świeże rzeczywiste oficjalne CSV GUNB i API ULDK, CLI `--refresh-sources` do codziennego odświeżania eksportów przy rozsądnym ponownym użyciu zweryfikowanych geometrii. Walidacja, prywatność, brak pozornego aktualizowania starego zestawu i ochrona poprzednich artefaktów po błędzie. Nie edytuje UI/workflows.

Kontroler: `README.md`, ten plan, repo/commity/push/settings, integracja, przeglądy, smoke i finalna weryfikacja. Agenci implementacyjni nie wykonują commitów ani zmian ustawień GitHub.

## Bramki ukończenia

1. Pierwszy zweryfikowany snapshot danych i źródeł wypchnięty do prywatnego repo; dokładny zdalny SHA i blob SHA sprawdzone.
2. Implementacje agentów gotowe z wykonanymi testami. Przegląd zgodności, następnie niezależny przegląd jakości/bezpieczeństwa. Istotne uwagi naprawione i ponownie sprawdzone.
3. Testy Python/UI/workflow, build, lokalny browser smoke desktop/mobile, interakcje filtrów/listy/mapy i brak błędów JS. Scan całego publikowanego drzewa/history: sekrety, prywatne identyfikatory, surowe cache.
4. Pełny commit/push; lokalny/tracking/zdalny SHA i kluczowe artefakty identyczne. Rzeczywisty CI i ręcznie wywołany import na GitHub zakończone sukcesem (nie tylko złożony YAML).
5. Po sukcesie: publiczne repo, Pages skonfigurowane i opublikowane. HTTP 200, zgodność wdrożonych JSON z artefaktami, browser smoke na dokładnym URL z prefiksem repo. Flaga publikacji włączona, dzienny harmonogram potwierdzony odczytem zdalnego workflow.
6. Końcowy raport: repo/site URL, commit/run URL, faktyczne daty danych, liczby rekordów/poligonów, ograniczenia. Nie deklarować kompletności pending applications ani pozytywnych pozwoleń bez źródłowego wyniku decyzji.

## Kontrakt JSON v1

`public/data/permits.json`:

```json
{"schemaVersion":1,"generatedAt":"ISO UTC","source":{"name":"GUNB RWDZ","url":"official URL","downloadedAt":"ISO UTC","coverage":"jawny opis zakresu dat/rodzajów"},"records":[]}
```

Record: `{id:string, kind:"application"|"decision"|"notification", title:string, description:string, applicationDate:string|null (YYYY-MM-DD), decisionDate:string|null, decisionNumber:string|null, status:string, locality:string, street:string, municipality:string, cadastralRegion:string, parcelNumbers:string[], parcelIds:string[], category:string, sourceUrl:string, geometryStatus:"matched"|"partial"|"unresolved", geometryNote:string}`. Brak nazwisk osób prywatnych w UI i imporcie; nazwy podmiotów nie są wymagane.

`public/data/parcels.geojson`: FeatureCollection z top-level `generatedAt` identycznym z permits i metadata, geometrie Polygon/MultiPolygon WGS84 lon/lat, properties `{id:string,parcelNumber:string,region:string,permitIds:string[],sourceUrl:string}`. Tylko potwierdzone identyfikatory działek; bez fikcyjnych geometrii. Dodatkowe pola jawnej metadanej pobrania dopuszczalne.

`public/data/metadata.json`: `{generatedAt:string,recordCount:number,parcelCount:number,matchedRecordCount:number,unresolvedRecordCount:number,coverage:string,warnings:string[],sources:[{name,url}]}`. Dodatkowe pola dozwolone. UI oblicza statystyki z rekordów, nie ufa bezwarunkowo licznikom metadanych.

## Weryfikacja wdrożenia — 3 października 2026

- Pełny kod: `c628002261cffe72dbe3dd922ef570726aafe6e4`; dane po rzeczywistym odświeżeniu Actions: `d675c0e1399364e6ce597c44ba82bff500dc4b90`.
- CI `37103489694`, ręczny świeży import `37103525834` i Pages build/deploy `37103791008` zakończone sukcesem; w ostatnim runie job deploy rzeczywiście wykonał się, nie został pominięty.
- Repo publiczne, Pages `build_type=workflow`, `PAGES_ENABLED=true`; strona `https://hubert-rybak.github.io/ozarow-building-permits/` zwróciła HTTP 200.
- Snapshot generacji `2026-10-03T06:37:57.293208Z`: 447 wpisów i 842 obrysy; trzy wdrożone pliki zgodne bajtowo z repo. Zachowano 48 wpisów bez geometrii i 29 częściowo dopasowanych.
- Browser desktop/mobile: 447 wierszy/842 obrysy, Duchnice 38/71, po filtrze zgłoszeń 12; reset i CSV działają; brak błędów JS, błędów HTTP aplikacji i poziomego overflow.
- Harmonogram codzienny `23 3 * * *` UTC oraz ręczny dispatch są obecne w zdalnym workflow. Nie twierdzimy, że przyszły run harmonogramu już się wykonał.
