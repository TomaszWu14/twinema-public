# Polityka bezpieczeństwa

## Zgłaszanie podatności

Podatności **nie zgłaszaj w publicznym issue**. Użyj prywatnego zgłoszenia w GitHubie:
zakładka **Security → Report a vulnerability** w tym repozytorium (GitHub Private Vulnerability Reporting).
Kontakt alternatywny: ustala Product Owner ([Z-22](docs/analiza/ZALOZENIA.md)).

W zgłoszeniu podaj: wersję lub commit, opis problemu, kroki odtworzenia i możliwy wpływ. Nie dołączaj danych
osobowych ani danych firmowych.

| Etap | Termin docelowy |
|---|---|
| Potwierdzenie przyjęcia | 3 dni robocze |
| Wstępna ocena wagi | 7 dni roboczych |
| Poprawka: krytyczna / wysoka | 14 / 30 dni |
| Poprawka: średnia / niska | najbliższe wydanie / według backlogu |

Terminy są propozycją do potwierdzenia przez PO.

## Wspierane wersje

Wspierana jest wyłącznie najnowsza wersja z gałęzi `main` (jedno wdrożenie, ciągłe dostarczanie).

## Jak dbamy o bezpieczeństwo

- Każdy PR przechodzi przegląd [SEC] według checklisty w [szablonie PR](.github/pull_request_template.md)
  i kontrole automatyczne: gitleaks, pip-audit, bandit (blokujące), semgrep i trivy (raport) —
  [CONTRIBUTING.md](CONTRIBUTING.md#narzędzia-i-uruchomienie-lokalne).
- Dokumenty: [klasyfikacja danych](docs/bezpieczenstwo/KLASYFIKACJA_DANYCH.md),
  [threat model](docs/bezpieczenstwo/THREAT_MODEL.md), [rejestr ryzyk](docs/bezpieczenstwo/RYZYKA.md),
  [RODO](docs/bezpieczenstwo/RODO.md), [checklista ASVS](docs/bezpieczenstwo/CHECKLISTA_ASVS.md).
- Sekrety wyłącznie w zmiennych środowiskowych; [.env.example](.env.example) nie zawiera wartości.
- Do usługi AI trafiają wyłącznie zagregowane liczby, bez danych źródłowych.

## Ujawnianie

Po wdrożeniu poprawki publikujemy opis w [CHANGELOG.md](CHANGELOG.md) (sekcja „Security”) bez szczegółów
umożliwiających atak na niezaktualizowane instalacje.
