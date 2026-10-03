# Pełne dane źródłowe GUNB — snapshot

Na wyraźne polecenie właściciela zachowano całe pobrane oficjalne archiwa GUNB oraz oryginalne wiersze dla gminy Ożarów Mazowiecki w `ozarow-full-source.json`, bez ograniczenia dat i bez redakcji tytułów, opisów ani nazwanych kolumn źródłowych. Wiersze nie są scalone: kilka wierszy może dotyczyć tej samej sprawy i różnych działek. JSON jest słownikiem nazw kolumn; powtórzone nagłówki CSV (np. `cecha`) mają jedną wartość pod danym kluczem. Wszystkie kolumny, także powtórzone, pozostają w niezmienionych oryginalnych ZIP-ach.

Archiwum mazowieckie zawiera również pozostałe gminy województwa, a archiwum zgłoszeń obejmuje dane krajowe od 2022 r. `manifest.json` podaje rzeczywiste czasy pobrania i SHA-256; `packagedAt` jest czasem spakowania, nie nowego pobrania. Dane dla aplikacji w `public/data/` są osobnym, scalonym wycinkiem.

Snapshot spakowano i przesłano do prywatnego repo; po udanej weryfikacji aplikacji repo upubliczniono 3 października 2026, zgodnie z decyzją właściciela. Ten katalog jest dostępny w repo, ale nie trafia do `public/` ani produkcyjnego builda Vite. Codzienny importer aplikacji nie aktualizuje automatycznie tego surowego snapshotu. Nie dodano sekretów, poświadczeń, cookies, logów ani plików środowiska.
