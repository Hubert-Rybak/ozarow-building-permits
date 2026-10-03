# P4 Register — Explore jako czytelny rejestr

## Cel i kompozycja

Priorytetem jest porównywanie rzeczywistych wpisów, a nie dekoracyjny dashboard. Desktop 1440×1000: rejestr zajmuje około 970 px, prawa kolumna kontekstowa 390 px. Trzy stałe kolumny: **Data / rodzaj**, **Inwestycja / lokalizacja**, **Działki / położenie**. Data ma cyfry tabelaryczne, tytuły pozostają pełne bez dwuwierszowego obcięcia, miejscowości mają stałą linię odniesienia. Obrys i jego brak są podpisane, nie tylko zakodowane kolorem. Cały wiersz jest przyciskiem.

Mapa jest pomocnicza: 320 px wysokości bez wyboru, 220 px po wyborze na desktopie, 360 px na telefonie. Wybrany wiersz ma oliwkową powierzchnię i gliniany akcent; dokładne powiązane obrysy mają ciemną krawędź. Panel szczegółów jest pod mapą, z widocznym na pierwszym ekranie desktopu działaniem **Wpis w źródle**. Reszta dowodów jest przewijana w panelu: semantyka wpisu, daty, adres, numery i identyfikatory działek, źródła geometrii.

Nie ma wykresów, fikcyjnych trendów, porównań ani dodatkowych wskaźników. Cztery liczniki są skromnym wierszem informacji wyliczanych z tych samych wyników.

## Kontrole

- Wyszukiwanie, okres i rodzaj wpisu stale widoczne.
- Rok, status źródłowy, miejscowość i geometria w natywnym, domyślnie zamkniętym `details` **Filtry szczegółowe**.
- Podpis disclosure pokazuje liczbę aktywnych dodatkowych wymiarów, również po jego zamknięciu.
- Reset jest stale dostępny, przywraca istniejące domyślne ostatnie 3 miesiące.
- Sortowanie i eksport są przy rejestrze. CSV zachowuje kolejność oraz dokładne ID widocznej listy.
- Źródła i ograniczenia pozostają dostępne. Na telefonie ostrzeżenia zbioru są pod powierzchnią roboczą: użytkownik nie traci pierwszego ekranu mapy, nie usuwa się żadnego ostrzeżenia. Krytyczny błąd wczytania nadal jest nad widokiem.

## Przepływy i zachowany kontrakt

1. **Desktop lista → kontekst:** klik lub Enter na wierszu wybiera wpis, ramuje powiązane działki i pokazuje szczegóły pod mapą; lista zachowuje szerokość.
2. **Mobile start:** zachowany domyślny widok mapy. Rzeczywisty początek mapy: 527.09 px przy 390×844; 558.09 px przy 320×700. Dla porównania dostarczony obraz bazowy miał początek mapy około 869 px. Są to pomiary layoutu, nie wskaźniki danych.
3. **Mobile mapowany wiersz → mapa:** przełączenie zakładki i przewinięcie do mapy, wyróżnienie dokładnych dostępnych powiązanych obrysów, również przy ponownym wyborze tego samego ID. To istniejąca logika, nie nowy wariant uproszczony.
4. **Polygon → szczegóły:** dotknięcie działki otwiera szczegóły wybranego wpisu; zamknięcie przywraca użyteczną mapę. Instancja Leaflet i filtry są zachowane.
5. **Bez obrysu:** wybór pozostaje na liście i pokazuje szczegóły z jawnym brakiem geometrii. Częściowy obrys pozostaje częściowy, nie staje się pełnym dopasowaniem.
6. **Brak wyników / ładowanie / błąd:** istniejące rozróżnienia, komunikaty i ponowienie są zachowane; niedostępności nie interpretuje się jako braku inwestycji.

Zachowane hooki: `.map-panel`, `.leaflet-map`, `.result-row`, `data-record-id`, `.workspace`, `view-map`, `view-list`, `.detail-panel`, etykiety i dostępne nazwy w języku polskim.

## Prawda danych

Pliki `public/data/` nie były modyfikowane. Zbiór rzeczywisty: 447 wpisów, 842 obrysy. W dniu wykonania 2026-10-03 domyślny okres daje 60 wpisów, 54 z obrysem, 6 bez obrysu, 127 unikalnych działek. Wyniki zależą od daty, nie zostały zaszyte w interfejsie. Logika okresu i strefy Europe/Warsaw pozostaje bez zmian: trzy miesiące kalendarzowe, obie granice włącznie; data decyzji, a przy braku data wniosku. Wszystkie daty i reset pozostają dostępne.

Decyzja nie staje się pozwoleniem. Zgłoszenie nie jest decyzją o pozwoleniu. Brak samodzielnych wniosków jest luką eksportu, nie zerową liczbą oczekujących wniosków. Obrysy to działki, nie budynki ani postęp prac. Szczegóły nie zawierają danych inwestorów lub projektantów. Nie dodano żadnych danych demonstracyjnych do aplikacji.

## Tokeny wizualne

| Token | Wartość / zastosowanie |
|---|---|
| Tło | `#f5f2eb` — ciepły papier |
| Powierzchnia | `#fffefb` — rejestr i dowody |
| Tekst główny | `#282e2a` |
| Tekst pomocniczy | `#64675f` |
| Linie | `#d8d5cb` |
| Akcent | `#814d34` — glina, wybór i focus |
| Akcja / geometria | `#3d5e4d` — oliwka |
| Nagłówki | lokalna Georgia / Times New Roman, bez pobierania fontów |
| Treść | Arial / Helvetica / sans-serif |
| Tytuł desktop/mobile | 34 / 28 px |
| Wiersz | tytuł 15 px, lokalizacja 13 px, data 14 px desktop |
| Geometria przestrzeni | radius 2–3 px, reguły zamiast cieni |
| Dostępność | główne cele ≥44 px, focus 3 px, reduced motion |

Native CSS, bez nowego frameworka, bez nowych zależności. Usunięto zewnętrzny import Google Fonts.

## Implementacja i koszt

Zmiany aplikacji ograniczono do `src/App.tsx` i `src/styles.css`. `src/ParcelMap.tsx`, `model.ts`, `types.ts`, `data.ts` pozostają niezmienione. Dopisano `tests/ui/register.test.tsx` i sekcję uruchomieniową README. Dane, importer, workflow, konfiguracje, sekrety i inne worktree nie były zmieniane.

Szacowany koszt przeniesienia do uzgodnionego wariantu produkcyjnego: **1–2 dni pracy frontendowej i QA**; to szacunek, nie pomiar. Nie potrzeba migracji danych. Największy koszt to sprawdzenie layoutu po wymianie arkusza CSS oraz odbioru na fizycznych urządzeniach i czytnikach ekranu.

## Zweryfikowane dowody

- `npm ci`: zakończone; audyt 0 podatności. Ostrzeżenie środowiska o zablokowanym skrypcie instalacyjnym esbuild nie zablokowało realnego builda.
- TDD: trzy nowe testy najpierw zawiodły dla brakującego disclosure, kontekstu kolumn/source ordering i list-first; dodatkowo wykryto cel wejścia wyszukiwania 42 px i podniesiono go do 44 px wewnątrz kontenera 46 px.
- 75 istniejących testów bez zmiany asercji; komplet **78/78**, 7 plików. Log: `tests.log`.
- TypeScript i Vite produkcyjny build: sukces. Log: `build.log`.
- `git diff --check`: sukces.
- `.cache/verify_list_map.py` na dokładnym porcie 4194: sukces po końcowym buildzie; realne touch/Chromium przy 390, 320 i 1440 px, pełne/częściowe/wielodziałkowe i powtarzane wybory, polygon→detail→close, unmapped, zachowanie mapy i filtrów. Log: `list-map-run.log`.
- Dodatkowa weryfikacja: 72 asercje; każdy wymiar filtru, szukanie i sortowanie synchronizują ID listy, obrysy, liczniki oraz pobrany CSV. Brak overflow względem `documentElement.clientWidth` dla 320/390/1440, zamkniętych/otwartych dodatkowych filtrów i wyboru. Keyboard, outline, reduced-motion, źródła i cele 44 px sprawdzone w rzeczywistym Chromium.
- Końcowe wykonanie: brak page errors, brak console errors, brak niezakończonych requestów. Preview uruchomione jako ograniczony subprocess i zakończone przez `finally`; nie pozostawiono serwera 4194.
- Obrazy obejrzane faktycznie: desktop/default, mobile/default, mobile/list, desktop/selected, mobile/selected i mobile/detail. Końcowy source action jest widoczny przy wybranym wpisie; wszystkie dostępne 7 działek przykładowego rzeczywistego zgłoszenia są wyróżnione.

## Artefakty i odtworzenie

Wszystkie w `.cache/design-output/`: wymagane `SPEC.md`, `verification.json`, `desktop.png` (1440×1000), `mobile.png` (390×844), `mobile-selected.png` (390×844). Dodatkowo `mobile-list.png`, `mobile-detail.png`, `desktop-selected.png`, logi oraz szczegółowy `browser-verification.json`.

```sh
npm ci
npm test -- --maxWorkers=1
npm run build
PLAYWRIGHT_BROWSERS_PATH=/opt/data/cache/scratch/ozarow-browser python .cache/verify_register.py
```

Skrypt uruchamia preview na `127.0.0.1:4194`, sprawdza rzeczywisty prefiks `/ozarow-building-permits/`, wykonuje istniejący regression script i zamyka serwer nawet po asercji.

## Ryzyka i granice

- Mapa 220 px przy wyborze desktopowym jest świadomym kompromisem: kontekst, nie główny GIS; przy wielkich/długich parcelach może być mniej czytelna niż mapa pełnoekranowa. Mobile pozostaje 360 px.
- Mobile 320×700: mapa rozpoczyna się na pierwszym ekranie, ale początkowo widoczny jest tylko jej górny fragment; cały widok jest dostępny po krótkim scrollu. Wybór wiersza automatycznie pokazuje pełną mapę.
- Filtry za disclosure i ograniczenia pod mapą są mniej natychmiastowe; dostępne i jawnie podpisane, nie usunięte.
- Map tiles OSM zależą od sieci. Pośrednie próby testów miały timeout `networkidle`; końcowy test był w pełni udany. Dodatkowy runner rozdziela gotowość rzeczywistych danych od opcjonalnego ustalenia żądań kafelków. Nie podmieniano kafelków ani JSON atrapami.
- Brak pełnego audytu kontrastu WCAG/czytnika ekranu oraz testów na fizycznym telefonie. Keyboard i wymiary celów sprawdzone, ale nie są pełnym audytem dostępności.
- Zero commitów, pushów, publikacji ani zmian innych kandydatów. Ten wariant nie jest rankingiem pozostałych.
