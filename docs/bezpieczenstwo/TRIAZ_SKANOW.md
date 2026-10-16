# Triaż skanów semgrep i trivy

**[SEC]** · US-014, R-18 · przegląd: 2026-10-16 · następny przegląd: 2027-01-31

Przed przełączeniem semgrep i trivy w tryb blokujący [SEC] ocenił każde ustalenie z pierwszych
przebiegów w CI. Zasada: ustalenie się **poprawia**. Wyjątek jest dopuszczalny tylko jako fałszywy alarm
z uzasadnieniem i decyzją PO, nigdy jako obniżenie wymagań.

## Wynik triażu

| Narzędzie | Reguła | Miejsca | Ocena | Działanie |
|---|---|---|---|---|
| semgrep | `github-actions` — akcje przypięte tagiem | workflow CI | prawdziwe (R-16) | akcje przypięte skrótem commita (US-018) |
| semgrep | `dependabot-missing-cooldown` | `.github/dependabot.yml` (3) | prawdziwe | okres karencji 7 dni dla nowych wydań |
| semgrep | `missing-user-entrypoint` | `Dockerfile` | prawdziwe w zapisie — aplikacja schodziła do `app` przez `gosu`, ale kontener startował jako root | `USER app` w obrazie (decyzja PO) |
| trivy | DS-0002 (brak `USER`) | `Dockerfile` | jak wyżej | jak wyżej |
| semgrep | `django-no-csrf-token` | 10 formularzy w 6 szablonach | **fałszywy alarm** — każdy z tych formularzy ma `{% csrf_token %}`; reguła tekstowa nie obejmuje długich formularzy z pętlami | reguła wyłączona w CI (decyzja PO); zastępuje ją test `core/tests/test_csrf_forms.py`, który sprawdza token w każdym formularzu POST |
| trivy | obraz: podatności wysokie i krytyczne | — | 0 po usunięciu `pip` z obrazu (R-19) | — |

## Tryb blokujący

- **semgrep** (`--error`): każde nowe ustalenie z reguł OWASP Top 10 i Django blokuje PR.
- **trivy config**: każde ustalenie w `Dockerfile` blokuje PR.
- **trivy image**: podatność wysoka lub krytyczna z dostępną poprawką blokuje PR.

## Jak postąpić z nowym ustaleniem

1. Poprawić kod albo konfigurację — domyślna ścieżka.
2. Fałszywy alarm: komentarz `nosemgrep: <pełny identyfikator reguły>` w danej linii z uzasadnieniem
   obok, wpis w tabeli powyżej, decyzja PO w opisie PR. Wyłączenie całej reguły — tylko z kontrolą zastępczą
   (test) i decyzją PO.
3. Podatność w obrazie bez możliwości aktualizacji: eskalacja do PO (rejestr ryzyk), nie wyciszenie.
