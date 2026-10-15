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
- Komunikat po usunięciu sprzętu podaje, ile grup floty mieszanej usunięto razem z nim (US-002).
- ADR przeniesione do `docs/architektura/adr/`.

### Security
- Własny model sprzętu edytuje i usuwa tylko jego autor albo Administrator; import z pliku nie nadpisuje
  cudzego modelu (US-001). Uwaga przy wdrożeniu: modele bez autora (np. dodane w panelu administracyjnym albo
  po usunięciu konta autora) może odtąd zmieniać tylko Administrator.
- Stanowisko renderujące odmawia połączenia bez HTTPS z serwerem innym niż lokalny, żeby token nie szedł
  otwartym tekstem (US-003).
  Uwaga przy wdrożeniu: stanowisko łączące się dotąd po `http://` z adresem w sieci lokalnej musi przejść na `https://`.
