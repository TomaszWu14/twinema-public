# Runbook operacyjny

**[DEV]** z [SEC] · wdrożenie, kopie zapasowe, odtworzenie, incydenty. Operacje na produkcji (wdrożenie,
migracje na danych produkcyjnych, odtworzenie) wykonuje się **tylko za zgodą PO**.

## Wdrożenie

| Krok | Działanie |
|---|---|
| 1 | Zmiana scalona do `main` po akceptacji PO (CI zielone). |
| 2 | Workflow `Deploy` wywołuje webhook platformy (Coolify) i czeka, aż `/health/` zwróci nowy skrót commita. |
| 3 | Kontener przy starcie wykonuje: migracje, utworzenie ról, opcjonalnie konto administratora i dane demo, start serwera. |
| 4 | Kontrola: `GET /health/` → `{"status": "ok", "db": "ok", "version": "<skrót>"}`. |

Ustawienia platformy (Coolify): typ budowy **Dockerfile**; port aplikacji **8000** tylko w sieci wewnętrznej
platformy, ruch z internetu wyłącznie przez proxy TLS (adres klienta z nagłówka proxy jest brany pod uwagę tylko z sieci wewnętrznej — US-006; zalecane: `TRUSTED_PROXIES` z siecią Traefika, bo przy porcie opublikowanym wprost (`-p 8000:8000`, bez proxy) każdy klient przychodzi z adresu prywatnego bramki Dockera i mógłby podmienić nagłówek, omijając blokadę logowania); kontrola
działania: ścieżka `/health/`, okres startowy co najmniej 120 s; trwały wolumen na media i — przy SQLite — na plik bazy.

Zmienne środowiskowe: [.env.example](../../.env.example); walidacja przy starcie w `web/twinema/config.py`.
Kontener uruchamia obok serwera worker kolejki zadań (`manage.py run_jobs`, ADR-0004); `RUN_WORKER=false`
wyłącza go, gdy worker działa jako osobna usługa z tym samym obrazem i poleceniem `python manage.py run_jobs`.
Worker co minutę odświeża sygnał zadania, które liczy; zadanie „w toku” bez sygnału od `JOB_STALE_MIN` wraca do kolejki. Zadanie z błędem Projektant ponawia przyciskiem „Policz ponownie”. Stan zadań: tabela `core_job`.
Kontener przy starcie usuwa też wpisy dziennika operacji starsze niż `AUDIT_RETENTION_DAYS` (US-008) i próby logowania
starsze niż `LOGIN_ATTEMPT_RETENTION_DAYS` (30 dni, RODO CP-2); dziennik ogląda Administrator pod `/dziennik/`.
**Demo publiczne (`DEMO_PUBLIC=true`) tylko na osobnej instancji z danymi demo** (R-02). Gdy w bazie są dane spoza demo, kontener zapisuje przy starcie ostrzeżenie w logach, Administrator widzi baner, a wejście gościa jest zablokowane (US-011, R-02).

### Wdrożenie zmian z PR #68 — kroki dla PO

- **Kopia zapasowa bazy przed wdrożeniem.** Migracja `twin 0008_pseudonimizacja_operatorow` nieodwracalnie
  zastępuje loginy operatorów w historii zadań pseudonimami (US-012). Wycofanie wersji nie przywróci loginów.
- Pseudonim zależy od `SECRET_KEY`: zmiana klucza daje inne pseudonimy dla nowych importów. Klucz zmieniać
  razem z ponownym importem historii zadań.
- Migracja `equipment 0007` dopisuje przyrostek („ 2”) do powtórzonych nazw własnych modeli sprzętu (US-022) —
  parametry i powiązania bez zmian; najstarszy model zachowuje nazwę.
- CSP jest domyślnie wymuszana (US-005). Jeśli w Coolify jest `CSP_REPORT_ONLY=true`, usuń tę zmienną albo ustaw
  `false`. Gdy po wdrożeniu któryś ekran przestanie działać, `CSP_REPORT_ONLY=true` przywraca tryb raportu bez
  zmiany kodu (zgłoś ekran jako błąd).
- Weryfikacja dwuetapowa (US-017): po wdrożeniu każdy Administrator przy logowaniu konfiguruje aplikację
  uwierzytelniającą. `TWO_FACTOR_ADMIN=false` wyłącza obowiązek tylko awaryjnie (zgłoś jako incydent).
- Ochrona gałęzi `main`: wymagane zatwierdzenie PR i zielone CI (R-09, US-013) — ustawia PO w GitHubie.
- Kontener działa jako `app` (UID 10001). Wolumeny używane dotąd mają już tego właściciela. Nowy katalog
  hosta: `chown -R 10001:10001 <katalog>` przed startem; jednorazowo można też uruchomić kontener z
  `--user root` — entrypoint naprawi uprawnienia i zejdzie do `app`.
- Usunięcie sekretu `AUTOMERGE_PAT` z repozytorium — automatyczny merge został usunięty z CI.
- Włączenie Private Vulnerability Reporting (Z-22).
- Czyszczenie historii repozytorium (R-01): [CZYSZCZENIE_HISTORII.md](CZYSZCZENIE_HISTORII.md).

### Wycofanie wersji

Na platformie: ponowne wdrożenie poprzedniego obrazu / commita. Jeśli nowa wersja miała migrację niewstecznie
zgodną — odtworzenie bazy z kopii sprzed wdrożenia (niżej).

## Kopie zapasowe

Decyzja PO (Z-36): **RPO 24 h, RTO 4 h**, retencja 14 kopii, próba odtworzenia co miesiąc (US-009, R-10).

| Krok | Działanie |
|---|---|
| Katalog | `BACKUP_DIR` — trwały wolumen **poza** wolumenem mediów, najlepiej na osobnym dysku; kopie zawierają dane poufne i osobowe, więc magazyn musi być szyfrowany i dostępny tylko Administratorowi platformy |
| Harmonogram | Coolify → aplikacja → *Scheduled Tasks*: `python manage.py backup`, codziennie o 02:00 (cron `0 2 * * *`) |
| Zawartość zestawu | katalog `RRRRMMDD-GGMMSS/`: `baza.dump` (PostgreSQL, `pg_dump --format=custom`) albo `baza.sqlite3`, `media.tar.gz` (bez plików tymczasowych importów), `manifest.json` (wersja, rozmiary, SHA-256) |
| Retencja | polecenie zostawia 14 najnowszych zestawów (`--keep N`, żeby zmienić) |
| Kopia poza serwerem | raz na dobę synchronizacja `BACKUP_DIR` do magazynu zewnętrznego (np. S3 z szyfrowaniem po stronie serwera) — konfiguruje Administrator platformy |
| Kontrola | w logach zadania: „Kopia … (baza…: N KB, media…: M KB)”; brak wpisu albo błąd = alarm. Sumy: `python manage.py backup --verify <katalog zestawu>` |

Ręcznie przed każdą migracją na produkcji: `python manage.py backup` w kontenerze.

## Odtworzenie

Cel: działanie w ciągu 4 h od decyzji o odtworzeniu (RTO, Z-36).

1. Wybierz zestaw i sprawdź go: `python manage.py backup --verify "$BACKUP_DIR/RRRRMMDD-GGMMSS"`.
2. Zatrzymaj aplikację (tryb serwisowy na platformie).
3. Baza: `pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" baza.dump` albo podmiana pliku SQLite na `baza.sqlite3`.
4. Media: `tar xzf media.tar.gz -C "$MEDIA_ROOT"`.
5. Uruchom aplikację; kontener wykona migracje do bieżącej wersji.
6. Sprawdź `/health/`, logowanie i otwarcie jednego modelu hali.
7. **Próba odtworzenia** na środowisku testowym co miesiąc (Z-36) — wynik (data, zestaw, czas trwania) zapisz w issue.

## Incydenty

| Sytuacja | Działanie natychmiastowe | Dalej |
|---|---|---|
| Administrator zgubił telefon z aplikacją uwierzytelniającą (US-017) | `python manage.py two_factor_reset <login>` w kontenerze | potwierdź tożsamość osoby innym kanałem; przy następnym logowaniu skonfiguruje nową aplikację |
| Użytkownik zablokowany po nieudanych logowaniach | `python manage.py axes_reset_username <login>` w kontenerze | sprawdź, czy to nie atak (adresy IP w panelu administracyjnym, sekcja prób logowania) |
| Wyciek tokenu stanowiska renderującego | nowy `RENDER_WORKER_TOKEN` (≥ 32 znaki) w zmiennych platformy, restart; ten sam token na stanowisku | przejrzyj zlecenia z ostatnich dni |
| Wyciek klucza usługi AI | unieważnij klucz u dostawcy, ustaw nowy `ANTHROPIC_API_KEY` | sprawdź zużycie u dostawcy |
| Niechciane udostępnienie pokazu | w prezentacji: „Wyłącz link” (albo nowy link — stary przestaje działać) | — |
| Demo publiczne na instancji z danymi rzeczywistymi | `DEMO_PUBLIC=false`, restart | ocena naruszenia ochrony danych (RODO: 72 h na zgłoszenie, jeśli dotyczy) — decyzja PO |
| Sekret w repozytorium | unieważnij sekret u źródła, ustaw nowy | usunięcie z historii — decyzja PO (przepisanie historii) |
| Aplikacja nie startuje | logi kontenera: komunikat „Błąd konfiguracji środowiska” wskazuje zmienną | popraw zmienną, wdrożenie ponownie |
| `/health/` zwraca 503 | baza niedostępna — sprawdź usługę bazy na platformie | odtworzenie z kopii, jeśli baza uszkodzona |
| Stanowisko renderujące odmawia połączenia „bez HTTPS” | ustaw adres serwera `https://…` (`TWINEMA_URL`) | — |

Zgłoszenia podatności: [SECURITY.md](../../SECURITY.md).
