# P3 · Tailwind Workspace

## Zakres
Samodzielny uruchamialny wariant w `/opt/data/cache/scratch/ozarow-ui-round1/prototype-03`, baza `20ed307`. Wyłącznie warstwa UI, konfiguracja kompilacji, zależności i testy UI. Bez zmian danych, importera, workflow, sekretów, produkcji i innych worktree; bez commitów/push/publikacji.

## Koncepcja i kompozycja
**Explore → Inspect**, nie panel GIS ani zestaw kart statystycznych. Główną powierzchnią jest zwarty warsztat: wyszukiwanie i okres w jednym pasku poleceń, liczniki jako typograficzny ledger na jednej linii, lewa lista wyników, prawa mapa. Dominantą jest rzeczywista przestrzeń mapy, nie hero ani objaśnienia.

Desktop 1440×1000: nagłówek 68 px, tytuł roboczy, pojedynczy pasek wyszukiwania; lewy panel do 380 px, mapa zajmuje resztę. Wybranie wpisu skraca listę do 260 px, a inspektor pojawia się bezpośrednio pod nią. Zachowujemy dwie kolumny — nie dokładamy trzeciego panelu, nie zakrywamy mapy szufladą.

Mobile 390×844: nagłówek 64 px, wyszukiwanie nad rzędem okres/filtry/reset, cztery zwarte liczniki, źródłowy status, jawny pasek ograniczeń i zakładki Mapa/Lista. Mapa zaczyna się na 408,5 px, cała powierzchnia mapy o wysokości 380 px mieści się na pierwszym ekranie. Baseline zaczynał mapę około 869 px od góry. Przy 320×700 widoczne jest 291,5 px mapy bez przewijania. Filtry dodatkowe nie zajmują domyślnie miejsca.

## Tokeny
- Canvas `#f5f4f0` — ciepła neutralna powierzchnia robocza.
- Ink `#17243c` — nagłówki i treść podstawowa.
- Command `#3456db` — sterowanie, fokus, aktywna zakładka i zaznaczony wiersz.
- Rule `#dcdedc` — linie rozdzielające zamiast kart i cieni.
- Muted `#606a79` — tekst pomocniczy; semantyczne kolory mapy zachowane z modelu.
- Systemowy font (`Inter` tylko jeśli lokalnie obecny, następnie Segoe UI/system-ui), brak pobierania fontów.
- Promień: 6 px dla przycisków i 8 px dla paneli, rytm 4/8/12/16/24 px.
- Primary taps minimum 44×44 px; widoczny fokus 3 px, ruch ograniczony przez prefers-reduced-motion.

## Tailwind — realna kompilacja
`tailwindcss@4.3.3` i `@tailwindcss/vite@4.3.3` dokładnie zapisane w package.json/lockfile, instalacja lokalna. Plugin Vite, CSS `@import "tailwindcss"`, tokeny `@theme`, klasy utility w JSX oraz komponenty `@apply` w warstwie components. Produkcyjny CSS ma 46 633 bajty, zawiera utility `.flex`, token `--color-command`; nie zawiera pozostałych dyrektyw `@apply`. Minifier usuwa komentarz wersji, więc wersję potwierdzamy po zainstalowanym pakiecie i lockfile, nie po banerze. Bez daisyUI, CDN CSS i runtime Tailwind.

Oficjalny wzorzec instalacji Vite zweryfikowano w źródle strony Tailwind Labs (`tailwindcss.com` zwrócił HTTP 403; odczyt oficjalnego repozytorium dokumentacji poprzez GitHub API/raw potwierdził plugin i import). Nie użyto zewnętrznych snippetów projektu.

## Przepływy
1. Szukaj / zmień okres: jedna wspólna kolekcja wyników zasila liczniki, listę, mapę i eksport CSV.
2. Filtry: przycisk z aria-expanded/aria-controls otwiera pięć dodatkowych wymiarów (rodzaj, rok, status, miejscowość, geometria). Zmiany obowiązują natychmiast. „Pokaż wyniki” lub Escape zamyka panel bez zerowania wyborów i oddaje fokus przyciskowi. „×” przy wyszukiwaniu usuwa tylko zapytanie i skupia pole. Reset odtwarza zakres 3 miesięcy.
3. Desktop: wybór wiersza zaznacza dokładnie powiązane działki i kadruje mapę, inspektor jest pod listą.
4. Telefon: wiersz z obrysem → Mapa, dokładne zaznaczenie/kadr i przewinięcie do mapy. Ten sam ID można wybrać ponownie. Wiersz bez obrysu → nadal Lista i szczegóły. Działka → szczegóły; zamknięcie → mapa (lub wiersz listy dla wpisu bez geometrii). Instancja mapy i filtry pozostają te same.
5. Ograniczenia zbioru mają stale widoczne rozwinięcie „Decyzja ≠ pozwolenie” i liczbę ostrzeżeń. Pełne źródła/zakres i metodologia są pod „O danych”, a częściowa/brak geometrii pozostają jawne w wierszach i szczegółach.

## Prawdziwe dane i semantyka
Snapshot: 447 rekordów, 842 poligony; domyślnie 60 wyników, 54 z obrysem, 6 bez obrysu, 127 unikalnych działek. Żadnych fikcyjnych trendów, metryk lub rekordów. Zachowany model dat: 3 miesiące kalendarzowe, strefa Europe/Warsaw, oba końce przedziału włącznie; data decyzji albo wniosku, wszystkie daty/reset niezmienione. Decyzja odnotowana w CSV nie staje się „pozwoleniem”; jej wynik nadal jest nieokreślony, jeśli brak rozstrzygnięcia w źródle.

## Weryfikacja
- Bazowe 75 testów zachowane bez osłabiania; cztery nowe testy najpierw RED (brak filtrów/clear/Tailwind), potem GREEN.
- 79/79 testów UI, 7 plików; `npm test -- --maxWorkers=1`.
- `npm run build`: TypeScript i Vite PASS, 36 modułów; `git diff --check` PASS.
- Niezmieniony `.cache/verify_list_map.py` uruchomiony na porcie 4193: PASS dla 390, 320 i 1440 px. Pełne/częściowe/wielodziałkowe obrysy, powtórzenie ID, rzeczywisty tap poligonu, wpis bez obrysu, reset, zachowanie filtrów i DOM mapy.
- Dodatkowe Chromium: brak overflow względem documentElement.clientWidth w stanach początkowym/filtrów/listy/wyboru; 60 wierszy CSV; klawiaturowe Escape/fokus; rzeczywiste minimum 44×44; realne liczniki; brak błędów JS i błędów HTTP aplikacji.
- Zrzuty `desktop.png`, `mobile.png`, `mobile-selected.png` oraz dodatkowe `desktop-selected.png`, `mobile-filters.png`; kontrola wizualna wykonana.
- Preview uruchamiany w ograniczonym subprocess i zakończony po kontroli.

## Koszty i ryzyka
- Dodano 12 lokalnych pakietów buildowych poprzez Tailwind; runtime aplikacji nie zyskał nowej biblioteki JS. Produkcyjny JS 406,67 kB / gzip 124,61 kB; CSS 46,63 kB / gzip 12,81 kB (razem ze stylem Leaflet). Statyczne dane nadal stanowią główny koszt pobrania; nie modyfikowano ich.
- Zewnętrzne kafelki OSM zależą od sieci i dostawcy. Geometria/lista nie zależą od dostępności podkładu; zachowano komunikat awarii kafelków. Anulowane żądania przy kadrowaniu nie są kwalifikowane jako awarie usług.
- Na małym ekranie inspektor pozostaje pod mapą, więc pełne dane wymagają przewijania. To świadomy koszt utrzymania dokładnego kadru bez zasłaniania mapy.
- Gęsty ledger używa małych opisów pomocniczych (9–11 px), ale dane główne i interakcje są większe. Nie wykonano formalnego audytu WCAG ani testów Safari/Firefox/czytnika ekranu.
- Pojedynczy timeout procesu Vitest i pojedynczy timeout kliknięcia Chromium były przejściowe; pełne późniejsze uruchomienia przeszły. Błąd selektora exact-label w dodatkowym harnessie naprawiono po wykazaniu, że tekst label zawiera opcje select; kod UI nie wymagał zmiany. Nie pominięto żadnych asercji funkcjonalnych.
- Brak wdrożenia produkcyjnego i commitów; raport dotyczy wyłącznie tego worktree.
