# Changelog

Wszystkie istotne zmiany projektu. Format: [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
wersjonowanie: [SemVer](https://semver.org/lang/pl/). Historia sprzed wprowadzenia dziennika: `git log`.

Pierwsze wydanie z numerem wersji ustali PO ([Z-23](docs/analiza/ZALOZENIA.md)); do tego czasu zmiany
trafiają do sekcji „Unreleased”.

## [Unreleased]

### Added
- Dokumentacja analityczna procesów: przegląd, procesy P1–P8, model danych, user flow, integracje,
  decyzje i ograniczenia (`docs/00-…05-…`).
- Proces pracy zespołu [BA] / [DEV] / [SEC]: `CONTRIBUTING.md` (Definition of Ready i Done, konwencje),
  `SECURITY.md`, szablony issues i PR, `CODEOWNERS`.
- Audyt stanu projektu z trzech perspektyw (`docs/AUDYT.md`).
- Dokumenty analizy (`docs/analiza/`): wizja, interesariusze, procesy AS-IS/TO-BE, wymagania 0.1, backlog
  MoSCoW, słownik, założenia, macierz śledzenia.
- Dokumenty architektury (`docs/architektura/`): kontekst i kontenery C4, model danych, API; ADR-0002
  (narzędzia jakości i bezpieczeństwa), ADR-0003 (własność modeli sprzętu).
- Dokumenty bezpieczeństwa (`docs/bezpieczenstwo/`): klasyfikacja danych, threat model STRIDE 0.1, rejestr
  ryzyk, RODO, checklista ASVS poziom 1.
- Strategia testów (`docs/testy/`) i runbook operacyjny (`docs/operacje/`).
- CI: pip-audit i bandit jako kontrole blokujące, semgrep i trivy jako raport, raport pokrycia testami;
  Dependabot dla pip, GitHub Actions i obrazów Docker.
- `tblib` w zależnościach deweloperskich — testy równoległe pokazują pełny traceback błędu.

### Changed
- Usunięcie hali, scenariusza i własnego sprzętu prowadzi przez ekran potwierdzenia z liczbą obiektów usuwanych
  razem z nim i tracących powiązanie (US-004).
- Rola Podgląd nie widzi w menu, kaflach i na ekranach przycisków prowadzących do stron bez dostępu (US-019).
- Komunikat po usunięciu sprzętu podaje, ile grup floty mieszanej usunięto razem z nim (US-002).
- ADR przeniesione do `docs/architektura/adr/`.
- Własne strony „nie znaleziono” i „błąd serwera” z drogą powrotu (US-020).
- Formularze scenariusza po błędzie walidacji zachowują wpisane wartości (US-021).
- Zlecenia renderu i montażu po 3 nieudanych próbach kończą się błędem zamiast wracać do kolejki bez końca (US-015).
- CI: próg pokrycia 80% dla logiki domenowej jest blokujący (Z-28, US-023); usunięty automatyczny merge
  gałęzi `claude/**` — scala tylko PO (R-09).
- CI: akcje GitHub przypięte skrótem commita, Dependabot z karencją 7 dni (US-018); semgrep i trivy
  blokują PR po triażu pierwszych wyników (US-014, `docs/bezpieczenstwo/TRIAZ_SKANOW.md`).
- Dziennik operacji wrażliwych dla Administratora: usunięcia, importy plików, linki publiczne — kto, co,
  kiedy, adres IP; retencja `AUDIT_RETENTION_DAYS` (domyślnie 365 dni) (US-008).
- Kolejka zadań w bazie z workerem `run_jobs` (ADR-0004): symulacja dnia i scenariusza oraz kalibracja liczą się
  w tle, a ekran pokazuje stan bez przeładowania (US-007); duży import zadań przetrwa restart i jest ponawiany
  bez duplikatów (US-024). Wynik zapisany w bazie widzą wszystkie procesy serwera.
- Nazwa własnego modelu sprzętu jest unikalna (formularz, kopie „(kopia) 2”, ograniczenie w bazie) (US-022).
  **Uwaga przy wdrożeniu:** migracja `equipment 0007` dopisuje przyrostek do powtórzonych nazw własnych modeli.
- Wynik symulacji przypięty do prezentacji 3D nie wypada z limitu przebiegów; gdy zniknie razem ze scenariuszem,
  prezentacja ostrzega Projektanta (US-025).
- Formularz typu regału i edycja stref po błędzie walidacji zachowują wpisane wartości (US-021).
- Import danych podstawowych, przebiegi ML i szkic scenariusza z Claude idą przez kolejkę zadań — żądanie nie
  czeka na wynik, ekran pokazuje stan i link do wyniku (T-1).
- Testy E2E w przeglądarce (Playwright, job CI `e2e`): logowanie i główne ekrany, wynik symulacji, ekrany ze
  skryptami pod wymuszoną CSP, demo gościa i link publiczny.
- Próby logowania (login, adres IP) usuwane po 30 dniach przy starcie kontenera (`LOGIN_ATTEMPT_RETENTION_DAYS`,
  RODO CP-2, decyzja PO).
- Kopie zapasowe: `manage.py backup` (baza + media, manifest SHA-256, retencja 14, `--verify`); obraz z
  `postgresql-client` (US-009). **Do ustawienia:** `BACKUP_DIR` i zadanie zaplanowane w Coolify (RUNBOOK).
- Procedura czyszczenia historii repozytorium (`docs/operacje/CZYSZCZENIE_HISTORII.md`, R-01) — wykonuje PO.

### Fixed (przegląd kodu po #68, 2026-10-17)
- Symulacja dnia i kalibracja: zadanie z błędem nie wraca do kolejki przy każdym wejściu na stronę — widać komunikat,
  a Projektant ponawia obliczenie przyciskiem „Policz ponownie”.
- Kolejka zadań: worker co minutę odświeża sygnał liczonego zadania (`core.Job.heartbeat_at`, migracja core 0004), więc
  długie zadanie nie wraca do kolejki i nie liczy się drugi raz równolegle; wynik zapisuje tylko worker, który wciąż ma
  zadanie. Ponowiony import zadań, który już się udał, nie oznacza partii jako błędnej.
- Weryfikacja dwuetapowa: adres powrotu z kilkoma parametrami nie gubi ich; po 5 błędnych kodach przy konfiguracji
  strona pokazuje nowy kod QR zamiast nieważnego starego.
- `manage.py backup --keep 0` (albo ujemne) kończy się błędem zamiast skasować wszystkie kopie, w tym nową.
- Dymki wykresów (prognoza ML, symulacja scenariusza, profil zadań) pokazują liczby po polsku z jednym miejscem
  po przecinku zamiast „9.600000000000001”.

### Security
- Migracja `twin 0009`: pseudonimizuje też loginy systemu magazynowego w rodzaju „OP-0001”, które 0008 pomijała
  (RODO, US-012). **Nieodwracalna** — kopia bazy przed wdrożeniem.
- `TRUSTED_PROXIES`: sieci proxy, od których brany jest adres klienta z `X-Forwarded-For` (blokada logowania, US-006);
  puste = jak dotąd (sieci prywatne).
- Weryfikacja dwuetapowa (TOTP, `django-otp`): obowiązkowa dla Administratorów, opcjonalna dla pozostałych; hasła kont
  uprzywilejowanych ≥ 12 znaków; `manage.py two_factor_reset <login>` (US-017). **Uwaga przy wdrożeniu:** Administratorzy
  po pierwszym logowaniu konfigurują aplikację uwierzytelniającą; `DJANGO_SUPERUSER_PASSWORD` musi mieć ≥ 12 znaków.
- CSP wymuszana: skrypty tylko z serwera albo z jednorazowym nonce, bez `'unsafe-inline'`/`'unsafe-eval'` dla
  skryptów, `object-src 'none'`, `form-action 'self'`; obsługa zdarzeń w atrybutach zastąpiona `core/js/ui.js` (US-005).
  **Uwaga przy wdrożeniu:** `CSP_REPORT_ONLY=true` w środowisku zostawia tryb raportu — ustaw `false` albo usuń zmienną.
- CSP także dla stylów bez `'unsafe-inline'` (`style-src 'self' 'nonce-…'`): 360 atrybutów `style=` w 52 szablonach
  zastąpione klasami `core/utilities.css`, kolory i szerokości z danych przez `data-color`/`data-pct` (`core/js/ui.js`),
  bloki `<style>` z nonce, dymki ECharts w trybie `richText`. Przy okazji paski udziałów segmentów ML pokazują właściwą
  szerokość — wcześniej przecinek dziesiętny („12,0%”) unieważniał regułę `width` i pasek miał pełną długość (R-20).
- Adres klienta do blokady logowania z nagłówka `X-Forwarded-For` tylko od proxy w sieci wewnętrznej (US-006).
- Ostrzeżenie w logach i baner dla Administratora, gdy demo publiczne działa na instancji z danymi spoza demo (US-011);
  wejście gościa jest wtedy zablokowane (R-02, decyzja PO).
- Obraz produkcyjny bez narzędzia `pip` — skan trivy wykazał w nim 4 podatności wysokie w bibliotekach
  wbudowanych w `pip`; aplikacja ich nie używa, a instalację zależności wykonuje `uv` na etapie budowy.
- Własny model sprzętu edytuje i usuwa tylko jego autor albo Administrator; import z pliku nie nadpisuje
  cudzego modelu (US-001). Uwaga przy wdrożeniu: modele bez autora (np. dodane w panelu administracyjnym albo
  po usunięciu konta autora) może odtąd zmieniać tylko Administrator.
- Stanowisko renderujące odmawia połączenia bez HTTPS z serwerem innym niż lokalny, żeby token nie szedł
  otwartym tekstem (US-003).
  Uwaga przy wdrożeniu: stanowisko łączące się dotąd po `http://` z adresem w sieci lokalnej musi przejść na `https://`.
- Symulację dnia i kalibrację uruchamia tylko Projektant (i Administrator); Podgląd i gość widzą wynik
  policzony wcześniej (Z-3, R-07).
- Login operatora w historii zadań magazynowych zastępowany pseudonimem „OP-…” przy imporcie i podglądzie
  (US-012, R-06). Ślad symulacji dla animacji 3D też liczy tylko Projektant (luka Z-3 znaleziona przy US-007). **Uwaga przy wdrożeniu:** migracja `twin 0008` nieodwracalnie zastępuje loginy już zapisane —
  przed wdrożeniem kopia zapasowa bazy. Zmiana `SECRET_KEY` zmienia pseudonimy nowych importów.
- Kontener działa jako użytkownik `app` od startu (`USER` w Dockerfile). **Uwaga przy wdrożeniu:** katalog
  hosta montowany jako wolumen (media, baza SQLite) musi należeć do UID 10001; wolumeny używane dotąd już
  są jego własnością (dotychczasowy start zmieniał właściciela).
