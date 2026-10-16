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
platformy, ruch z internetu wyłącznie przez proxy TLS (adres klienta z nagłówka proxy jest brany pod uwagę tylko z sieci wewnętrznej — US-006); kontrola
działania: ścieżka `/health/`, okres startowy co najmniej 120 s; trwały wolumen na media i — przy SQLite — na plik bazy.

Zmienne środowiskowe: [.env.example](../../.env.example); walidacja przy starcie w `web/twinema/config.py`.
**Demo publiczne (`DEMO_PUBLIC=true`) tylko na osobnej instancji z danymi demo** (R-02). Gdy w bazie są dane spoza demo, kontener zapisuje przy starcie ostrzeżenie w logach, a Administrator widzi baner na stronie startowej (US-011).

### Wycofanie wersji

Na platformie: ponowne wdrożenie poprzedniego obrazu / commita. Jeśli nowa wersja miała migrację niewstecznie
zgodną — odtworzenie bazy z kopii sprzed wdrożenia (niżej).

## Kopie zapasowe

Projekt nie ma automatycznego mechanizmu kopii (R-10, US-009). Do czasu automatyzacji — procedura ręczna
przed każdą migracją na produkcji i co najmniej raz w tygodniu. RPO i RTO ustala PO.

| Co | PostgreSQL | SQLite |
|---|---|---|
| Baza | `pg_dump --format=custom --file=twinema-RRRRMMDD.dump "$DATABASE_URL"` | zatrzymanie aplikacji albo `sqlite3 "$DB_PATH" ".backup twinema-RRRRMMDD.sqlite3"` |
| Media | archiwum katalogu `MEDIA_ROOT` (`tar czf media-RRRRMMDD.tgz -C "$MEDIA_ROOT" .`) | jak obok |
| Przechowywanie | poza serwerem aplikacji, szyfrowane, z ograniczonym dostępem (dane poufne i osobowe) | jak obok |
| Retencja | propozycja: 7 dziennych, 4 tygodniowe — do potwierdzenia z [RODO](../bezpieczenstwo/RODO.md) | jak obok |

Kopie można też włączyć po stronie platformy (Coolify ma zaplanowane kopie baz danych) — decyzja PO.

## Odtworzenie

1. Zatrzymaj aplikację (tryb serwisowy na platformie).
2. Baza: `pg_restore --clean --if-exists --dbname="$DATABASE_URL" twinema-RRRRMMDD.dump` albo podmiana pliku SQLite.
3. Media: rozpakuj archiwum do `MEDIA_ROOT`.
4. Uruchom aplikację; kontener wykona migracje do bieżącej wersji.
5. Sprawdź `/health/`, logowanie i otwarcie jednego modelu hali.
6. **Próba odtworzenia** na środowisku testowym co kwartał — wynik zapisz w CHANGELOG (sekcja operacyjna) lub w issue.

## Incydenty

| Sytuacja | Działanie natychmiastowe | Dalej |
|---|---|---|
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
