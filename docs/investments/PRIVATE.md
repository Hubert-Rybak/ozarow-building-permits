# Adapter prywatny, środowiskowy, regionalny i FE

## Wynik rzeczywistego uruchomienia — 3 października 2026

Adapter zwraca **50 rekordów źródłowych**, z których **15 ma geometrię**, a **35 pozostaje na liście bez geometrii**. To nie liczba nowych budów. Artefakt wkładu ma dokładnie klucze `records`, `sources`, `warnings`, zgodnie z `docs/INVESTMENT_CONTRACT.md`. Niczego nie zapisano do `public/`, nie opublikowano i nie wdrożono.

| sourceId | Rekordy | Status | Pokrycie |
|---|---:|---|---|
| `environmental` | 19 | `fresh` | Całe 38 publikacji rocznika 2026, wszystkie 38 szczegółów i 52 załączniki; publikacje grupowane w jawnie udokumentowane tożsamości przedsięwzięć.[1] |
| `private-projects` | 3 | `static` | Aura Nova I, Hillwood Ożarów III, Apartamenty Home Premium II — II etap; dokumenty faktycznie pobrane i odczytane.[3][4][5] |
| `regional` | 4 | `static` | LK85/CPK, DP4120W Pogroszew–Umiastów, A2 i historyczny gazociąg.[6][7][8][9] |
| `eu-funding` | 24 | `fresh` | 24 różne umowy z 35 312 wierszy krajowego XLSX, stan 30 września 2026; filtr wyłącznie dokładnego miejsca realizacji.[10] |

**Geometrie:** 300 zweryfikowanych poligonów działek ULDK + 1 punkt źródłowy Hillwood = 301 obiektów. Zapytano 301 jednoznacznych identyfikatorów: 297 środowiskowych i 4 prospektowe; potwierdzono 300. Niezmapowana pozostaje `143206_5.0007.156` (Konotopa); nie podmieniono jej na działkę po podziale ani na punkt.[2]

## Pliki i użycie

Pliki implementacji:

- `scripts/investment_sources/private.py` — `collect(cache: Path, prior: dict | None = None) -> dict`, prawdziwe pobieranie, parsery, izolacja źródeł, walidacja i ULDK.
- `scripts/investment_sources/private_catalog.py` — jawne grupy publikacji i własne krótkie streszczenia FE; bez fuzzy scalania.
- `tests/investments/test_private.py` — 19 testów offline.
- `tests/investments/fixtures/private_environment.json` — minimalne faktyczne nagłówki/daty/identyfikatory BIP, bez pełnych artykułów, osób technicznych i kontaktów.
- `docs/investments/PRIVATE.md` — ten dokument.

Artefakty lokalne, ignorowane przez Git:

- `.cache/private-contribution.json` — rzeczywisty wkład 50 rekordów.
- `.cache/private-evidence.json` — liczniki, limity, oryginalne receipt timestamps, URL, SHA-256 oraz tylko bezpieczne odpowiedzi ULDK; surowe dokumenty nie są mirrorowane w tym eksporcie.
- `.cache/private-verification.json` — wynik walidacji wszystkich rekordów i zgodności każdego poligonu z oryginalnym WKT oraz timestampem.
- `.cache/private-http/` — prywatne odpowiedzi HTTP/PDF/XLSX wraz z oryginalnymi metrykami pobrania.
- `.cache/private-retention-test/` — wykonana próba awarii wszystkich czterech źródeł z pełnym prior; wszystkie 50 rekordów i wszystkie 301 geometrii zachowane jako `retained`.
- `.cache/private-red*.log`, `.cache/private-green*.log`, `.cache/private-regression.log` — RED → GREEN i regresje.

Minimalne wywołanie integracyjne (uruchamiane z katalogu repo):

```python
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from investment_sources.private import collect

contribution = collect(Path(".cache"), prior=previous_full_dataset)
```

Adapter nie zmienia `__init__.py`, centralnego importera, zależności projektu, UI ani workflow. Importer nadrzędny nadal odpowiada za połączenie wkładów, końcową walidację i transakcyjną publikację pojedynczego datasetu.

## Tożsamość i chronologia środowiskowa

`private_catalog.py` jawnie przypisuje literalne ID artykułów do tych samych przedsięwzięć na podstawie treści projektu, miejsca i wykazu działek. Kluczem rekordu jest pierwsze wskazane ID publikacji, a każda publikacja zachowuje własne ID zdarzenia, URL i datę. Daty decyzji i publikacji są odrębne. Różne projekty DATA4 (studnia i rozbudowa serwerowni) nie są scalane; działka studni nie oznacza całego campusu.[1]

`sourceUpdatedAt` grupy jest maksimum udokumentowanych edycji **wszystkich** jej artykułów, nie wyłącznie najnowszej publikacji. Dowodem jest `modify` albo `active` różne od podanego `originActive`; samo pierwotne `active` nie jest edycją. Przykład: wcześniejszy artykuł 95482 grupy 95445 ma `originActive=2026-05-06 10:44:20`, `active=2026-05-06 10:47:13`, czyli edycję `2026-05-06T08:47:13+00:00`, zachowaną także przy późniejszym nieedytowanym artykule. Metadane źródła biorą maksimum edycji wszystkich rekordów oraz maksimum receiptów artykułów/odczytanych załączników, nadal oddzielnie od dat decyzji/publikacji i receiptów geometrii ULDK.

Załączniki zawierają niekiedy sprzeczne znaki sprawy, w tym powtórzony znak dla kanalizacji i ulicy Kapuckiej. Nie obcinamy znaku do domniemanego numeru sprawy i nie scalamy po jego prefiksie. Artykuł `95918` ma nagłówek drogowy, a załącznik opisuje regulację Kanału Ożarowskiego w ramach tej drogi; rekord jawnie ostrzega o rozbieżności, zamiast automatycznie utożsamiać zakresy.[1]

W szczególności AJS PARTS w Jawczycach ma sześć zweryfikowanych działek: `143206_5.0005.44/2`, `.45/5`, `.46/8`, `.47/5`, `.49/10`, `.49/11`; publikacje 10 czerwca i 16 lipca 2026 nie stanowią dowodu rozpoczęcia budowy. Data center Płochocin ma 19 źródłowych działek z obrębu `0019`. Magazyn energii Grenergy na działce `143206_5.0017.147/8` ma decyzję środowiskową z 17 września 2026.[1][2]

Zakresy działek w tytułach, np. 30–209, 210 i 212–213 w PGR Strzykuły, są rozwijane literalnie. Historyczne działki wymienione jako „przed podziałem” są pomijane. Każdy rozwinięty identyfikator przechodzi osobną weryfikację ULDK; zakres nie jest domniemaną granicą zabudowy.[1][2]

Obręb `Pogroszew Kolonia` jest w ULDK literalnie nazwany `Pogroszew Kol.` i zweryfikowany jako `143206_5.0017`. To jawnie udokumentowana identyfikacja, nie domyślne geokodowanie nazwy. Malformed `001` i `011` w źródłach hal pozostają niezmapowane — żadnego dopisywania zera.[1][2]

Wszystkie 52 załączniki pobrano i sprawdzono czytelność PDF. Tekstowe obwieszczenia są odczytane, skany linkowane i oznaczone. Ręczne odczyty/OCR części decyzji pomogły zweryfikować nazwy spółek; nie kopiujemy pełnego OCR ani nazw przedstawicieli. Nie twierdzimy, że kompletnie odczytano wszystkie strony wszystkich skanów.

## Prywatne źródła i dokładność

Aura Nova I: w treści prospektu aktualizacja **24 marca 2026**, adres Kapucka 34 i 36, działki 46/3, 47/1, 74/25, poprawny obręb 0003. Miasto jest w ULDK jednostką `143206_4`, nie wiejskimi Duchnicami `143206_5.0003`. Prospekt deklaruje pozwolenie na użytkowanie z 16 października 2025 i możliwe zajęcie części 46/3 oraz 47/1 pod drogę. Pokazane są działki, nie obrysy dwóch budynków.[3][2]

Hillwood: punkt `[20.776937, 52.210795]` z rzeczywistego HTML inwestora, `accuracy=source-point`; park istniejący oferowany na wynajem. Nie publikujemy odkrytych marketingowych obrysów hal i terenu: nie ustalono licencji ani dokładności EGiB.[4]

Home Premium: główna tabela ma niepoprawne `003`, którego nie poprawiono. Niezależna część notarialna tego samego prospektu podaje dla tej samej działki 77/4 poprawny literalny obręb `0003`; wyłącznie ta identyfikacja uzasadnia `143206_4.0003.77/4`. Pełna data sporządzenia prospektu jest niewypełniona — nie użyto daty katalogu URL jako daty dokumentu.[5][2]

Dodatkowy prospekt z `inwestycjaozarow.pl` sprawdzono sieciowo; pobranie zatrzymał błąd TLS. Nie włączono wymyślonego rekordu ani danych z nieodczytanego dokumentu.

## Regionalne — bez wymyślonej trasy

LK85: decyzja lokalizacyjna **160/SPEC/2026 z 8 września 2026**, aktualizacja artykułu BIP 30 września, pierwotna publikacja o wszczęciu 25 czerwca. Tunel km 4+762–13+673, zakres linii w decyzji km 4+762–14+200. Załącznik `203399` faktycznie pobrano: 12 stron skanów. Wykonano OCR badawczo, ale kolumny, podziały działek i nawiasy są niejednoznaczne; bez zatwierdzonego wykazu nie publikujemy działek ani geometrii CPK.[6]

DP4120W: komunikat 2 października zapowiada początek 5 października 2026, ok. 1600 m Pogroszew–Umiastów, od DP4121W do DW718. Na dzień kontroli 3 października start jest przyszły; status pozostaje zapowiedzią, a nie rozpoczęciem robót.[7]

A2: komunikat wojewody 3 kwietnia 2025 obejmuje gminę, ale sam nie dowodzi początku prac ani dokładnego odcinka w gminie; brak załączników ZRID/geometrii. Gazociąg: lista i mapa BIP z 15 stycznia 2016 są historycznym planem, nie aktualnym przebiegiem powykonawczym.[8][9]

PWZ nie podaje w TLS certyfikatu pośredniego. Adapter pobiera certyfikat z oficjalnego repozytorium Certum i wykonuje `openssl verify` wobec **istniejących zaufanych korzeni**, zanim zbuduje lokalny bundle. TLS i sprawdzanie nazwy hosta pozostają włączone; nie używamy `verify=False` i nie zmieniamy certyfikatów systemu.

## FE — filtr, kwoty i daty

Link XLSX jest odkrywany z oficjalnej strony przez rzeczywiste `href`/`data-url` przycisku pobierania, nie składany z aktualnej daty. Arkusz identyfikowany po nazwie i relacji w ZIP, czytany strumieniowo przez stdlib XML/ZIP. Sprawdzany jest header, snapshot, daty, nieujemne kwoty i unikalność lokalnego numeru umowy.[10]

Filtr obejmuje **dokładne `GM.: Ożarów Mazowiecki` w miejscu realizacji**, nie nazwę beneficjenta ani jego siedzibę. Każdy z 24 rekordów zachowuje numer umowy, beneficjenta, program, fundusz, działanie, własny krótki opis, źródłowy zakres geograficzny, daty rozpoczęcia/zakończenia i kwoty. Żaden rekord FE nie ma wygenerowanego adresu lub geometrii.[10]

15 umów jest wielogminnych, 9 ma jedną gminę w źródłowym miejscu realizacji. Koszty `project-total` i `eu-contribution` dla wielogminnych dotyczą **całego projektu**, nie są w całości przypisane Ożarowowi. W aktualnym XLSX **nie ma kolumny kosztów kwalifikowalnych**; `eligible.amount=null` z jawnym opisem braku, bez obliczania z procentu.[10]

Liczby są konwertowane z rzeczywistych wartości komórek, a ich oryginalne reprezentacje tekstowe zachowane jako fakty. Ułamkowych dat Excel nie zaokrąglamy do następnego dnia; bierzemy ich dzień kalendarzowy zgodnie z systemem 1900/1904 skoroszytu. Snapshot 30 września jest datą, nie fikcyjnym timestampem edycji o północy.

## Zachowanie awaryjne, limity i dowody

- `prior` oznacza pełny dataset, a filtrowanie następuje wyłącznie po `sourceId`.
- Błąd źródła, schema/typy/daty, duplikaty oraz utrata ponad 20% rekordów, publikacji lub geometrii zatrzymują zastąpienie wcześniejszego źródła.
- Wcześniejsze rekordy zachowywane są bez zmiany timestampów jako `retained`; bez prior źródło jest `unavailable`, z jawnym ostrzeżeniem.
- Oryginalne `fetchedAt` nigdy nie pochodzi z mtime. Receipt waliduje URL, SHA-256, timestamp i TTL. Cache źródeł: 24 h; **wyłącznie pozytywne i ponownie walidowane** ULDK: 30 dni.
- 4 workery, 3 próby, timeout połączenia 15 s / odczytu 75 s, max 100 MB/download, max 2000 artykułów. Nie ma ukrytego limitu działek — wszystkie 301 jednoznacznych ID próbowano.
- Jednostka, exact region ID/nazwa/gmina, exact parcel ID, status `0`, jedna odpowiedź, `SRID=4326`, poprawny niepusty Polygon/MultiPolygon i współrzędne przechodzą kontrolę przed użyciem.
- Wszystkie poligony w artefakcie porównano z oryginalnym WKT, URL i oryginalnym receipt timestampem. Żadnego „repair geometry”, zmiany osi, SRID ani syntetycznej pinezki.
- Privacy audit artefaktu: 0 adresów e-mail, 0 technicznych pól osób/kontaktów/cookies/tokenów, 0 geometrii marketingowych.

## Testy i zależności

Zależności runtime: istniejące `requests`, `Shapely`, dodatkowo **PyMuPDF** do realnego odczytu PDF; stdlib obsługuje XLSX. Dla naprawy brakującego intermediate PWZ wymagany `openssl`. Nie zmieniono wspólnej listy zależności; integrator musi dopisać PyMuPDF. Tesseract/Pillow były użyte wyłącznie do badawczego OCR w prywatnym cache, nie są wymagane przez adapter.

Wykonano:

```text
RED #1: 13 failures — brak adaptera
RED #2: brak obsługi literalnego prefiksu powiatu, data-url oraz poprawnego chain TLS
RED #3: brak własnych opisów FE i zachowania per-document timestamps
RED #4: brak blokady błędnego zagnieżdżonego schematu
GREEN: Ran 19 tests ... OK
Regresje: 97 passed, 1 skipped, 45 subtests passed in 59.20s
```

Polecenia użyte do wykonania (lokalny target PyMuPDF/pytest nie zmienia deps projektu):

```sh
PYTHONPATH=.cache/private-deps /opt/data/ozarow-building-permits/.cache/venv/bin/python -m unittest discover -s tests/investments -p 'test_private*.py' -v
PYTHONPATH=.cache/private-deps /opt/data/ozarow-building-permits/.cache/venv/bin/python -m pytest tests/data tests/investments -q
```

SHA-256 `.cache/private-contribution.json`: `a0d6d98e1edaab03db0290f44e345de87a30766c3f45a2dacbc617a4a3fae08d`.

SHA-256 `.cache/private-evidence.json`: `fa31a4512b726fa9dc0ff023203c68a44aff71f65d535b1fee61c790dd0bc350`.

Finalne uruchomienie ponownie użyło 416 oryginalnych odpowiedzi; po wcześniejszym rzeczywistym pobraniu źródeł i geometrii **nie nadpisano dat receiptów datą finalnego uruchomienia**. Te dwa hashe identyfikują tę konkretną generację lokalną, a nie przyszłe odświeżenia.

## Sources

[1] https://bip.ozarow-mazowiecki.pl/api/menu/23699/articles?limit=100&offset=0
[2] https://uldk.gugik.gov.pl
[3] https://aura-nova.pl/wp-content/uploads/2025/11/Prospekt-Informacyjny_Aura-Nova-I.pdf
[4] https://www.hillwood.pl/nieruchomosci/hillwood-ozarow-iii
[5] https://homepremium.pl/wp-content/uploads/2025/09/Prospekt-informacyjny-02.09.2025-6.pdf
[6] https://bip.ozarow-mazowiecki.pl/api/articles/95745
[7] https://pwz.pl/news/uwaga-roboty-drogowe-w-gminie-ozarow-mazowiecki
[8] https://www.gov.pl/web/uw-mazowiecki/trzeci-pas-na-a2--wazne-decyzje-wojewody
[9] https://bip.ozarow-mazowiecki.pl/m,20115,planowana-budowa-gazociagu-rembelszczyzna-mory-wola-karczewska.html
[10] https://funduszeeuropejskie.gov.pl/wp-content/uploads/2026/10/Lista_projektow_FE_2021_2027_30092026-1.xlsx
