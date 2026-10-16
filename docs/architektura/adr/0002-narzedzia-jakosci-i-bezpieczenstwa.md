# ADR-0002: Narzędzia jakości i bezpieczeństwa w CI

**Data:** 2026-10-15 · **Status:** proponowana (do akceptacji PO) · **Role:** [DEV] + [SEC]

## Kontekst

CI miało lint (ruff), testy Python i JS, kontrolę migracji, `check --deploy` oraz gitleaks; pip-audit działał
tylko raz w tygodniu i nie blokował. Brakowało SAST, skanu kontenera, automatycznych aktualizacji zależności
i pomiaru pokrycia. Proces zespołu wymaga, by ustalenia o wysokiej wadze blokowały PR.

## Rozważane opcje

| Obszar | Opcje | Wybór |
|---|---|---|
| SAST | bandit; semgrep; CodeQL | bandit (blokujący) + semgrep z regułami OWASP i Django (raport) |
| SCA | pip-audit; Safety; Dependabot alerts | pip-audit (blokujący) + Dependabot (PR z aktualizacjami) |
| Kontener | trivy; grype; Docker Scout | trivy (Dockerfile i obraz) |
| Pokrycie | coverage.py; pytest-cov | coverage.py — testy działają na runnerze Django, bez pytest |
| Typowanie | mypy; brak | **brak na teraz** — kod nie ma adnotacji typów; wprowadzenie = osobna historyjka |
| Formatowanie | ruff format; brak | **brak na teraz** — repozytorium nie jest sformatowane ruffem (masowy reformat = osobny PR) |

Wszystkie wybrane narzędzia są darmowe i open-source albo wbudowane w GitHub.

## Decyzja

- **Blokujące:** ruff, testy, migracje, `check --deploy`, gitleaks, **pip-audit na każdym PR**,
  **bandit od wagi i pewności średniej** (`web/`, `tools/`, bez testów i migracji).
- **Raportujące (artefakty):** semgrep, trivy (konfiguracja i obraz: wysokie i krytyczne z dostępną poprawką),
  pokrycie testami. Semgrep i trivy nie dało się uruchomić w środowisku przygotowania tej zmiany (brak dostępu do
  rejestru reguł i do demona Dockera), dlatego najpierw raportują; po triażu pierwszych wyników przechodzą
  w tryb blokujący (US-014, R-18).
- **Fałszywe alarmy** oznaczane pojedynczo: `# nosec Bxxx` na linii i uzasadnienie w komentarzu nad nią.
  Na start oznaczono trzy: stała w `mark_safe` (B308), adres stanowiska ograniczony do http(s) (B310),
  katalog tymczasowy dodatku Blendera na komputerze użytkownika (B108).
- **Wersje narzędzi przypięte** w `requirements-dev.txt` i workflow; Dependabot aktualizuje pip, akcje GitHub i obrazy.
  Trivy działa z obrazu `aquasec/trivy:<wersja>`, bo akcja `trivy-action` pod przypiętym tagiem okazała się niedostępna.

## Konsekwencje

- PR z podatną zależnością albo nowym ustaleniem SAST średniej wagi nie przejdzie bez poprawki lub
  uzasadnionego wyjątku.
- Czas CI rośnie o kilka minut (osobne joby równolegle; budowa obrazu dla trivy).
- Próg pokrycia: 80% dla logiki domenowej, blokujący (decyzja PO, Z-28). Tryb blokujący semgrep/trivy — po triażu (US-014).
- Akcje przypięte tagami, nie skrótami commitów (R-16, US-018).
