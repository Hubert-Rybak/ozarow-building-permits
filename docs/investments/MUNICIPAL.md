# Gminna mapa inwestycji — adapter `municipal-map`

## Wynik realnego wykonania

Adapter `scripts/investment_sources/municipal.py` udostępnia dokładnie:

```python
collect(cache: pathlib.Path, prior: dict | None = None) -> dict
# {'records': [...], 'sources': [...], 'warnings': [...]}
```

Ostatnia kontrola wykonana **3 października 2026, `2026-10-03T12:18:00.462Z`**:

| Kontrola | Wynik |
|---|---:|
| Surowe rekordy ArcGIS; count i IDs przed/po | 439 |
| Wykluczone szablony `Kolejnosc=-1` | 1 |
| Zachowane rekordy źródłowe | 438 |
| Oryginalne geometrie `Point`, WGS84 | 438 |
| Rekordy bez geometrii | 0 |
| Punkty poza oficjalną granicą | 1: OBJECTID 400 |
| Brak liczbowego kosztu, zachowany jako `null` | 91 |
| Status „Ukończone” / „Realizowane” / „Zaplanowane” | 358 / 63 / 17 |
| Strony inwestycji; rozmiar strony | 3; 200 |
| Czas wykonania z pełnym sprawdzonym prior | 5,01 s |

**Liczby są wynikiem tej kontroli, nie stałymi ani oczekiwaniem przyszłych pobrań.** Pełne pokrycie oznacza pełną warstwę gminnej mapy, nie wszystkie przedsięwzięcia publiczne i prywatne w gminie. Licznik oznacza rekordy źródłowe, nie unikalne budowy.

- Niezależny wkład: `.cache/municipal-contribution.json`.
- Dowód dokładnie tego pobrania: `.cache/municipal-evidence/municipal-20261003T121756-f183cce2/evidence.json` oraz ponumerowane odpowiedzi w tym katalogu.
- `.cache/municipal-run-summary.json` podaje czas, datę oraz dokładne ścieżki artefaktu i dowodu.
- Poprzednia niezależna realna kontrola bez prior również zwróciła 439/438; dowód: `.cache/municipal-evidence/municipal-20261003T120417-7ec671d0/evidence.json`.

Cache i dowody **nie są zasobami do publikacji**. Nie przenosić ich do `public/`, `dist/` ani archiwów publicznego repo. Centralny importer odpowiada za InvestmentDataset, globalne liczniki i transakcyjny zapis; adapter nie edytuje App, workflow ani wspólnego importera.

## Odkryte źródło i wykluczenie szablonu

Normalne publiczne pobranie, bez logowania, CAPTCHA, przeglądarkowych obejść ani zapisu do zewnętrznych usług:

```text
Portal: https://www.ozarow.gminneinwestycje.pl/
Zaobserwowany aktualny moduł:
https://www.ozarow.gminneinwestycje.pl/assets/dataService-F123ODcc.js
Inwestycje:
https://services-eu1.arcgis.com/n7DhHnz2koymALo1/ArcGIS/rest/services/Ozarow_Maz_inwestycje_/FeatureServer/17
Oficjalna granica używana przez ten sam moduł:
https://services-eu1.arcgis.com/n7DhHnz2koymALo1/ArcGIS/rest/services/Ozarow_granica/FeatureServer/14
```

Hash modułu przy tym pobraniu: `6cae9e5c453af601cd302500b470fa16ec3e6f214f2986fa0d470ff8c6dbd5a6`.

Każde odświeżenie odkrywa adres modułu z bieżącego HTML, a w razie potrzeby przegląda ograniczoną kolejkę importów `/assets/` tej samej domeny. Hash nazwy pliku nie jest zamrożony. Moduł musi zawierać oba dokładne endpointy oraz rzeczywistą regułę `.filter(s=>s.properties.Kolejnosc!==-1)`. Zmiana tej reguły lub endpointów jest błędem wymagającym przeglądu, nie cichą zmianą interpretacji danych.

Wykluczony teraz OBJECTID **286** ma `Kolejnosc=-1`, tytuł „Wybierz inwestycję na mapie” i brak geometrii. Adapter wyklucza wszystkie takie wpisy zgodnie z frontendem, nie według tytułu i nie według braku punktu. Prawdziwy rekord bez punktu pozostaje na liście z ostrzeżeniem.

## Bramki kompletności, schematu i geometrii

1. Metadane muszą wskazywać `OBJECTID`, `GlobalID`, Point oraz wszystkie używane pola i ich typy; usługa musi obsługiwać paginację i porządek wyników. Dla granicy wymagane są FID i typ Polygon.
2. `returnCountOnly` i `returnIdsOnly` muszą być zgodne; IDs muszą być unikalnymi liczbami całkowitymi.
3. GeoJSON pobierany jest przez `resultOffset`/`resultRecordCount`, `orderByFields=OBJECTID ASC`, `outSR=4326`. Dla granicy używany jest `FID ASC`. Rozmiar strony wynosi `min(200, maxRecordCount)`; maksima: 50 000 rekordów na warstwę, 500 stron, 1100 prób HTTP w przebiegu, 20 odwiedzanych modułów, 20 MB na odpowiedź.
4. Każda strona musi mieć dokładnie oczekiwaną długość. Odrzucane są strukturalne błędy ArcGIS, złe CRS, niezgodne ID Feature/OBJECTID, zła kolejność, duplikaty oraz końcowy `exceededTransferLimit=true`. Po złączeniu sprawdzany jest **dokładny** zbiór uporządkowanych IDs, nie tylko liczba.
5. Powtarzane count/IDs i metadane muszą być niezmienione po pobraniu; zmiana `editingInfo` lub schematu unieważnia kandydata.
6. GlobalID zachowywany jest literalnie i sprawdzany pod kątem unikalności. Koszty muszą być nieujemne i finite albo `null`. Każdy punkt musi mieć dokładnie dwie finite współrzędne WGS84; adapter nie zaokrągla ani nie geokoduje.
7. Granica jest pobierana naprawdę, a jej Polygon/MultiPolygon musi być niepusty, poprawny i mieć poprawne współrzędne. Zasięg kontrolowany przez `boundary.covers(point)` obejmuje również sam brzeg. Zaobserwowany atrybut `JPT_NAZWA1` granicy to **pojedyncza spacja**, nie nazwa gminy: pochodzenie ustala dokładny endpoint `Ozarow_granica` w oficjalnym module, nie dopisana nazwa. Nie tworzymy sztucznego prostokąta granicy.
8. Punkt OBJECTID 400, inwestycja wodociągowa przy ulicy Ożarowskiej, jest poza tą granicą. **Pozostaje w danych i na mapie**, z ostrzeżeniem rekordowym i źródłowym. Nie jest to dowód błędu zakresu całego przedsięwzięcia.
9. Spadek liczby rekordów **lub liczby mapowanych rekordów o więcej niż 20%** względem zweryfikowanego prior blokuje zastąpienie snapshotu. Nie stosujemy historycznej liczby 438 jako dolnego progu.

Przejściowe timeouty, błędy połączenia, HTTP 408/429/500/502/503/504 oraz przejściowe kody ArcGIS 429/500/502/503/504 mają najwyżej trzy próby z opóźnieniami 0,5 i 1 s; timeout pojedynczego zapytania to 10 s na połączenie i 45 s na odczyt. Permanentne/schema errors nie są maskowane retry.

Przy błędzie: weryfikowany jest pełny wymagany kontrakt rekordów **tego sourceId**, bezpieczne URL, typy kosztów/geometrii, unikalność, metadane oraz licznik źródła. Poprawne stare rekordy pozostają niezmienione, źródło otrzymuje `retained`, zachowuje poprzedni `fetchedAt`/`sourceUpdatedAt` i jawny warning. Nieprawidłowy prior nie jest używany. Bez poprawnego prior wynik to `unavailable` i zero rekordów. Potwierdzony pusty zbiór jest odrębnie `fresh` (chyba że blokuje go loss guard). Błąd zapisu cache nie udaje udokumentowanego świeżego pobrania.

Retencja zmienia wyłącznie `status` i `warnings` źródła: poprzednie `coverage`, licznik i wszystkie pozostałe pola dowodowe pozostają dokładnie niezmienione. Komunikat o nieudanym odświeżeniu jest ostrzeżeniem, nie prefiksem dopisywanym do pokrycia. Regresja `test_real_retention.py` wymusza awarię HTTP w rzeczywistym `municipal.collect`, następnie przeprowadza pełny zweryfikowany prior przez centralne `build_dataset` i `refresh` do osobnego katalogu testowego, bez zmiany walidatora i snapshotu publicznego.

## Semantyka i ograniczenia ekspozycji

- Każdy rekord ma wszystkie i tylko klucze InvestmentRecord z `docs/INVESTMENT_CONTRACT.md`; źródło analogicznie InvestmentSource. ID ma postać `municipal-map:<literalny OBJECTID>`.
- Zachowane bez przepisania: `Tytul`, `Kategoria`, `KategorID`, `Status`, `Status_txt`, `Filtr_rok`, `Koszt_txt`, `Koszt_kalk`, `Obreb`, `Link`, `Zdjecie`, GlobalID, OBJECTID, XML_ID, Numer, Kolejnosc i techniczne daty (nie tożsamości edytorów). Surowe fakty są tekstami z atrybucją; status opisowy jest w `facts`, status główny w `status`. `Obreb` jest źródłową etykietą miejscowości/obrębu, nie nowym dopasowaniem administracyjnym.
- Wymagane brakujące `address` pozostaje pusty. Nie odgadujemy ulic, działek, relacji do GUNB ani tras. `relatedIds`, `parcelIds`, `events` pozostają puste.
- `fetchedAt=2026-10-03T12:18:00.462Z` oznacza pobranie; źródłowe metadane `lastEditDate=1782491646319` oznaczają **`2026-06-26T16:34:06.319Z`**. Rekordowe `EditDate` trafia oddzielnie do `sourceUpdatedAt` rekordu i jego geometrii; nie jest zastępowane datą metadanych ani pobrania. CreationDate i jego wersja UTC są faktami, nie datą inwestycji.
- `statusAsOf=null`: EditDate nie jest udokumentowaną datą oceny stanu budowy. Źródłowe czerwcowe/historczne etykiety nie są nowym potwierdzeniem październikowym.
- `years` pochodzi wyłącznie z jawnych czterocyfrowych lat `Filtr_rok`; oryginalny tekst też jest zachowany. Nie tworzymy dat 1 stycznia z lat, dlatego `dates=[]`.
- Koszt ma `kind=reported`, oryginalny `label=Koszt_txt`, `amount=Koszt_kalk`, `currency=PLN` zgodnie z aktualnym modułem i `scope=unknown`. **Rok kosztu pozostaje null**, bo Filtr_rok nie dowodzi roku finansowania. Nie uznajemy kwoty za umowę, plan roczny ani ostateczny koszt i nie sumujemy jej z innymi źródłami.
- Geometria zawsze `accuracy=source-point`, `parcelId=null` i jawna notatka „nie jest obrysem inwestycji, działką ani trasą”.
- Zapytania mają allowlistę pól, **bez Creator/Editor** i bez `outFields=*`. Metadane mogą zawierać nazwy tych pól, nigdy ich wartości w rekordach. Nie pobieramy pełnych opisów WordPress ani plików zdjęć. Publiczny dostęp do API i pusty copyrightText nie są ustaloną licencją na te materiały.
- Bezpieczne źródłowe Link/Zdjecie pozostają linkami do źródła, nie kopiami. Gdy Link brak/niebezpieczny, `sourceUrl` jest prawdziwym HTTPS zapytaniem do tej warstwy z dokładnym OBJECTID. Nie zgadujemy URL urzędu. Schematy nie-http(s), userinfo, kontrolne znaki/backslash i oczywiste parametry sekretów są odrzucane z ostrzeżeniem.
- Wszystkie zewnętrzne stringi są danymi tekstowymi, nie HTML. Adapter niczego nie wykonuje; konsumenci powinni używać zwykłego tekstu/React escaping, nie `innerHTML`.

## Testy i odtworzenie

TDD: pierwszy przebieg testów przed utworzeniem adaptera zakończył się oczekiwanymi niepowodzeniami „municipal adapter must exist”; kolejne RED obejmowały licznik prior, utratę geometrii, awarię cache i błędny typ metadanych. Finalne GREEN:

- **14 testów offline**, plus opcjonalny live-evidence test pomijany bez parametrów.
- Z realnym artefaktem: **15/15 testów adaptera i dowodów**.
- Istniejące testy Python danych: **79, OK, 1 skip**; workflow: **20, OK**. Nie uruchamiano frontendowych testów UI ani wdrożenia, bo adapter ich nie zmienia.
- `git diff --check`: OK. Brak commit/push/deploy.

Fixture `tests/investments/fixtures/municipal_observed.json` zawiera jawny wyciąg realnych obserwacji (OBJECTID 1, 9, 286, 400, metadane i rzeczywistą granicę). Jedyna celowa modyfikacja fixture to `maxRecordCount=2` do wymuszenia paginacji; to **wyłącznie dane testowe**, nigdy fallback produkcji. Testy używają jawnego serwera fixture i kontrolowanych mutacji odpowiedzi, nie syntetycznych danych udających realne pobranie.

Z katalogu tego worktree:

```bash
PY=/opt/data/ozarow-building-permits/.cache/venv/bin/python
$PY -m unittest discover -s tests/investments -p 'test_municipal*.py' -v

MUNICIPAL_LIVE_ARTIFACT=.cache/municipal-contribution.json \
MUNICIPAL_LIVE_EVIDENCE=.cache/municipal-evidence/municipal-20261003T121756-f183cce2/evidence.json \
$PY -m unittest discover -s tests/investments -p 'test_municipal*.py' -v
```

Osobne pobranie, bez zapisu do publicznych danych:

```bash
PYTHONPATH=scripts $PY -c 'from pathlib import Path; import json; from investment_sources.municipal import collect; result=collect(Path(".cache/municipal-evidence")); assert result["sources"][0]["status"]=="fresh", result["warnings"]; Path(".cache/municipal-contribution.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))'
```

W kolejnych cyklach centralny importer przekazuje `prior` jako pełny InvestmentDataset, nie wkład pojedynczego adaptera. Nazwę nowego katalogu dowodowego należy wziąć z realnego pobrania; test live nie pobiera danych samodzielnie ani nie wybiera „dowolnego ostatniego” snapshotu.

Live-evidence test niezależnie sprawdza hashe wszystkich zapisanych odpowiedzi, count/IDs, pełny kontrakt, **każdy zachowany atrybut każdego rekordu**, dokładne współrzędne i semantykę punktu, koszty null, odrębne daty oraz wynik sprawdzenia granicy. Zapisy dowodów i artefakt nie zawierają przykładowych udanych odpowiedzi zamiast realnego pobrania.
