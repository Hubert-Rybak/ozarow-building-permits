# P1 — Atlas GIS

## Wynik i zakres

Lokalny, uruchamialny prototyp React/TypeScript/Vite/Leaflet, bez dodatkowego frameworka i bez publikacji. Worktree: `/opt/data/cache/scratch/ozarow-ui-round1/prototype-01`, punkt wyjścia `20ed307465800256fb1a144e55e154668e202841`. Zmieniono wyłącznie UI, testy UI, konfigurację testów i README. Nie zmieniono importerów, źródłowych JSON/GeoJSON, workflow ani ustawień produkcji.

Rzeczywisty snapshot: **447 wpisów / 842 geometrie**. Dla domyślnych ostatnich trzech miesięcy kalendarzowych w Europe/Warsaw: **60 wpisów, 54 z obrysem, 6 bez obrysu, 127 unikalnych działek**. Wartości pochodzą z załadowanego zbioru, nie z dekoracyjnych statystyk.

## Kompozycja — Explore/GIS, nie formularz nad mapą

- Ciemny, 68-pikselowy pasek Atlas identyfikuje narzędzie i gminę. Bez marketingowego hero.
- Zawsze widoczny pasek źródła: link GUNB/RWDZ, rzeczywiste liczby całego zbioru i data importu. Ograniczenia mają własne dostępne rozwinięcie; nie usunięto żadnego ostrzeżenia.
- Desktop: jedna przestrzeń robocza, od lewej **rail narzędzi/wyników 308 px**, elastyczna mapa i **kontekstowy inspektor 264 px** (304 px po wyborze). Przy 1440×1000 mapa ma 816 px szerokości i pozostaje równocześnie widoczna z wynikami. Lista oraz inspektor przewijają się niezależnie.
- Stan inspektora przed wyborem wyjaśnia następny krok i ograniczenia mapy. Po wyborze pokazuje istniejące dane wpisu, wynik semantyczny, geometrię i odsyłacze źródłowe.
- Telefon: kompaktowe wyszukiwanie, reset, okres, rozwinięcie „Filtry”, cztery liczniki i zakładki Mapa/Lista. Pięć drugorzędnych filtrów jest zwiniętych, ale zachowuje wartości i nie odmontowuje mapy.
- Przy 390×844 panel mapy zaczyna się na **y=339,17**, rzeczywisty canvas Leaflet na **y=375,17**. Baseline: mapa zaczynała się około y=869. Przy 320×700 canvas zaczyna się na y=393,56. Mapa jest dostępna na pierwszym ekranie obu telefonów.
- Powrót z listy przewija do wybranego obszaru mapy, zamiast ponownie prezentować formularz. Szczegóły na telefonie są poniżej mapy; kliknięcie działki przewija bezpośrednio do nich.

## Tokeny i środki wizualne

| Token | Wartość / użycie |
|---|---|
| Ink | `#1c2b39`, masthead i podstawowa typografia |
| Accent | `#155cc3`, wybór zakładki, wynik, odsyłacze |
| Line | `#dce2e8`, granice powierzchni i struktura |
| Soft | `#eef4fc`, wybrany wpis i powierzchnie pomocnicze |
| Surface | biel; podłoże `#edf0f2` |
| Radius | 5–6 px; geometria narzędzia, nie kafelki marketingowe |
| Typografia | lokalny stos Inter/system-ui; brak pobierania webfontów |
| Skala | nagłówki 17–23 px, wiersze 12–13 px, metadane 9–11 px |
| Rytm | odstępy 6/8/10/12/16/20 px, ramki 1 px |

Kolory warstw zachowują dotychczasowe semantyczne znaczenie; „Decyzja” nie jest etykietą pozytywnego pozwolenia. Wybrany obrys ma mocniejszy kontur. Rysunek pustego inspektora jest lokalnym SVG, nie ikoną zależną od dostępności glifu/fontu.

## Zachowane i sprawdzone przepływy

1. Wspólne filtrowanie mapy, wyników, liczników i CSV; wyszukiwanie, okres, rodzaj, rok, status źródłowy, miejscowość, pokrycie geometrią i sortowanie pozostają dostępne.
2. „Wszystkie daty” pokazuje 447 rekordów. Reset przywraca ostatnie trzy miesiące, a nie pusty lub pełny zbiór.
3. Telefon, wpis z geometrią: Lista → wybór → Mapa, dokładnie wszystkie powiązane działki wyróżnione i mieszczące się w canvasie. Kolejne wybranie tego samego ID ponawia przepływ.
4. Działka → szczegóły, zamknięcie → mapa. Instancja Leaflet i wartości filtrów są zachowane. Dla wpisu bez geometrii wybór pozostaje w liście/szczegółach.
5. Dopasowanie częściowe jest jawnie opisane i filtrowalne. Nie zamieniono brakujących geometrii na fałszywe punkty.
6. Mobilny fokus przechodzi do kontrolki mapy albo panelu szczegółów, nie zostaje na ukrytym wierszu. Escape zamyka inspektor i odtwarza fokus właściwej powierzchni. Dostępne są skip-link, polskie etykiety, klawiaturowy wybór działek i reduced motion.
7. Podstawowe przyciski, selecty, zamykanie, legenda, zoom, reset, eksport i rozwinięcia mają co najmniej 44 px wysokości. Brak pułapki fokusu.
8. Zachowano loading, błąd, retry, brak wyników, pusty zbiór, niedostępny podkład i ostrzeżenia o niedostępnej geometrii. W przeglądarce wymuszono HTTP 503 dla permits.json i potwierdzono, że retry wraca do rzeczywistych 60 rekordów.

## Weryfikacja

Nowe testy powstały przed zmianami: cztery czerwone kontrakty Atlas, następnie dodatkowy czerwony test mobilnego fokusu. Oryginalne 75 testów UI i ich asercje pozostały nietknięte.

- `npm test`: **80/80**, 7 plików, ostatni przebieg 21,30 s.
- `npm run build`: poprawny TypeScript i produkcyjny Vite build; 36 modułów. Wyniki: `index-DwvaXOrR.css`, `index-CXLRdE68.js`.
- `git diff --check`: exit 0.
- `python .cache/verify_atlas.py`: exit 0. Bounded preview 4191 uruchamia się tylko w czasie testu i jest zatrzymywany wraz z grupą procesów.
- Nie zmieniony `.cache/verify_list_map.py` wykonano pod `http://127.0.0.1:4191/ozarow-building-permits/`: przejścia 390/320/1440, powtarzane wybory, matched/partial, wielodziałkowe wpisy, dokładne ID i ramkowanie, polygon→details, unmapped, reset i zachowanie instancji. Dwa końcowe przebiegi zakończyły się sukcesem.
- Overflow sprawdzono względem `document.documentElement.clientWidth`, nie `innerWidth`: 1440/1440, 390/390, 320/320. Także po wyborze brak poziomego overflow.
- Brak błędów JavaScript i błędnych odpowiedzi aplikacji w pomyślnych przebiegach. Podkład OSM faktycznie załadował 16/6/4 kafelki odpowiednio dla desktop/390/320.
- Zrzuty mają dokładny viewport, nie full-page: `desktop.png` 1440×1000; `mobile.png` i `mobile-selected.png` 390×844. Dodatkowo `desktop-selected.png` 1440×1000. Rendered obrazy obejrzano wizualnie.

Szczegółowe pomiary, ID rzeczywistych rekordów i wyniki interakcji znajdują się w `verification.json`; stdout oryginalnej regresji w `list-map-stdout.txt`.

## Ryzyka i zastrzeżenia

- Podkład OpenStreetMap jest zewnętrzną zależnością. Pierwszy wcześniejszy zrzut desktop powstał przed załadowaniem kafelków; finalna procedura czeka na ich dostępność i finalne zdjęcie ma rzeczywisty podkład. Lista i obrysy nadal działają bez kafelków.
- Współdzielony host powodował timeouty testów przy równoległych workerach. Vitest w tym worktree uruchamia pliki szeregowo, z jednym workerem i limitem 15 s; nie zmieniono asercji. Końcowy wynik 80/80.
- Jeden wcześniejszy przebieg list-map miał timeout lokalizatora podczas przejść touch; nie odtworzono go w diagnostycznym przebiegu ani w dwóch późniejszych wykonaniach oryginalnego skryptu. Nie zastępowano danych ani nie osłabiano skryptu. Warto monitorować flakiness na przeciążonym hoście.
- Zwinięte filtry celowo wymagają dodatkowego dotknięcia; active-count informuje o filtrach innych niż domyślne. Mobilny reset używa ikony z zachowaną etykietą „Wyczyść filtry”.
- Metadane są celowo zwarte. Telefon 320 px ma więcej zawijania liczników niż 390 px. Dane nie są ukrywane przez page-level overflow clipping.
- Sprawdzono Chromium desktop/touch, nie Safari, czytnik ekranu ani fizyczne urządzenia. Breakpoint 721–1100 ma układ dwukolumnowy i inspektor pod spodem, ale nie był osobnym viewportem acceptance.
- Artefakty w `.cache/` są lokalne i ignorowane przez git. Prototyp nie jest opublikowany; preview po testach nie działa. Brak commitów/pushów.

## Uruchomienie

```bash
cd /opt/data/cache/scratch/ozarow-ui-round1/prototype-01
npm ci
npm test
npm run build
npm run preview -- --host 127.0.0.1 --port 4191 --strictPort
# URL: http://127.0.0.1:4191/ozarow-building-permits/
```

Powtarzalna, ograniczona czasowo weryfikacja z automatycznym zamknięciem preview:

```bash
PLAYWRIGHT_BROWSERS_PATH=/opt/data/cache/scratch/ozarow-browser python .cache/verify_atlas.py
```
