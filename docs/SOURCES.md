# Źródła, zakres i codzienne odświeżanie

## Oficjalne źródła

Publiczna mapa GUNB prowadzi do oficjalnych archiwów CSV. Importer nie omija CAPTCHA, nie korzysta z nieudokumentowanego API JSON i nie uzupełnia braków fikcyjnymi wpisami.[1][2]

Używane są dwa archiwa: mazowiecki eksport wniosków/decyzji oraz krajowy eksport zgłoszeń od 2022 roku.[3][4] Strona pobierania, ponownie sprawdzona **3 października 2026**, opisuje dane od 1 stycznia 2016 i codzienną aktualizację w godzinach nocnych. Opis podaje separator `#`, lecz rzeczywiście pobrane eksporty mają separator `;`; importer rozpoznaje oba.[2] Zgłoszenia z wybranego archiwum nie mają tak długiego zakresu jak eksport wnioskowy.

Geometrie pochodzą z oficjalnej usługi ULDK GUGiK, wyłącznie z `GetParcelById`, `result=geom_wkt,id`, `srid=4326`. Wymagane są: sukces, dokładnie jeden wynik, **identyczny identyfikator zwrócony**, jawny `SRID=4326`, poprawny niepusty Polygon/MultiPolygon i poprawna kolejność długość/szerokość geograficzna. Nie stosujemy wyszukiwania po nazwie obrębu ani punktów zastępczych.[5]

## Cała gmina i identyfikatory

- Zakres obejmuje **miasto i obszar wiejski**, nie tylko miejscowość Ożarów Mazowiecki. Jednostki źródłowe `143206_4` i `143206_5` są sprawdzane przez `GetCommuneById`: oba zapytania wskazują `143206_3 | Ożarów Mazowiecki | powiat warszawski zachodni`.[6][7]
- Rekord należy do zakresu, jeśli ma jednostkę `143206_4`/`143206_5` **albo** TERC `1432063`/`1432064`/`1432065`. Wpisy ze sprzecznymi/brakującymi odwołaniami pozostają widoczne jako częściowe lub nierozwiązane; nie otrzymują geometrii na podstawie nazwy miejscowości.
- Obręb sprawdzamy przez `GetRegionById`, wymagając dokładnego ID i gminy Ożarów Mazowiecki. Pełny identyfikator działki `WWPPGG_R.OOOO.[AR_NR.].NR_DZ` tworzymy tylko z poprawnych źródłowych tokenów.[5]
- Nie poprawiamy `_2` na `_5`, `3` na `0003` ani innych błędnych ID. Nie wyszukujemy przybliżonej pary „miejscowość + działka”.
- Wiersze wielu działek łączymy według identyfikatora systemowego GUNB. Kontrakt `permits.json` pozostaje `schemaVersion: 1`; pola rekordu są allowlistą. Właściwości GeoJSON pozostają dokładnie `id`, `parcelNumber`, `region`, `permitIds`, `sourceUrl`.

## Rzeczywiste odświeżenie z 3 października 2026

Wyniki obliczono z rzeczywistych wygenerowanych plików i sprawdzono testami powiązań w obie strony:

| Pozycja | Wynik |
|---|---:|
| Unikalne wpisy GUNB | **447** |
| Wpisy z odnotowaną decyzją | **346** |
| Zgłoszenia | **101** |
| Wpisy typu sam wniosek bez odnotowanej decyzji | **0** |
| Potwierdzone wielokąty działek ULDK | **842** |
| Działki miasta `143206_4` | **176** |
| Działki obszaru wiejskiego `143206_5` | **666** |
| Wpisy ze wszystkimi odwołaniami potwierdzonymi | **370** |
| Wpisy z częścią geometrii | **29** |
| Wpisy bez potwierdzonej geometrii | **48** |
| Unikalne poprawne składniowo odwołania działkowe sprawdzone | **934** |
| Odwołania bez wiarygodnej geometrii | **92** |
| Odwołania poza limitem | **0** |
| Obręby pozytywnie potwierdzone przez ULDK PRG | **44** |
| Wiersze CSV w zakresie dat i gminy | **1111** |
| Publiczne, zweryfikowane odpowiedzi ULDK w cache dowodowym | **888** |

W porównaniu z wycinkiem pobranym 2 października: **2 dodatkowe wpisy decyzji i 3 dodatkowe obrysy**, bez twierdzenia, że mają najnowszą datę wpływu. Filtr dat wpływu to **2025-01-01–2026-10-03 włącznie**, faktyczne daty wpisów nadal **2025-01-09–2026-09-23**. Świeże pobranie nie oznacza, że źródło udostępnia wszystkie zdarzenia z dnia pobrania.

Końcowe archiwa pobrano **2026-10-03 05:44:05.741668 UTC** (wnioski/decyzje) i **05:44:18.491338 UTC** (zgłoszenia). Serwer podał odpowiednio `Last-Modified: Fri, 02 Oct 2026 21:35:13 GMT` i `Fri, 02 Oct 2026 21:36:10 GMT`. To znaczniki serwera HTTP, nie obietnica kompletności rejestru. Dokładne URL, SHA-256, ETag, wielkości i czasy rzeczywistego pobrania są w `metadata.json`.

Geometrie mają rzeczywiste czasy pobrania **2026-10-02 21:44:00.391116–2026-10-03 05:37:02.071574 UTC**. Ostatnią generację utworzono **2026-10-03 06:22:23.877999 UTC**, podczas końcowej walidacji offline już świeżo pobranych źródeł. Potwierdzono **0 wywołań HTTP** w tej walidacji, `geometryCoverage.reusedParcelCount: 842`, `freshParcelCount: 0` i `publicEvidenceResponseCount: 888`. `refreshPolicy.sourcesForced: false` prawidłowo opisuje końcowe odtworzenie offline; rzeczywiste wymuszone pobranie obu ZIP-ów odbyło się wcześniej o 05:44 UTC. Czasy źródeł/geometrii nie są zastępowane czasem generacji lub checkoutu Git.

Przeprowadzono dwa rzeczywiste importy online ze wszystkimi odwołaniami (`--max-parcels 0`). Drugi działał z **pustym prywatnym cache**, tak jak nowy runner CI: ponownie pobrał oba ZIP-y, ponownie zweryfikował 888 publicznych dowodów ULDK i uzyskał te same 447 rekordów/842 obrysy. Niedopasowane odwołania ponownie sprawdzano w usłudze; błędów nie utrwala się w cache.

## Ograniczenia, których nie wolno ukrywać

1. **Decyzja ≠ pozwolenie.** Eksport podaje numer i datę decyzji, lecz nie wynik rozstrzygnięcia. Etykieta brzmi „Decyzja odnotowana — wynik nieudostępniony w CSV”, nigdy automatycznie „Zatwierdzone”. Data wpływu jest zachowana w jednym rekordzie typu `decision`.
2. Wszystkie 346 wpisy wnioskowe w tym wycinku mają odnotowaną decyzję. **Nie oznacza to braku nierozpatrzonych wniosków w gminie ani kompletności rejestru spraw oczekujących.** Nie dodajemy fikcyjnych rekordów `application`.
3. Wszystkie 101 zgłoszeń w wycinku mają źródłowy status „Brak sprzeciwu”; zachowują rodzaj `notification`, nie są pozwoleniami. Nieznany swobodny tekst statusu jest pomijany i liczony w statystykach, zamiast publikować potencjalne dane osobowe.
4. W **35 wierszach** zakresu występują błędne, obce lub niejednoznaczne odwołania katastralne. Źródłowe nazwy miejscowości nie są oficjalną listą miejscowości gminy. Sprzecznych wpisów wybranych po TERC nie naprawiamy.
5. Nie udało się potwierdzić obrębów `143206_4.0013`, `143206_4.0031`, `143206_5.0015`. Pozostałe błędy obejmują brak wyników lub niepoprawne odpowiedzi powiatowe/usługowe. Nie rozstrzygamy, czy dawną działkę podzielono.
6. Geometria przedstawia **stan podczas pobrania**, nie granice historyczne w dniu złożenia wniosku. Po upływie 30 dni dowód ULDK musi być odświeżony; nie przedłużamy ważności przez zmianę daty pliku.
7. Zakres jest filtrem **daty wpływu**, nie daty wydania decyzji. Starsze wnioski mogą mieć nowsze decyzje poza tym zbiorem. Zgłoszenia sprzed 2022 wymagają osobnego oficjalnego archiwum; obecny plik nie zapewnia ich pokrycia.[4]
8. Publiczny tytuł jest automatycznym, ogólnym skrótem rodzaju inwestycji, nie dosłownym opisem ani kwalifikacją prawną.

## Prywatność przy publicznym repozytorium

Wykluczenie kolumn inwestora/projektanta **nie wystarcza**: swobodny opis może zawierać imię i nazwisko także przy pustym polu inwestora. W aktualnych 1111 wybranych wierszach **623** mają puste pole inwestora, a **70** opisów ma wskaźnik wymagający ostrożności, np. „dla”, „inwestor” lub znak kontaktu. Nie jest to dowód, że wszystkie te 70 opisów zawierają dane osobowe.

Dlatego **nie publikujemy surowych tytułów/opisów GUNB**. Zamiast nich importer emituje wyłącznie stały słownik ogólnych etykiet (np. „Budowa — budynek mieszkalny jednorodzinny”) i jawny komunikat o pominięciu opisu. Taki skrót nie może skopiować nieznanego nazwiska, telefonu, adresu e-mail lub PESEL z tekstu. Pola inwestorów, imion/nazwisk projektantów i uprawnień nadal nie trafiają do allowlisty. Adres inwestycji i oficjalne identyfikatory spraw/działek pozostają częścią zestawu.

Audyt **408 unikalnych tokenów z osobowych pól źródłowych** wykazał **0 dopasowań w opublikowanych tytułach/opisach**. Audyt i testy wypisują wyłącznie liczby lub identyfikatory spraw/działek, nie prywatne wartości. To dodatkowa kontrola, nie uzasadnienie powrotu do surowego free-text.

**Kontrola przed upublicznieniem historii Git:** read-only audyt początkowego prywatnego commitu `29b4ca3` wykazał 445 rekordów ze swobodnymi tytułami i 445 niepustych swobodnych opisów, niezgodnymi z obecnym kryterium publikacji. W 42 rekordach występują kontekstowe znaczniki wymagające ostrożności. Brak dopasowań 405 znanych tokenów osobowych oraz brak wzorców e-mail/11 cyfr/telefonu nie dowodzi braku innych danych osobowych. **Ten commit nie przechodzi aktualnej polityki publicznej. Przed zmianą widoczności repozytorium trzeba zanonimizować całą osiągalną historię zawierającą wcześniejsze opisy; poprawienie samych plików w HEAD nie wystarcza.** Audyt nie zmienił Gita ani nie ujawnił nazwisk.

Surowe ZIP/CSV są tylko w ignorowanym prywatnym `.cache/` (katalog `0700`). Importer odmawia cache pod `public/` lub katalogiem `--output`. **Nie wolno zapisywać surowego cache w GitHub Actions cache ani uploadować go jako artefaktu.** Nigdy nie publikuj całego `.cache/`.

### Publiczny cache dowodów ULDK, bez surowych CSV

`scripts/uldk-cache.json` jest osobnym plikiem do śledzenia w repozytorium, **poza artefaktem strony**. Zawiera wyłącznie sprawdzone odpowiedzi ULDK dla działek, obrębów i gminy: kanoniczny oficjalny URL, oryginalny tekst odpowiedzi, rzeczywisty `downloadedAt` oraz SHA-256 tekstu. Nie zawiera CSV, ZIP ani inwestorów/projektantów. Obecnie zawiera 888 odpowiedzi i ma około 606 kB.

Importer przed użyciem weryfikuje ponownie allowlistę domeny i operacji, kanoniczny URL, SHA-256, dokładny ID/SRID, poprawność wielokąta i czas pobrania. Dowody starsze niż 30 dni, daty przyszłe, błędy, obce ID oraz niedozwolone URL są ignorowane. Sam pozytywny wynik walidacji geometrii bez prawdziwej daty pobrania nie tworzy dowodu.

W codziennym CI trzeba zachować w repozytorium **zarówno `public/data/`, jak i `scripts/uldk-cache.json`**, aby nowe geometrie i ich prawdziwe daty mogły być użyte przez kolejny runner. Nie trzeba używać Actions cache. Pozytywne odpowiedzi mają TTL liczony z `downloadedAt`, także w trybie offline. Nie cache'ujemy odpowiedzi negatywnych.

## Uruchomienie

Python 3.12+; zależności z `requirements-data.txt`:

```bash
python3 -m venv .cache/venv
.cache/venv/bin/python -m pip install -r requirements-data.txt

# Codzienny publiczny import: oba ZIP-y zawsze świeżo pobrane;
# pozytywne ULDK/PRG pozostają użyteczne do 30 dni.
.cache/venv/bin/python scripts/import_data.py --refresh-sources --max-parcels 0

# Dokładny zakres obecnego zestawu:
.cache/venv/bin/python scripts/import_data.py --refresh-sources --since 2025-01-01 --until 2026-10-03 --max-parcels 0

# Pełne odświeżenie również wszystkich pozytywnych odpowiedzi ULDK:
.cache/venv/bin/python scripts/import_data.py --refresh --until 2026-10-03

# Odtworzenie bez sieci: oba ZIP-y z potwierdzonymi receiptami
# oraz pozytywne odpowiedzi ULDK nie starsze niż 30 dni.
.cache/venv/bin/python scripts/import_data.py --offline --until 2026-10-03

# Mniejszy/historczny zakres lub limit obrysów: osobny output/cache dowodowy,
# aby nie zastąpić pełnego publicznego zestawu.
.cache/venv/bin/python scripts/import_data.py --max-parcels 200 --output .cache/sample-data --uldk-public-cache .cache/sample-uldk.json

# Testy offline, również rzeczywistej geometrii i dowodów publicznych:
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/data -v
```

`--since`/`--until` wymagają ISO, `--workers` dopuszcza 1–6, `--max-parcels 0` oznacza wszystkie. Limit dotyczy wyłącznie obrysów, nie liczby rekordów; pominięcia są jawne. `--refresh-sources` jest rozłączne z `--offline`; `--refresh` odświeża oba rodzaje źródeł/cache. Domyślny import bez flag odświeżania może użyć źródłowego ZIP-u do 24 godzin i dlatego **nie jest poleceniem codziennego wymuszonego pobrania**.

## Zabezpieczenia przed utratą opublikowanych danych

- Maksymalnie trzy próby na URL, ULDK timeout `10/30 s`, ZIP `15/150 s`, ograniczone opóźnienia i równoległość.
- ZIP: CRC, limit 200 MiB pobrania i 1 GiB rozpakowanego CSV, SHA-256 oraz osobny receipt HTTP z prawdziwą datą, ETag i Last-Modified. Nie używamy `mtime` jako dowodu pobrania.
- Każdy wykorzystywany nagłówek jest wymagany osobno dla każdego źródła; niepoprawna liczba pól lub nieoczekiwane duplikaty kolumn są błędem. Dozwolony jest znany duplikat `cecha`.
- Brak rekordów jednej kategorii, całkowity brak geometrii, brak systemowego ID lub niepoprawna data w wierszu z gminy blokują publikację. Niepoprawne **odwołania działkowe** nie usuwają rekordów: pozostają partial/unresolved.
- W porównaniu z poprzednim zestawem spadek **większy niż 20%** liczby rekordów, geometrii lub jednej kategorii źródłowej blokuje publikację. Nie można zawęzić istniejącego zakresu dat; do mniejszego wycinka trzeba użyć osobnego `--output`. Nie ma automatycznego obejścia tych zabezpieczeń w codziennym CI.
- Przed jakimkolwiek zapisem publikacyjnym wspólny `validate_artifacts` sprawdza cały kandydat: pola i typy, unikalność ID, powiązania w obie strony, liczniki, daty i dokładną zgodność geometrii z dowodami ULDK. `permits.json`, `parcels.geojson` i `metadata.json` mają identyczne `generatedAt`.
- Wszystkie trzy pliki i cache dowodowy serializujemy/fsync w stagingu, ponownie odczytujemy i walidujemy przed commitowaniem. Linux używa atomowego `renameat2(RENAME_EXCHANGE)` katalogu danych; przenośny fallback ma rollback. Obsługiwany błąd zapisu lub publikacji przywraca poprzednie bajty trzech plików **i** cache dowodowego. Dwa niezależne cele nie tworzą jednak jednej transakcji odpornej na nagłe przerwanie procesu/zasilania.
- Testy pokrywają kontrakt v1, miasto/wieś, daty, deduplikację, decyzja ≠ pozwolenie, brakujące wnioski oczekujące, pełne/częściowe powiązania, dokładne ID, WGS84 Polygon/MultiPolygon, błędny WKT, retry, TTL względem daty dowodu, odświeżanie samych ZIP-ów, prywatność przy pustym inwestorze i rollback. Każdy z **842** publicznych obrysów porównano z jego oryginalną odpowiedzią ULDK w prywatnym i publicznym cache dowodowym.

## Sources

[1] https://wyszukiwarka.gunb.gov.pl/mapa-api/
[2] https://wyszukiwarka.gunb.gov.pl/pobranie.html
[3] https://wyszukiwarka.gunb.gov.pl/pliki_pobranie/wynik_mazowieckie.zip
[4] https://wyszukiwarka.gunb.gov.pl/pliki_pobranie/wynik_zgloszenia_2022_up.zip
[5] https://uldk.gugik.gov.pl/opis.html
[6] https://uldk.gugik.gov.pl/?request=GetCommuneById&id=143206_4&result=id%2Ccommune%2Ccounty&srid=4326
[7] https://uldk.gugik.gov.pl/?request=GetCommuneById&id=143206_5&result=id%2Ccommune%2Ccounty&srid=4326
