# P5 Pocket Map

## Cel i kompozycja

Explore do szybkiego przeglądania najbliższej okolicy, nie panel narzędzi GIS. Telefon: niewielki nagłówek miejsca, pojedyncze pole wyszukiwania z chipem okresu/filtrów, niskie liczniki, pełna szerokość mapy i stała dolna nawigacja **Mapa / Lista / Filtry**. Bez dużego hero, stale rozłożonych sześciu filtrów, kart KPI czy dodatkowej biblioteki UI. Na desktopie mapa pozostaje główna, obok jest lista wyników; filtry nadal na żądanie.

Rzeczywiste pomiary przy 390×844: mapa zaczyna się na **y=180,875 px**, ma **566 px** wysokości. Baseline przy tej szerokości zaczynał mapę około y=869. Po wyborze wpisu kompaktowa karta jest dokowana nad dolną krawędzią mapy, a nagłówek, wyszukiwanie i dolna nawigacja pozostają na ekranie. Nie zmieniamy Leaflet w statyczny obraz ani nie rysujemy fikcyjnych działek.

## Tokeny

- Tło `#f8f9fb`, powierzchnie białe, tekst `#202c34`, tekst pomocniczy `#677482`, linie `#e3e7ed`.
- Akcent nawigacji/fokusu `#235bce`, powierzchnia aktywna `#edf2ff`.
- Kolory semantyczne geometrii i logika statusów pochodzą z niezmienionego modelu. Kolor decyzji bez wyniku nie oznacza zatwierdzenia.
- Systemowy font `-apple-system / BlinkMacSystemFont / Segoe UI / sans-serif`; usunięto zdalny import fontów. Nagłówki 17–23 px, treść 12–14 px, mobilny input 16 px; najmniejsze etykiety liczników 8 px są wyłącznie pomocnicze.
- Zaokrąglenia 13–18 px dla sterowania, 22 px dla karty; cień `0 8px 30px #253c5b17`.
- Główne akcje ≥44 px; dolne przyciski mają 56 px wysokości. `safe-area-inset-*`, widoczny focus i `prefers-reduced-motion`.
- Podkład OSM jest delikatnie wyciszony filtrem CSS `saturate(.6) contrast(.94) brightness(1.04)`, bez zmiany źródła, danych i atrybucji.

## Przepływy

1. **Start:** mapa, ostatnie trzy miesiące kalendarzowe według daty Europe/Warsaw, granice włącznie. W dniu wykonania: 60 wpisów, 54 z obrysem, 6 bez obrysu, 127 unikalnych działek. Pełny zbiór ma 447 wpisów i 842 obrysy. Nie zmieniano importu ani danych.
2. **Szukaj:** jeden współdzielony stan wyszukiwania/filtrów/sortu dla listy, mapy, liczników i CSV. Dokładne polskie etykiety formularza zachowane. „Wszystkie daty” pokazuje cały zbiór, reset przywraca trzy miesiące.
3. **Filtry:** natywne, początkowo zamknięte `<details>`. Dolna akcja otwiera panel i przenosi focus na „Okres”. Escape zamyka filtry i przywraca focus na dolną akcję. Nie jest to modalny dialog.
4. **Lista → mapa:** wpis z rzeczywistą geometrią przełącza telefon na mapę, zaznacza i kadruje wszystkie dostępne powiązane obrysy. Karta startuje w trybie peek. Ponowny wybór tego samego ID nadal działa; peek ukrywa się przy przejściu na listę, więc nie przechwytuje następnego dotyku.
5. **Inspekcja:** „Pełne informacje i źródło” to natywne disclosure w nie-modalnej regionie `.detail-panel`. Dotknięcie/Enter działki otwiera pełne informacje i focus regionu. Rozwinięcie można zwinąć bez utraty zaznaczenia. Powtórne wybranie tej samej działki ponownie rozwija informacje.
6. **Powrót:** × / Escape usuwa kartę, przywraca mapę/focus na telefonie, nie odmontowuje Leaflet ani nie kasuje filtrów. Mobilny scroll-margin zapobiega niepotrzebnemu skokowi strony pod kartę.
7. **Bez geometrii:** wpis pozostaje w widoku listy, z pełnymi szczegółami i jawnym komunikatem o braku potwierdzonej geometrii. Częściowe dopasowanie zachowuje ostrzeżenie i tylko faktycznie dostępne obrysy.
8. **Źródła:** O danych i ograniczenia są nadal dostępnymi disclosures poniżej mapy; link nagłówka otwiera metodologię. Źródło konkretnego wpisu i każdej działki pozostało w inspekcji. Loading/error/retry, puste wyniki, stan niedostępnego OSM i ostrzeżenia importu zachowane.

## Implementacja i koszt

Zmiany: `src/App.tsx`, `src/ParcelMap.tsx`, `src/styles.css`, `tests/ui/pocket.test.tsx`, `tests/ui/layout.test.ts`, `README.md`. Model, loader, typy, publiczne JSON/GeoJSON, importer i workflows bez zmian. Stabilne selektory mapy/listy/szczegółów oraz etykiety PL pozostają. Brak nowych zależności, fontów sieciowych, portalu modalnego, animacji wejścia lub blokady scrolla.

Koszt utrzymania: mały stan disclosures/selection-request oraz CSS dokowania, z testem powtórnego wyboru. Desktop zachowuje listę obok mapy zamiast osobnej aplikacji. Nowe UI dodaje trzy testy do istniejących 75, bez usuwania lub osłabiania poprzednich asercji. Artefakty kompilacji: około 33,40 kB CSS i 407,38 kB JS przed gzip; nie przeprowadzano benchmarku wydajności.

## Faktyczna weryfikacja

- `npm ci`: zakończone; audit 0 podatności. Polityka npm zablokowała postinstall esbuild, ale build został rzeczywiście wykonany i działa.
- `npm test -- --maxWorkers=1 --pool=threads --testTimeout=30000`: **78/78**. RED → GREEN dla nowych filtrów/peek, pointer-interception przy ponownym wyborze oraz ponownego otwarcia tego samego ID.
- `npm run build`: TypeScript + Vite zakończone.
- `git diff --check`: brak błędów whitespace.
- Prawdziwy Python Playwright + Chromium, `PLAYWRIGHT_BROWSERS_PATH=/opt/data/cache/scratch/ozarow-browser`, rzeczywisty preview 4195, bez mokowania danych i mapy.
- `.cache/verify_list_map.py http://127.0.0.1:4195/ozarow-building-permits/`: PASS dla 390×844, 320×700 i 1440×1000. Zachowane asercje wszystkich powiązanych obrysów, kadrowania, rzeczywistego dotyku działki, dwóch powtórzeń tych samych ID, częściowej geometrii, zamknięcia i instancji mapy. Harness uzupełniono wyłącznie o otwarcie/zamknięcie nowych filtrów i silniejszy pomiar overflow wobec `documentElement.clientWidth`.
- Bez overflow przy 320/390/1440; bez błędów JavaScript i nieudanych HTTP aplikacji. Zewnętrzne kafle OSM są wyłączone z raportu błędów HTTP aplikacji, a screeny wykonano po rzeczywistym załadowaniu kafli.
- Na 390 px rzeczywisty eksport CSV pobrano i sparsowano: **60 rekordów**, zgodnie z bieżącymi wynikami; Escape i focus-return inspekcji/filtrów sprawdzone; główne touch targets pomierzone ≥44×44 px; emulowano reduced-motion.
- `desktop.png` 1440×1000, `mobile.png` 390×844, `mobile-selected.png` 390×844: screenshoty rzeczywistego defaultu i wybranego pierwszego wyniku, obejrzane po wykonaniu.
- Preview uruchamiany przez bounded subprocess z `finally: terminate/wait`; port 4195 po zakończeniu nie nasłuchuje. Brak commitów, pushy i publikacji.

## Koszty i ryzyka / czego nie potwierdzono

- Podkład OSM zależy od sieci i może doładowywać się po zmianie zoomu; istniejący komunikat awarii zostaje. Nie deklarujemy pełnej dostępności offline.
- Karta świadomie zasłania dolną część mapy; można ją natychmiast zwinąć/zamknąć. Wiele odległych działek wymaga szerokiego kadru, a drobne poligony należy przybliżyć; lista jest równoległą dostępną ścieżką.
- Pomocnicze liczniki są mocno skompresowane; do szczegółowego czytania służy lista/inspekcja. Informacje źródłowe przeniesiono poza pierwszy ekran, ale nie usunięto.
- Brak testów Safari, fizycznego telefonu, VoiceOver/NVDA lub formalnego audytu WCAG. Sprawdzono Chromium/touch, natywne sterowanie klawiaturą, focus, Escape i rozmiary celów; nie deklarujemy pełnego audytu dostępności.
- Pierwsze równoległe uruchomienia testów i jeden browser action miały timeout przy współdzielonym obciążeniu hosta. Końcowe serializowane testy i dwa pełne przebiegi browser regression zakończyły się powodzeniem; to nie benchmark.
- Prototyp lokalny. Nie modyfikowano produkcji, innych kandydatów, settings/secrets ani historii Git. Nie rangowano innych propozycji.

## Artefakty i odtworzenie

Wszystkie dowody są w `.cache/design-output/`; `verification.json` łączy rzeczywiste wyniki testów/build/diff-check z `screenshots-verification.json` i `.cache/list-map-local.json`.

```bash
npm ci
npm test -- --maxWorkers=1 --pool=threads --testTimeout=30000
npm run build
python .cache/preview_p5.py
```

Skrypt bounded preview kończy serwer również w razie wyjątku; nie należy pozostawiać osobnego serwera na 4195 podczas jego uruchomienia.
