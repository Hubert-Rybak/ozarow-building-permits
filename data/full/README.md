# Pełne dane źródłowe — prywatny snapshot

Na wyraźne polecenie właściciela zachowano całe pobrane oficjalne archiwa GUNB oraz wszystkie oryginalne kolumny/wiersze dla gminy Ożarów Mazowiecki w `ozarow-full-source.json`, bez ograniczenia dat i bez redakcji tytułów, opisów ani kolumn źródłowych. Wiersze nie są scalone: kilka wierszy może dotyczyć tej samej sprawy i różnych działek.

Archiwum mazowieckie zawiera również pozostałe gminy województwa, a archiwum zgłoszeń obejmuje dane krajowe od 2022 r. `manifest.json` podaje rzeczywiste czasy pobrania i SHA-256; `packagedAt` jest czasem spakowania, nie nowego pobrania. Dane dla aplikacji w `public/data/` są osobnym, scalonym wycinkiem.

Repo pozostaje prywatne. Ten katalog nie trafia do `public/` ani produkcyjnego builda Vite. Codzienny importer aplikacji nie aktualizuje automatycznie tego surowego snapshotu. Nie dodano sekretów, poświadczeń, cookies, logów ani plików środowiska.
