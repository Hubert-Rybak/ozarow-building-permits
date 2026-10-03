# P1 Atlas GIS — port produkcyjny i weryfikacja

Wybrany kierunek: **P1 Atlas GIS**, zwycięzca spośród wariantów spełniających hard gates. Szczegóły punktacji, niezależne głosy i bloker P5: [JURY_RESULT.md](JURY_RESULT.md).

## Rozdzielenie ról

- Pięć osobnych agentów przygotowało P1–P5 w izolowanych worktrees z tego samego baseline `20ed307465800256fb1a144e55e154668e202841`.
- Trzech nowych jurorów niezależnie oceniło wszystkie pięć kandydatów.
- Nowy, szósty agent implementacyjny przeniósł P1 do aplikacji; nie był autorem żadnego prototypu ani jurorem.
- Osobny reviewer SPEC zaliczył dokładny, zamrożony port. Następny, niezależny reviewer QUALITY/security zaliczył ten sam kod przed publikacją; oba przeglądy wiążą dokładne SHA-256 źródeł.
- Dodatkowa sugestia QUALITY została sprawdzona rzeczywistą przeglądarką: wszystkie rozwinięte kontrolki filtrów są osiągalne i bez overflow przy wysokości 600 px i szerokościach 720/721/1099/1100/1101/1440 px. Dowody: `implementation/breakpoints.json`.
- Koordynator odpowiada za testy, PR, CI, merge, Pages i sprawdzenie strony. Ten dokument opisuje dowody lokalne; sam nie jest potwierdzeniem deploymentu.

## Zmiany względem zamrożonego P1

- Pomocnicze etykiety mają co najmniej 11 px; mobilne pole wyszukiwania 16 px i minimum 44 px wysokości.
- Faktyczny link „Wpis w źródle” jest wcześnie w inspektorze, przed długimi identyfikatorami działek.
- Zamknięcie × oraz Escape przywracają fokus do właściwej widocznej powierzchni; wybór mobilnego wiersza z geometrią kieruje do mapy, a wpis bez geometrii do listy/szczegółów.
- Pusty inspektor jest krótszy, bez usuwania ostrzeżeń i informacji o źródłach.
- Zwycięska implementacja używa natywnego CSS i nie dodaje zależności. DaisyUI/Tailwind pozostają rzeczywistymi, skompilowanymi eksperymentami w P2/P3, nie zależnościami produkcji.

## Sprawdzone wykonaniem

- **89/89 testów UI**, w tym wszystkie 75 testów bazowych zachowane bajtowo oraz 14 nowych. Port: RED 5 testów → GREEN; poprawki jury również poprzedzone niezaliczonymi regresjami.
- **79/79 testów danych**, **20/20 testów workflow**, TypeScript, production build, kontrakt `dist/` i `git diff --check`: PASS w niezależnym przebiegu koordynatora.
- Publiczne dane, importer, mapowy komponent Leaflet, modele, loader, typy, bazowe testy, zależności oraz workflows niezmienione.
- Rzeczywisty Chromium: **320×700, 390×844, 820×1180, 1440×1000**. Domyślnie 60 wpisów/127 działek, pełny okres 447 wpisów/842 geometrie w tym snapshotcie. CSV zachowuje dokładną kolejność i ID widocznej listy; potwierdzono także filtr częściowej geometrii.
- Pierwszy mobilny canvas mapy: y≈394 przy 320 px, y≈385 przy 390 px. Brak poziomego overflow względem `documentElement.clientWidth`; główne cele dotykowe minimum 44×44 px.
- Działki `143206_4.0004.95/13` i `143206_4.0004.95/14` wpisu `permit:ST-MZ-OZ/WNIOSEK/26523/2026` mają bezpośrednio dotykalne punkty na obu telefonach. Nie wymagają zamknięcia karty ani ręcznego przesuwania mapy.
- Potwierdzono rzeczywiste lista→mapa, wielodziałkowe/partial/unmapped, powtórny wybór tego samego ID, poligon→szczegóły→zamknięcie, fokus/×/Escape, zachowanie instancji Leaflet/kamery/filtrów i reduced motion.
- Celowo wstrzyknięte HTTP 503 przechodzi do błędu z wyłączonym CSV; retry przywraca niezmienione prawdziwe dane. Nie podstawiano sztucznych danych.

Dowody: `implementation/parent-verification.json`, `implementation/source-fingerprints.json` oraz zrzuty w `implementation/`. Dotyczą lokalnego builda; po merge koordynator dodatkowo porównuje live JS/CSS i wszystkie trzy pliki danych z opublikowanym snapshotem oraz ponawia testy prawdziwej strony.

## Ograniczenia

Nie wykonano testów Safari, fizycznych urządzeń ani pełnego audytu czytnika ekranu/WCAG. Kafelki OSM i istniejący natywny popup/autopan Leaflet pozostają zależnościami zewnętrznymi. Liczby dotyczą tego snapshotu, a nie niezmiennej liczby przyszłych wpisów.
