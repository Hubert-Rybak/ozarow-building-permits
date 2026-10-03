# P2 · Civic daisyUI

## Zakres i rezultat

Lokalny, uruchamialny prototyp w `/opt/data/cache/scratch/ozarow-ui-round1/prototype-02`, odłączony od bazowego `20ed307`. Bez commitów, push, publikacji, zmian danych, importerów, workflow, ustawień i poświadczeń. Nie oceniano innych kandydatów.

**Cel:** jasny obywatelski Explore, nie katalog komponentów. Biel i ciepła szarość, spokojny niebieski akcent, dyskretny zielony znak gminy; systemowy font bez zdalnych fontów. Karty zamiast zwartych wierszy, jedna główna akcja filtrów, wyraźna nawigacja mapa/lista oraz czytelna kolumna szczegółów.

## Rzeczywista integracja

- `tailwindcss@4.3.3`, `@tailwindcss/vite@4.3.3`, `daisyui@5.7.47`: dokładne devDependencies i zachowany lockfile.
- `vite.config.ts`: rzeczywisty plugin `tailwindcss()`.
- `src/styles.css`: lokalny `@import "tailwindcss"`, `@plugin "daisyui"`, lokalny `@plugin "daisyui/theme"` z motywem `civic`.
- Użyte komponenty: navbar, card, input, select, btn/btn-primary/btn-ghost/btn-outline/btn-square, badge, join, stats, drawer/drawer-end/drawer-toggle/drawer-side/drawer-overlay.
- Bez CDN, zdalnego arkusza i atrap klas. Arkusz daisyUI rzeczywiście dostarcza przełączanie i układ drawer oraz komponenty; CSS aplikacji dostosowuje układ i tokeny.
- Oficjalne referencje instalacji: `https://tailwindcss.com/docs/installation/using-vite`, `https://daisyui.com/docs/install/react/` — oba pobrania HTTP 200 podczas pracy. Backend web_extract nie obsługiwał ekstrakcji; sprawdzono referencje bezpośrednim HTTP.

## Tokeny i układ

| Token | Wartość |
|---|---|
| Tło | `#f4f5f1` |
| Powierzchnia | `#ffffff` |
| Tekst | `#203c47` |
| Główna akcja | `#245e77` + biały tekst |
| Zieleń kontekstu | `#436951` |
| Obramowanie | `#dce2de` |
| Fokus | `#b58038`, 3px |
| Promień | 8–14px |
| Główny tap target | min. 44px, kwadrat 44 × 44 |
| Breakpoint mobilny | 720px |
| Szerokość treści | max. 1440px |

Desktop: listowe karty po lewej i mapa po prawej. Lista w nawigacji rozwija katalog do trzech kolumn. Wybrany rekord dodaje kontekstową kolumnę szczegółów; przy mniejszych szerokościach szczegóły przechodzą pod workspace. Wąski ekran: mapa/lista przełączane bez odmontowania Leaflet, mapa przed podsumowaniem liczbowym i ograniczeniami. Źródło GUNB oraz data importu pozostają nad mapą. Ograniczenia i pełna metodologia nie zostały usunięte.

## Progressive disclosure i dostępność

Okres i wyszukiwanie są stale dostępne. Rodzaj, rok, status źródłowy, miejscowość oraz położenie na mapie są w wysuwanym panelu. Zmiany aktualizują wspólny zbiór od razu; „Pokaż wyniki” zamyka panel, nie tworzy odrębnego stanu filtrów.

Panel: `aria-expanded`, `aria-controls`, rola dialogu podczas otwarcia, `aria-modal`, inert podczas zamknięcia, fokus na zamknięciu, pułapka Tab/Shift+Tab, Escape, powrót fokusu do wyzwalacza oraz zamknięcie tłem. Widoczność drawer bez animacji dyskretnej: oryginalne opóźnienie daisyUI uniemożliwiało w prawdziwym Chromium początkowy fokus; zostało wyłączone. Obsługa reduced-motion i widoczny fokus zachowane. Standardowe linki attribution Leaflet pozostają małym drukiem, zgodnie z istniejącą mapą; główne kontrolki mają 44px.

## Zachowane przepływy i semantyka

1. Start / reset: ostatnie **3 miesiące kalendarzowe**, Europe/Warsaw, obie granice włącznie, data decyzji albo data wniosku.
2. „Wszystkie daty”: cały aktualnie załadowany zbiór, również rekordy bez daty.
3. Wspólne filtry dla listy, mapy, liczników i eksportu CSV; wszystkie dotychczasowe wymiary i sortowanie.
4. Mobilny wybór karty z geometrią → mapa, zaznaczenie i objęcie kadrem wszystkich dostępnych polygonów; również kolejne wybranie tego samego ID.
5. Polygon → szczegóły; zamknięcie szczegółów → ponownie widoczna mapa. Stan filtrów i instancja Leaflet zachowane.
6. Rekord bez geometrii → szczegóły w widoku listy, bez sztucznego punktu na mapie.
7. Partial i unresolved jawne; dostępne obrysy nie udają kompletnych dopasowań.
8. Decyzja ≠ pozytywne pozwolenie. Wynik nieudostępniony w CSV jest opisany jako nieokreślony. Źródła, prywatność, ograniczenia, zakres i metodologia zachowane.
9. Ładowanie, pusty wynik, błąd, ponowienie i brak kafelków OSM nadal obsługiwane.

## Rzeczywiste dane i sprawdzenie

- Dataset: **447 wpisów, 842 unikalne obrysy**, 399 wpisów z obrysem w całym zbiorze.
- Domyślny okres 3 października 2026: **60 wpisów, 54 z obrysem, 6 bez obrysu, 127 unikalnych działek**.
- Bazowe 75 testów UI zachowane. Dodano 2 testy TDD: przed zmianami prawidłowy RED (brak wyzwalacza panelu i integracji pluginów), po zmianach **77/77**, 7 plików. Finalny run: 15.29s, `npm test -- --maxWorkers=1 --pool=threads --testTimeout=20000`.
- `npm run build`: TypeScript i produkcyjny Vite OK; finalny build 10.88s.
- `git diff --check`: OK.
- `.cache/verify_list_map.py http://127.0.0.1:4192/ozarow-building-permits/`: exit 0, prawdziwy Chromium/touch na 390, 320 i 1440px; dopasowanie pełne, częściowe, wiele działek, powtórne ID, polygon→detail→map, unmapped→list, reset, zachowanie filtrów i instancji.
- Stricte document overflow: scrollWidth/clientWidth **1440/1440, 390/390, 320/320** na domyślnych ekranach; dodatkowy browser check listy również bez overflow.
- Mobilna mapa: top **437px**, widoczne **365px** przy 390×844; top **438.5px**, widoczne **261.5px** przy 320×700. Bazowy mobilny screenshot miał mapę od ok. 869px.
- Rzeczywisty eksport CSV: **60 rekordów, 20 kolumn, ID identyczne z bieżącą listą**.
- Rzeczywisty abort pobrania permits → stan błędu → „Spróbuj ponownie” → 60 oryginalnych rekordów. Bez zastępczych danych.
- Klawiatura: Tab oraz Shift+Tab zamykają cykl wewnątrz panelu, Escape przywraca fokus.
- Brak błędów JS i nieudanych odpowiedzi aplikacji w sprawdzonych przebiegach. OSM jest usługą zewnętrzną, nie aplikacją.
- Dodatkowe browser checks: zmierzone 9.369s. Tokeny modelu i łączny czas wszystkich prób nie są dostępne jako dokładny licznik; nie wpisano wymyślonych wartości.
- Preview uruchamiany jako bounded subprocess, zakończony w finally. Odczyt portu 4192 po sprzątaniu: connect_ex **111** (brak nasłuchu).

## Koszt zależności i bundle

`npm ci`: 158 audytowanych pakietów; po instalacji 171, **+13**. Audyt install: 0 podatności. daisyUI/Tailwind to koszt kompilacji i CSS, bez dodatkowej biblioteki UI runtime. Finalny bundle:

- CSS: **106975 B**, gzip narzędzia Vite ok. **22.30 kB**; gzip Python **22219 B**.
- JS: **408496 B**, gzip Vite ok. **125.06 kB**; gzip Python **124354 B**.

Różnica gzip wynika z narzędzia/parametrów kompresji. Nie zmierzono porównywalnego builda baseline, więc nie podano niezweryfikowanej różnicy rozmiaru bundle.

## Artefakty i oględziny

W `.cache/design-output/`: **SPEC.md**, **verification.json**, **desktop.png** (1440×1000), **mobile.png** (390×844), **mobile-selected.png** (390×844). Dodatkowo mobile-320.png, mobile-details.png i drawer.png. Wszystkie wymagane screenshots, a także szczegóły, rzeczywiście otwarto i obejrzano; mapa ma prawdziwe kafelki i prawdziwe działki, szczegóły pokazują właściwą semantykę, tekst nie przelewa się poza ekran.

## Zmiany plików

Tracked: `src/App.tsx`, `src/styles.css`, `vite.config.ts`, `package.json`, `package-lock.json`, `README.md`.
Nowy test: `tests/ui/civic.test.tsx`.
Lokalne narzędzia i dowody: `.cache/capture_p2.py`, `.cache/extra_p2.py`, `.cache/debug_p2.py`, `.cache/list-map-local.json`, `.cache/design-output/*`.
`ParcelMap.tsx`, model, typy, loader oraz artefakty danych pozostawiono bez zmian.

## Problemy i ograniczenia

- Pierwszy run testu TDD przekroczył timeout; ponowiony w jednym workerze dał prawidłowy RED. Później pojedynczy fork Vitest nie wystartował w limicie; finalna pełna seria w jednym wątku przeszła bez błędów.
- Pierwszy bounded run starego verifiera przekroczył 220s. Finalny run z limitem 400s zakończył się poprawnie; żaden timeout nie zastąpił wyniku pozytywnego.
- npm ostrzegł o zablokowanym postinstall esbuild. TypeScript, Vite build i przeglądarka działały; nie zmieniano ustawień allowScripts.
- Początkowy browser check fokusowania drawer wykazał realną usterkę przejścia visibility; poprawiono ją i sprawdzono ponownie w Chromium, łącznie z pułapką fokusu.
- Układ przesuwa ograniczenia i podsumowanie pod mapę na telefonach; są dostępne po przewinięciu. Źródło i link „O danych” pozostają widoczne.
- Dane importu i geometrii mogą być niekompletne lub opóźnione; zachowano wszystkie ostrzeżenia. OSM wymaga dostępu do sieci, ale obrysy i lista działają bez kafelków.
- Nie przeprowadzono pełnego audytu WCAG / czytnika ekranu. Nie uruchamiano testów importerów i workflow, ponieważ pozostają poza zakresem UI.
- Bez publikacji, commitów ani pozostawionego serwera. To osobny kandydat do późniejszego porównania.
