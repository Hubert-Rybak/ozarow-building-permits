# Źródła, zakres i odtwarzanie danych

## Oficjalne źródła

Mapa publiczna GUNB prowadzi do eksportów CSV i obsługuje pełne identyfikatory działek. Nie używamy CAPTCHA ani niepublicznego API.[1]

Pobrano dwa oficjalne archiwa: mazowiecki eksport wniosków/decyzji oraz krajowy eksport zgłoszeń od 2022 roku.[3][4] Strona pobierania opisuje dane od 1 stycznia 2016 roku, codzienną aktualizację i UTF-8. Wbrew jej opisowi separatora `#`, pobrane 2 października 2026 pliki mają separator `;`; importer rozpoznaje oba warianty z nagłówka.[2]

Geometrie pobrano z oficjalnej usługi ULDK GUGiK przez `GetParcelById`, z `result=geom_wkt,id` i `srid=4326`. Dokumentacja dopuszcza pełny identyfikator `WWPPGG_R.OOOO.[AR_NR.].NR_DZ` i ostrzega, że wyszukiwanie po nazwie obrębu może być niejednoznaczne. Takiego wyszukiwania nie stosujemy.[5]

## TERYT i obręby: bez zgadywania

- Jednostki `143206_4` (miasto) i `143206_5` (obszar wiejski) pochodzą bezpośrednio z kolumn ewidencyjnych GUNB, nie z nazw miejscowości.[3][4]
- Zapytania ULDK `GetCommuneById` dla obu jednostek zwróciły `143206_3 | Ożarów Mazowiecki | powiat warszawski zachodni`.[6][7]
- Przed pobraniem geometrii weryfikujemy `GetRegionById` z `result=id,region,commune`: wymagamy dokładnego ID i gminy Ożarów Mazowiecki. Pełne ID działki tworzymy wyłącznie z poprawnych składniowo pól źródłowych. W odpowiedzi działkowej wymagamy dokładnie tego samego ID.[5]
- Filtr całej gminy: poprawna jednostka ewidencyjna `143206_4` lub `143206_5`, **albo** TERC `1432063`, `1432064`, `1432065`. Dzięki temu import nie ogranicza się do nazwy miasta i zachowuje również wpisy ze sprzecznym/brakującym opisem katastralnym. Takie wpisy nie otrzymują geometrii na podstawie domysłu.
- Nie poprawiamy `_2` na `_5`, numeru obrębu `3` na `0003` ani innych błędnych identyfikatorów. Nie szukamy po samej parze „miejscowość + numer działki”.

## Zweryfikowany wycinek z 2 października 2026

Statystyki poniżej policzono z opublikowanych artefaktów, nie z szacunków:

| Pozycja | Wynik |
|---|---:|
| Unikalne wpisy GUNB po połączeniu wierszy działek | **445** |
| Wpisy z odnotowaną decyzją | **344** |
| Zgłoszenia | **101** |
| Wpisy typu sam wniosek bez odnotowanej decyzji | **0** |
| Potwierdzone wielokąty działek ULDK | **839** |
| Potwierdzone działki miasta `143206_4` | **173** |
| Potwierdzone działki obszaru wiejskiego `143206_5` | **666** |
| Wpisy ze wszystkimi odwołaniami potwierdzonymi | **368** |
| Wpisy z częścią geometrii | **29** |
| Wpisy bez potwierdzonej geometrii | **48** |
| Poprawne składniowo unikalne odwołania działkowe sprawdzone przez importer | **931** |
| Odwołania bez wiarygodnej geometrii | **92** |
| Poprawne odwołania pozostawione poza limitem | **0** |
| Obręby pozytywnie potwierdzone przez ULDK PRG | **44** |

Zakres filtra daty wpływu: **2025-01-01–2026-10-02 włącznie**. Faktycznie dostępne daty wpływu: **2025-01-09–2026-09-23**. Nie jest to filtr dat wydania decyzji: decyzje dotyczące starszych wniosków nie są częścią tego wycinka.

Archiwa GUNB pobrano 2 października 2026 około 21:33 UTC. Geometrie z potwierdzonych odpowiedzi ULDK pobrano **2026-10-02 21:44:00–21:50:32 UTC**. Generacja JSON może być późniejsza niż pobranie, także przy odtworzeniu offline. `metadata.json` zawiera dokładne znaczniki czasu, sumy SHA-256 obu ZIP-ów, liczby wierszy, katalog obrębów, listę niepotwierdzonych ID oraz statystyki do niezależnej weryfikacji.

## Jawne ograniczenia

1. **Decyzja ≠ pozwolenie.** Pobrany CSV ma datę i numer decyzji, ale nie wynik rozstrzygnięcia. W aplikacji należy pokazać „Decyzja odnotowana — wynik nieudostępniony w CSV”, nie „Zatwierdzone”. Wniosek z odnotowaną decyzją jest jednym wpisem typu `decision`, zachowującym datę wpływu.
2. W wycinku wszystkie 344 wpisy wnioskowe mają odnotowaną decyzję. **Nie oznacza to braku nierozpatrzonych wniosków w gminie ani kompletności rejestru pending applications.** Nie utworzono fikcyjnych wpisów typu `application` dla zapełnienia filtra.
3. W tym wycinku wszystkie 101 zgłoszeń mają źródłowy status „Brak sprzeciwu”. Zgłoszenia zachowują rodzaj `notification` i nie są przedstawiane jako wydane pozwolenia.
4. Źródło zawiera sprzeczne TERC/jednostki/obręby i nazwy miejscowości spoza gminy. W 35 wierszach zakresu występują nieprawidłowe, obce lub niejednoznaczne odwołania katastralne; zachowano wpisy wybrane po TERC jako jawnie niepewne. Nie utożsamiamy 32 źródłowych etykiet miejscowości z listą 32 administracyjnych miejscowości gminy.
5. Nie udało się potwierdzić obrębów `143206_4.0013`, `143206_4.0031`, `143206_5.0015`. Pozostałe niepowodzenia działkowe obejmują odpowiedzi „brak wyników”, błędy odpowiedzi powiatowej i inne brakujące/nieprawidłowe odpowiedzi. Nie rozstrzygamy, czy konkretna działka została podzielona, czy wpis/usługa ma błąd.
6. Geometria jest stanem ULDK **z chwili pobrania**, nie rekonstrukcją granic w dniu złożenia wniosku. Odświeżenie może zmienić obrys lub pozostawić dawny numer nierozwiązany. Nie generujemy prostokątów, punktów zastępczych ani poligonów syntetycznych.
7. Zbiór nie obejmuje dat wpływu sprzed 2025 roku ani nowszych, niedostępnych jeszcze w eksporcie. Archiwum zgłoszeń użyte przez importer zaczyna się w 2022 roku; dla szerszego zakresu sprzed 2022 trzeba dodać osobne archiwum historyczne.[4]

## Prywatność

Publikujemy wyłącznie allowlistę pól z kontraktu `docs/PLAN.md`. Pola inwestorów, nazwisk/imion projektantów i ich uprawnień nie są eksportowane. Znane imiona/nazwiska z tych pól są także usuwane z tytułów/opisów. Kontrola 2674 źródłowych tokenów osobowych w wybranych wierszach wykazała **0 pozostałych dopasowań w opublikowanych tytułach/opisach**; kontrola wypisuje tylko liczby, nie nazwiska.

Surowe archiwa zostają wyłącznie w `.cache/`, poza `public/`, i są ignorowane przez Git. Katalog cache ma uprawnienia `0700`. Nie należy wysyłać surowych CSV/ZIP-ów do repozytorium ani publikować całego cache. Nazwy ulic mogą oczywiście zawierać nazwiska patronów — to element adresu, nie pole inwestora.

## Uruchomienie

Z katalogu repozytorium:

```bash
python3 -m venv .cache/venv
.cache/venv/bin/python -m pip install -r requirements-data.txt

# Cała gmina, cały zakres od 2025-01-01 do dnia uruchomienia;
# domyślnie wszystkie poprawne odwołania działkowe, cztery połączenia ULDK.
.cache/venv/bin/python scripts/import_data.py

# Dokładny zakres dat opublikowanego wycinka:
.cache/venv/bin/python scripts/import_data.py --since 2025-01-01 --until 2026-10-02 --max-parcels 0

# Odtworzenie bez sieci: wymaga wcześniej pobranych ZIP-ów i zweryfikowanych odpowiedzi.
.cache/venv/bin/python scripts/import_data.py --offline --until 2026-10-02

# Wymuszone pobranie nowych odpowiedzi, bez zmiany dat filtra:
.cache/venv/bin/python scripts/import_data.py --refresh --until 2026-10-02

# Szybszy wycinek samych obrysów: liczba rekordów nadal pełna, brakujące obrysy jawne.
.cache/venv/bin/python scripts/import_data.py --max-parcels 200

# Testy offline, włącznie z realnymi artefaktami:
PYTHONDONTWRITEBYTECODE=1 .cache/venv/bin/python -m unittest discover -s tests/data -v
```

`--since` i `--until` wymagają dat ISO. `--workers` dopuszcza 1–6, `--max-parcels 0` oznacza wszystkie. Limit obrysów obejmuje najnowsze wpisy najpierw i jest podany w metadanych, nie ogranicza eksportu rekordów. `--output` umożliwia budowę osobnego wycinka bez nadpisania podstawowego katalogu.

### Niezawodność i cache

- Maksymalnie trzy próby na URL. Timeout połączenia/odczytu: ULDK `10/30 s`, archiwa `15/150 s`; krótkie ograniczone opóźnienia między próbami.
- Archiwa mają kontrolę ZIP/CRC, schematu kolumn i SHA-256. Brak wpisów jednej ze źródłowych kategorii lub całkowity brak potwierdzonych geometrii kończy import błędem, zamiast nadpisać poprzedni zestaw pustymi danymi.
- Cache przechowuje tylko poprawnie zweryfikowane odpowiedzi tekstowe. Błędy ULDK nie są trwale cache'owane. ZIP-y są używane do 24 godzin, pozytywne geometrie/PRG do 30 dni; `--refresh` omija cache, `--offline` nigdy nie wywołuje sieci. Czasy rzeczywistego pobrania geometrii są jawne w metadanych.
- Wszystkie trzy artefakty serializuje się i zapisuje do katalogu tymczasowego **przed** publikacją. Na Linuksie używany jest atomowy `renameat2(RENAME_EXCHANGE)` dla całego katalogu. Fallback przenosi katalog z rollbackiem (możliwa krótka niedostępność, ale bez mieszania generacji plików). Wyjątek przed publikacją zachowuje poprzedni zestaw.
- Testy sprawdzają daty, filtr miasto/wieś, separator, deduplikację, statusy, niepoprawne ID, arkusze, Polygon/MultiPolygon, SRID i kolejność osi, pełne/częściowe powiązania, cache/retry oraz zachowanie poprzednich plików po błędzie. Dodatkowo każde z 839 opublikowanych obrysów porównano z rzeczywistą, zapisaną odpowiedzią ULDK.

## Sources

[1] https://wyszukiwarka.gunb.gov.pl/mapa-api
[2] https://wyszukiwarka.gunb.gov.pl/pobranie.html
[3] https://wyszukiwarka.gunb.gov.pl/pliki_pobranie/wynik_mazowieckie.zip
[4] https://wyszukiwarka.gunb.gov.pl/pliki_pobranie/wynik_zgloszenia_2022_up.zip
[5] https://uldk.gugik.gov.pl/opis.html
[6] https://uldk.gugik.gov.pl/?request=GetCommuneById&id=143206_4&result=id%2Ccommune%2Ccounty&srid=4326
[7] https://uldk.gugik.gov.pl/?request=GetCommuneById&id=143206_5&result=id%2Ccommune%2Ccounty&srid=4326

## Publiczna wersja historycznego snapshotu

Przed upublicznieniem repo pola swobodnych tytułów/opisów tego snapshotu zastąpiono deterministycznymi skrótami ze stałego słownika. Daty, identyfikatory, obrysy i sumy pobranych archiwów zachowano. Czas tej migracji prywatności zapisano jako `privacyProcessedAt`; nie oznacza ponownego pobrania danych GUNB.
