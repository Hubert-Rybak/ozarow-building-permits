# Publiczne wzbogacenie inwestycji — adapter `public`

## Wynik rzeczywistego pobrania

Zweryfikowano **3 października 2026 r.**, ostatnie uruchomienie rozpoczęte o **12:41:14 UTC**. Bez publikacji, commitów, zmian UI, importera i workflow. `collect(cache: Path, prior: dict | None = None)` zwraca wkład `records/sources/warnings`; `prior` może być pełnym InvestmentDataset. Każdy rekord ma wszystkie wymagane klucze kontraktu.

| Źródło | Pokrycie | Rekordy |
|---|---|---:|
| `budget` | 7/7 artykułów menu 23685; pełna zastępująca tabela 2a, strony 10–15 PDF 203516 | 119 |
| `wpf` | 7/7 artykułów menu 23686; wszystkie przedsięwzięcia majątkowe, obie połowy tabeli, strony 12–19 PDF 203514 | 46 |
| `procurement` | 50 odkrytych kart/menu rocznika 2026, 51 artykułów; 39 tożsamości eZamówień, 105 opublikowanych dokumentów API; 11 kart tylko BIP | 50 |
| `bo` | 30/30 kart i 30/30 wyników, 29 wybranych, 1 niezakwalifikowany | 30 |
| `municipal-news` | 352/352 wpisów WordPress 2026 w 4 stronach; jawny filtr tytułów infrastruktury/zamówień po odrzuceniu sprzedaży i rekrutacji | 59 |
| **Razem** | Rekordy źródłowe, nie liczba unikalnych budów | **304** |

BO: 16 rekordów z geometrią, **23 punkty** w 16 Feature (Point/MultiPoint), 14 bez geometrii. Wyłącznie `input#markers` z kart, kolejność wejściowa lat,lon odwracana do GeoJSON lon,lat. Nigdy `city_lat/city_lng`. Edycja/wybór **2026**, wykonanie **2027**, potwierdzone świeżo odkrytym PDF wyników BIP 203094. Dwanaście kart oznaczono jako działania społeczne / nie budowa; pozostałe również pozostają propozycjami/wybranymi projektami, nie wykonanymi robotami.

## Finanse i pochodzenie

`fetchedAt` pochodzi wyłącznie z oryginalnego receipt HTTP w `public-http/ledger.json`, nigdy z rozpoczęcia adaptera. Dla źródła jest to maksimum receiptów wszystkich użytych odpowiedzi, również odkrywania/paginacji i trafień memo (memo nie tworzy nowego receipt). Dla rekordu: finanse — maksimum przyjętego PDF oraz szczegółów uchwały bieżącej i pierwotnej; zamówienia — maksimum GetTender, GetTenderDocuments, szczegółów powiązanych artykułów BIP i odczytanego PDF oferty, jeśli użyty; BO — maksimum karty, wyników i PDF/szczegółów publikacji dowodzącej roku realizacji; aktualności — receipt strony WordPress zawierającej dany wpis. Geometrie BO zachowują wyłącznie receipt swojej karty, niezależnie od daty odczytu wyników. Brak receipt jest błędem, nie zastępowany zegarem zadania.

Najnowsze przyjęte uchwały: **XXX/280/26 i XXX/279/26, 24.09.2026**, opublikowane 29.09.2026. Załączniki wybierane z faktycznych metadanych artykułów, nie z odgadniętego ID. Każdy rekord linkuje uchwałę, załącznik, stronę/wiersz i dokument pierwotny (budżet 201247; WPF 201244). Projekty uchwał są pomijane. Dodatkowo pełna lista 213 zarządzeń burmistrza z menu 23689: 8 zmian budżetu, żadna nowsza od uchwały wrześniowej.

* Budżet: suma wszystkich 119 wierszy końcowej kolumny `Po zmianie` = **58 525 698,97 PLN**; sprawdzono też sumy rozdziałów. Kwoty są `annual-plan`, nie przyrostami ani wykonaniem.
* WPF: suma 46 majątkowych przedsięwzięć = **168 560 681,59 PLN** nakładów wieloletnich. Roczne limity: 2026 **39 883 527,39**, 2027 **62 584 681,99**, 2028 **34 098 107,55**, 2029 **25 636 104,00**; 2030–2034 jawne zera źródłowe. Limit zobowiązań **118 804 931,49 PLN** podawany osobno w facts, nie jako umowa. Każdy limit i suma porównywane z wierszem `1.b`.
* Powtarzające się nazwy w finansowaniu (np. PSZOK, Cyberbezpieczny Samorząd) pozostają osobnymi wierszami źródłowymi. Budżetu, WPF i innych źródeł nie wolno sumować razem.
* Parser PyMuPDF używa `find_tables(strategy='lines_strict')`. Zwykła strategia `lines` dzieli fizyczne wiersze i niszczy nazwy. Pierwszy nagłówek WPF zawiera dodatkowy tekst daty; rok limitu odczytuje się z właściwej kolumny, nie z całego nagłówka dokumentu.

## Zamówienia i wiadomości

ID odkrywane z rzeczywistych publikacji BIP, PDF i ich hiperłączy oraz Office DOCX/ODT (XML i relacje ZIP; stdlib). Wszystkie opublikowane, nieusunięte dokumenty API i załączniki BIP mają linki w events/facts; dokumentacja chroniona/ZIP nie jest mirrorowana. `isValid` terminów i `Published/deleteDate` dokumentów są respektowane.

GetTender nie udostępnia potwierdzonego timestampu edycji: `sourceUpdatedAt` postępowania pozostaje `null`. `initiationDate` jest datą wszczęcia (w `dates`, a w `statusAsOf` tylko przy `Initiated`), nie edycją. Późniejszy `publishedDate` dokumentu ani pierwotna publikacja BIP również nie są datą edycji postępowania; agregacja metadanych źródła nie propaguje dat wszczęcia.

Kapucka: **4 950 000 PLN** to finansowanie przetargu; **4 193 070 PLN brutto** to wybrana oferta INSTALNIKA, odczytana z faktycznie pobranego PDF wyboru. Od teraz dotyczy to każdego postępowania: `tender_results.py` czyta najnowszą „Informację o wyborze oferty” (o ile po niej nie opublikowano unieważnienia) i pierwszą „Informację z otwarcia ofert”; wykonawca, cena brutto per część, planowana data umowy i kwota przeznaczona per część trafiają do rekordu tylko przy jednoznacznym brzmieniu. Inaczej dokument zostaje linkiem, a źródło notuje to w ostrzeżeniu — nieczytelny PDF nigdy nie zatrzymuje adaptera. `Agreement/CompletedContract` to etap zamówienia, **nie ukończenie budowy**. Konflikt cancellationDate obok Agreement jest ostrzeżeniem, nie automatycznym unieważnieniem. Wiadomość gminy z **1.10.2026** stanowi odrębny dowód umowy; wrzesień 2027 zapisano jako miesiąc w facts, bez sztucznej daty dziennej.

Świeże wiadomości z **2.10.2026**: zakończony skatepark Płochocin, ogłoszony przetarg Umiastów (9 miesięcy od umowy), zapowiedziana droga **powiatowa 4120W** ze startem **5.10.2026**, czyli przyszłym na dzień weryfikacji. Wiadomości nie nadpisują statusów innych adapterów. Brak fuzzy join; relatedIds pozostają puste, gdy nie wykazano literalnej tożsamości.

## Granice pokrycia i codzienne wykonanie

* Pełne odkryte menu/karty BIP 2026 nie oznaczają pełnego eksportu wszystkich zamówień gminy poza BIP. Bez ID zachowano menu: 23706, 23817, 23730, 23737, 23738, 23739, 23740, 23741, 23742, 23757, 23758. Nie wywnioskowano CPV ani niezweryfikowanych cen umów/ofert z dowolnych kwot w dokumentach; dokumenty pozostają dostępne przez linki.
* Filtr tytułów aktualności może pominąć tekst o inwestycji z nieinformacyjnym tytułem. Poza czterema szczegółowo rozpoznanymi komunikatami status/inwestor nie są zgadywane. Źródło wydawcy nie oznacza inwestora gminnego.
* Nie odtwarzano działek, tras i obrysów z nazw ulic. Rekordy bez geometrii nie są usuwane.
* Wszystkie dostarczone źródła mają stan `fresh` z realnego HTTP. Nie użyto browsera, CAPTCHA ani niepublicznych API; codzienny CI nie wymaga headless browsera. Parser obsługuje zweryfikowany układ tabel; zmiana układu lub niekompletny dokument daje błąd, nie przykładowe wiersze udające komplet.
* Roczniki finansów i zamówień odkrywane z bieżącego drzewa BIP. Kontrola zarządzeń jest jawnie przypięta do menu **2026**; przejście roku wymaga ponownego odkrycia menu. BO jest świadomie adapterem edycji **2026**. Nie udaje odświeżenia przyszłej edycji.
* Maks. 3 próby HTTP, timeouty, brak podmiany błędu na stary plik oznaczony fresh. Błąd, duplikaty, ucięcie, niezgodna suma, uszkodzony schemat lub utrata ponad 20% zachowują poprzednie rekordy danego źródła ze stanem `retained`, poprzednim fetchedAt i ostrzeżeniem; bez prior stan `unavailable`.
* Raw/cache pozostają poza payloadem publikowanym. Tylko fakty, tytuły, metadane liczbowe/datowe i własne krótkie podsumowania; bez opisów autorów BO, zdjęć, technicznych kont edytorów i mirrorowanych dokumentów.

## Uruchomienie i dowody

Sprawdzone wersje runtime: **requests 2.34.2, beautifulsoup4 4.14.3, PyMuPDF 1.28.2**; Python 3.10+. Pipeline powinien dodać te zależności swoim własnym mechanizmem. Badawcze PyMuPDF użyto poprzez PYTHONPATH do lokalnego pylibs; nie jest to wymóg docelowego CI.

```sh
python -m unittest discover -s tests/investments -p 'test_public*.py' -v
python -m scripts.investment_sources.public --cache .cache
# Następne pobranie / pełny InvestmentDataset prior:
python -m scripts.investment_sources.public --cache .cache --prior .cache/public-contribution.json
```

TDD: początkowy RED 10 brakujących funkcjonalności, kolejne regresje RED/GREEN; **17 testów przechodzi**, compileall przechodzi. Uwaga: unittest discover od samego `tests/` bez pakietowych init nie odkrywa tego podkatalogu; użyć powyższego polecenia lub pytest integratora.

Artefakty niepublikowane: `.cache/public-contribution.json`, `.cache/public-coverage.json`, `.cache/public-validation.json`, `.cache/public-http/ledger.json` (297 rzeczywistych żądań ostatniego pełnego pobrania, URL/czas/rozmiar/SHA-256). Weryfikacja: 304 unikalne ID, wymagane klucze, spójne source.recordCount, URL/date/cost, 490 events. Fixtures zawierają wyłącznie tabele/metadane i fragmenty BO bez opisów autorów; nie PDF ani fotografie.
