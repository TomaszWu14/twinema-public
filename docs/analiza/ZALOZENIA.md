# Założenia do potwierdzenia

**[BA]** · Gdy PO nie odpowiada, BA przyjmuje bezpieczne, minimalne założenie i zapisuje je tutaj.
Założenia biznesowe Z-1…Z-19 (stan obecny, wolumeny, metoda symulacji, retencja itd.) są w
[00-przeglad.md](../00-przeglad.md#założenia-wymagające-potwierdzenia). Poniżej założenia przyjęte przy
wprowadzaniu procesu zespołu i audycie. Materiały z okresu budowy (burza mózgów): [docs/ZALOZENIA.md](../ZALOZENIA.md).

| Nr | Kwestia | Przyjęte założenie (bezpieczne, minimalne) | Status |
|---|---|---|---|
| Z-20 | Język commitów | po angielsku, Conventional Commits — jak dotychczasowa historia; dokumentacja po polsku | do potwierdzenia |
| Z-21 | Gałęzie | zalecane `feature/<id>-<nazwa>`; sesja asystenta AI pracuje na jednej wyznaczonej gałęzi `claude/…`, więc kilka historyjek trafia do jednego PR z osobnymi commitami | do potwierdzenia |
| Z-22 | Kanał zgłaszania podatności | prywatne zgłoszenie w GitHubie (Private Vulnerability Reporting) — PO musi je włączyć w ustawieniach repozytorium | do potwierdzenia |
| Z-23 | Numer pierwszego wydania | bez numeru do decyzji PO; proponowane `0.9.0` dla stanu po audycie, `1.0.0` po zamknięciu ryzyk wysokich | do potwierdzenia |
| Z-24 | Podstawa przetwarzania loginów operatorów (historia zadań) | do czasu decyzji: dane traktowane jak dane osobowe; rekomendacja: pseudonimizacja przy imporcie (US-012) | **decyzja PO (2026-10-16):** pseudonimizacja przy imporcie |
| Z-25 | Poziom ASVS | poziom 1 z wybranymi wymaganiami poziomu 2 dla danych poufnych | do potwierdzenia |
| Z-26 | Własność obiektów | hale, scenariusze i prezentacje są wspólne dla wszystkich Projektantów (jeden zespół); wyjątek: własne modele sprzętu — autor albo Administrator (US-001, ADR-0003) | do potwierdzenia |
| Z-27 | Mierniki sukcesu | propozycja M-1…M-5 w [WIZJA](WIZJA.md), bez wartości docelowych | do decyzji |
| Z-28 | Próg pokrycia testami | raport bez progu; domyślnie proponowane 80% dla logiki domenowej (`scenario/sim`, `ml`, `twin/layout`, `twin/design_*`) | **decyzja PO (2026-10-16):** próg 80% dla logiki domenowej, blokujący w CI |
| Z-29 | Akceptacja ryzyk niskich R-12, R-13, R-15 | proponowana akceptacja do 2027-01-31 — **nieważna bez potwierdzenia PO** | **decyzja PO (2026-10-16):** zaakceptowane do 2027-01-31 |
| Z-30 | Auto-merge gałęzi `claude/**` | PR pozostaje szkicem do akceptacji PO, więc auto-merge się nie uzbraja; docelowo wymagane zatwierdzenie w ochronie gałęzi (US-013) | **decyzja PO (2026-10-16):** auto-merge usunięty; merge tylko przez PO |
| Z-31 | Model użytkownika usuniętego autora | model sprzętu bez autora może zmieniać tylko Administrator | przyjęte w US-001 |
| Z-32 | Historia repozytorium (R-01) | — | **decyzja PO (2026-10-16):** przepisać historię; zalecana opcja A (nowe repozytorium z jedną migawką) — [procedura](../operacje/CZYSZCZENIE_HISTORII.md), wykonuje PO |
