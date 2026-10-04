# Radar Ożarów

Polskojęzyczny radar inwestycji gminnych, publicznych i prywatnych oraz mapa publicznych wpisów budowlanych GUNB RWDZ dla **całej gminy Ożarów Mazowiecki — miasta i obszaru wiejskiego**. React + TypeScript + Vite + Leaflet, statyczne JSON/GeoJSON, bez serwera aplikacyjnego i bez kluczy API w przeglądarce.

## Co przedstawiają dane

- Wpisy wniosków, odnotowanych decyzji i zgłoszeń, z opisem inwestycji, datami, adresem, odwołaniami do działek i źródłami.
- Rzeczywiste obrysy działek z publicznej usługi **ULDK GUGiK**, weryfikowane po pełnym identyfikatorze i obrębie — nie geokodowane punkty ani sztuczne prostokąty.
- Lista, mapa, wyszukiwanie, filtry i szczegóły oraz eksport wyników.
- Jawne statusy pokrycia geometrią: pełne, częściowe i nierozwiązane; zakres i czas pobrania są zapisane w metadanych.

**Odnotowana decyzja nie oznacza pozytywnego pozwolenia.** CSV nie podaje wyniku rozstrzygnięcia. Zgłoszenie nie jest pozwoleniem. Brak wpisów typu „sam wniosek” w eksporcie nie dowodzi braku nierozpatrzonych wniosków w gminie.

Domyślny zakres importu obejmuje daty **wpływu wniosków od 1 stycznia 2025 roku**, a nie wszystkie decyzje wydane od tej daty. Źródło może zawierać błędy TERC, nieaktualne numery działek i sprzeczne etykiety miejscowości. Takie odwołania nie są automatycznie „naprawiane”. Obrysy opisują stan ULDK z chwili pobrania, nie historyczne granice z daty wniosku.

Aplikacja domyślnie pokazuje **ostatnie 3 miesiące kalendarzowe** względem dzisiejszej daty w strefie Europe/Warsaw, według daty decyzji lub — przy jej braku — daty wniosku. Filtr „Okres → Wszystkie daty” udostępnia cały załadowany zbiór, także wpisy bez daty. Mapa, lista, liczniki i eksport CSV korzystają z tych samych filtrów; „Wyczyść filtry” przywraca ostatnie 3 miesiące.

Pełna metodologia, oficjalne źródła, weryfikacja TERYT, zakres i ograniczenia: **[docs/SOURCES.md](docs/SOURCES.md)**.
