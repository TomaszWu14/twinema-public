# Strategia testów

**[DEV]** z udziałem [BA] (kryteria akceptacji) i [SEC] (testy bezpieczeństwa) · wersja 0.1

## Piramida testów

| Poziom | Co testujemy | Narzędzie | Gdzie | Stan |
|---|---|---|---|---|
| Jednostkowe — logika | symulacja, ML, geometria i walidacja układu, importery, napisy filmu (czysty Python) | `unittest` / Django test runner | `web/*/tests/` | szeroko pokryte |
| Jednostkowe — JS | moduły edytora, sceny, odtwarzaczy (czyste funkcje) | `node --test` | `web/twin/tests/js/` | pokryte kluczowe moduły |
| Integracyjne | widoki z bazą: uprawnienia ról, formularze, importy, API stanowiska | Django `TestCase` + klient testowy | `web/*/tests/test_*views*.py`, `core/tests/test_role_matrix.py` | pokryte |
| End-to-end | kluczowe ścieżki w przeglądarce | Playwright (Chromium) | — | **brak** — planowane dla: logowanie → symulacja → prezentacja; demo gościa |
| Bezpieczeństwa | „brak dostępu” dla każdej roli, link publiczny, token stanowiska, scena bez danych źródłowych | Django `TestCase` | `core/tests/test_role_matrix.py`, `scenario/tests/test_public_link.py`, `render/tests/` | pokryte; rozszerzane z każdą historyjką |
| Statyczne | lint, SAST, SCA, sekrety, kontener | ruff, bandit, semgrep, pip-audit, gitleaks, trivy | CI | [ADR-0002](../architektura/adr/0002-narzedzia-jakosci-i-bezpieczenstwa.md) |

## Zasady

- **Każde kryterium akceptacji ma test** — także kryteria bezpieczeństwa (np. „Projektant B dostaje 403 przy
  edycji modelu Projektanta A”). Nazwa klasy lub docstring wskazuje historyjkę (`US-nnn`).
- **Macierz roli:** każdy nowy widok dostaje wpis w teście macierzy ról albo własny test 403 dla ról bez uprawnień.
- **Dane testowe syntetyczne**, tworzone w testach; bez danych produkcyjnych i loginów przypominających prawdziwe osoby.
- **Testy deterministyczne:** symulacja z ustalonym ziarnem losowania; czas zamrażany, gdy wynik od niego zależy.
- **Baza w CI:** PostgreSQL (jak produkcja); lokalnie SQLite.
- **Błąd naprawiany testem:** najpierw test odtwarzający błąd, potem poprawka.

## Pokrycie

Raport pokrycia generuje job `coverage` w CI (artefakt `coverage`), konfiguracja w `pyproject.toml`.
Próg nie jest jeszcze egzekwowany — propozycja: **80% dla logiki domenowej** (`scenario/sim`, `ml`,
`twin/layout.py`, `twin/design_*`), bez progu dla widoków; decyzja PO ([Z-28](../analiza/ZALOZENIA.md), US-023).
Wynik pomiaru z audytu: [AUDYT.md](../AUDYT.md#dev-jakość-kodu-testy-architektura).

## Uruchomienie

Polecenia: [CONTRIBUTING.md](../../CONTRIBUTING.md#narzędzia-i-uruchomienie-lokalne).
