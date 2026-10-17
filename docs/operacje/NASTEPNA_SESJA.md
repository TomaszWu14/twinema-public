# Przekazanie do następnej sesji

Stan na 2026-10-17. Wszystkie zmiany są w `main` (PR #68, #79, #80, #81), CI zielone, brak otwartych PR.

## Zasady pracy (bez zmian)

- Zespół trzech ról: [BA], [DEV], [SEC]; commity w Conventional Commits.
- Po każdym etapie: podsumowanie per rola + lista decyzji dla PO.
- Merge tylko po akceptacji PO. Bez push na inne gałęzie, bez wdrożeń i migracji na produkcji bez zgody PO.
- Nie wymyślać wymagań biznesowych — pytać. Nie obniżać wymagań bezpieczeństwa — eskalować do PO.
- Żadnych nazw kontrahentów, materiałów, pracowników ani danych firmowych. Znaleziska trafiają do sekcji „Do anonimizacji” w [05-decyzje](../05-decyzje-i-ograniczenia.md), nie do dokumentacji.

## Otwarte zadania

### 1. R-01 — czyszczenie historii repozytorium

Wykonuje PO, asystent prowadzi krok po kroku według [CZYSZCZENIE_HISTORII.md](CZYSZCZENIE_HISTORII.md).

- [ ] Krok 1: kopia lustrzana (mirror) starego repo.
- [ ] Krok 2: adres e-mail noreply do autorstwa commitów.
- [ ] Krok 3: commit-migawka (orphan).
- [ ] Krok 4: kontrola gitleaks + `git grep` (oczekiwany kod wyjścia 1, brak trafień).
- [ ] Krok 5: publikacja do nowego repozytorium.
- [ ] Kroki 6–9: stare repo prywatne lub usunięte; przepięcie Coolify i sekretów; ochrona gałęzi `main`; usunięcie `AUTOMERGE_PAT`.
- [ ] Zamknięcie R-01 w [RYZYKA.md](../bezpieczenstwo/RYZYKA.md), CHANGELOG i [AUDYT.md](../AUDYT.md) (w nowym repo).

**Na start sesji PO wkleja:** wynik `git log --oneline` migawki, wynik `git grep` z kroku 4, wynik gitleaks i nazwę nowego repo. Asystent je weryfikuje i przechodzi do kroków 6–9.

### 2. Wdrożenie (po stronie PO)

- [ ] Kopia bazy przed wdrożeniem — migracje `twin` 0008 i 0009 są nieodwracalne.
- [ ] Coolify: `CSP_REPORT_ONLY=false`.
- [ ] Coolify: `BACKUP_DIR` + codzienne zadanie kopii zapasowej.
- [ ] Coolify: `DJANGO_SUPERUSER_PASSWORD` co najmniej 12 znaków.
- [ ] Coolify: `TRUSTED_PROXIES` (lista CIDR; patrz [RUNBOOK.md](RUNBOOK.md)).
- [ ] `python manage.py seed_demo` na instancji demo (rejestr obiektów demo).
- [ ] Włączenie Private Vulnerability Reporting w ustawieniach repo.

## Przydatne polecenia

```bash
cd web
DJANGO_DEBUG=true DJANGO_ALLOWED_HOSTS='*' python manage.py test --parallel 4 --exclude-tag e2e
E2E_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
  DJANGO_DEBUG=true DJANGO_ALLOWED_HOSTS='*' python manage.py test --tag e2e
```

Usuń ten plik (lub zaktualizuj), gdy wszystkie pozycje będą odhaczone.
