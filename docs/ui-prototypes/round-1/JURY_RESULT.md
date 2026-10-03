# Wynik niezależnego jury UI/UX

**Wybrany do wdrożenia: P1 Atlas GIS — 8,23/10.**

Trzech nowych jurorów oceniło wszystkich pięciu kandydatów (15 ocen wariantów). Każdy stosował tę samą punktację: mobile35%, hierarchia20%, dostępność20%, wygląd15%, niezawodność10%. Wynik to średnia ważona obliczona wPython, nie ręcznie dobrana rekomendacja.

## Ranking i eligibility

- **P5: 8.29/10** — **wykluczony z wdrożenia w tej wersji: potwierdzony bloker**
- **P1: 8.23/10** — spełnia hard gates
- **P3: 8.05/10** — spełnia hard gates
- **P2: 7.59/10** — spełnia hard gates
- **P4: 7.47/10** — spełnia hard gates

P5 dostał nieco wyższą ocenę wyglądu/UX i był preferowany przez dwóch jurorów. Jednak J1 odtworzył na320×700 kartę peek całkowicie zasłaniającą obie wybrane działki pierwszego domyślnego wyniku. Parent niezależnie powtórzył problem w dwóch cyklach: oba obrysy miały0 dostępnych punktów dotykowych przy próbkowaniu wnętrza. FitBounds do całej mapy nie wystarcza, jeśli karta zasłania jej używalny obszar. Dowody: `jury/P5-blocker-parent.json` i screenshot. Zgodnie z zamrożoną regułą potwierdzony niespełniony hard gate wyklucza wariant do czasu poprawki/ponownej oceny; najwyżej punktowany kwalifikujący się wariant toP1. Nie twierdzimy, że wszyscy jurorzy wskazali tego samego faworyta.

## Poprawki P1 przed produkcją

- Powiększyć pomocnicze etykiety/liczniki i czytelność wyszukiwania bez wypychania mapy poza pierwszy ekran telefonu.
- Umieścić Wpis w źródle wcześnie w inspektorze przed długą listą działek.
- Ujednolicić desktopowy powrót fokusu po × iEscape; zachować prawidłowy fokus/mobile lista→mapa→szczegóły.
- Skrócić pusty inspektor, zachowując informację o interpretacji i źródle.

Implementację wykonuje osobny, nowy subagent; autorzy prototypów i jury nie wdrażają wybranego kodu. Następnie osobne SPEC→QUALITY/security review, pełne testy i PR/CI/Pages oraz sprawdzenie prawdziwej strony. Na etapie wyboru produkcja jest bez zmian.

## Zakres dowodów

Wszystkie5 wcześniej przeszły niezależny parent build/UI/dist i rzeczywiste przypadki mapped/multi/partial/unmapped/same-ID/close na320/390/1440. Panel znalazł dodatkowy specyficzny przypadekP5 pominięty w ogólnym smoke. Testy i punktacja nie są pełnym audytem WCAG, Safari, fizycznych telefonów lub czytników ekranu. Surowe niezależne głosy i agregat są w `jury/`.
