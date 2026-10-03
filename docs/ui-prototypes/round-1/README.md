# Pięć prototypów UI/UX — runda1

Otwórz `index.html` jako lokalną galerię zrzutów (bez serwera i bez zależności sieciowych). To nie zastępuje działających map.

Każdy katalog P1–P5 zawiera opis, desktop/mobile/selected screenshot oraz kompletny `source.patch` zawierający także nowe testy. Odtworzenie w osobnym checkout bazowego commita `20ed307465800256fb1a144e55e154668e202841`:

```sh
git apply --check /ścieżka/Pn/source.patch
git apply /ścieżka/Pn/source.patch
npm ci
npm test -- --maxWorkers=1
npm run build
npm run preview
```

Użyj adresu Vite z prefiksem `/ozarow-building-permits/`. Dane bazowego repo pozostają wymagane; patch nie zawiera danych ani sekretów. P2 rzeczywiście kompiluje daisyUI+Tailwind, P3 Tailwind; pozostałe bez nowych zależności. Ograniczenia i wyniki są w SPEC oraz wspólnym parent-verification.json. Wybór jury i produkcyjny redesign są osobnymi etapami; galeria sama nie oznacza wdrożenia.
