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
- Procedura czyszczenia historii repozytorium (`docs/operacje/CZYSZCZENIE_HISTORII.md`, R-01) — wykonuje PO.

### Security
- Adres klienta do blokady logowania z nagłówka `X-Forwarded-For` tylko od proxy w sieci wewnętrznej (US-006).
- Ostrzeżenie w logach i baner dla Administratora, gdy demo publiczne działa na instancji z danymi spoza demo (US-011).
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
  (US-012, R-06). **Uwaga przy wdrożeniu:** migracja `twin 0008` nieodwracalnie zastępuje loginy już zapisane —
  przed wdrożeniem kopia zapasowa bazy. Zmiana `SECRET_KEY` zmienia pseudonimy nowych importów.
- Kontener działa jako użytkownik `app` od startu (`USER` w Dockerfile). **Uwaga przy wdrożeniu:** katalog
  hosta montowany jako wolumen (media, baza SQLite) musi należeć do UID 10001; wolumeny używane dotąd już
  są jego własnością (dotychczasowy start zmieniał właściciela).
