# Audyt stanu projektu

**Data:** 2026-10-15 · **Zakres:** całe repozytorium (kod, testy, CI, konfiguracja, dokumentacja) ·
**Role:** [BA], [DEV], [SEC] · Metoda: przegląd kodu, uruchomienie testów, bandit, pip-audit, pomiar pokrycia.

## Podsumowanie

| Perspektywa | Ocena | Najważniejsze |
|---|---|---|
| [BA] | dobra dokumentacja funkcji, słaba strona biznesowa | procesy P1–P8 opisane z kodu; brak potwierdzonej wizji, mierników sukcesu, wymagań niefunkcjonalnych i retencji danych |
| [DEV] | dojrzały monolit z dobrym pokryciem testami | 676 testów zielonych, CI z PostgreSQL; długie obliczenia w żądaniu, import w wątku, brak typowania i testów E2E |
| [SEC] | solidne podstawy, kilka luk procesowych i konfiguracyjnych | brak podatności w zależnościach, SAST bez ustaleń wysokich; ryzyka krytyczne/wysokie: historia repozytorium, demo publiczne, dane osobowe operatorów, kopie zapasowe |

## [BA] Co aplikacja robi i czego brakuje w wymaganiach

**Robi:** projektowanie układu magazynu z danymi z plików, symulacja dnia typowego i szczytowego, wąskie
gardła, koszty, prezentacja 3D z linkiem publicznym, film z napisami, demo publiczne — opis w
[00-przeglad.md](00-przeglad.md) i procesach [P1–P8](01-procesy/).

**Braki w wymaganiach:**
1. Brak potwierdzonej wizji i mierników sukcesu — propozycja w [WIZJA.md](analiza/WIZJA.md), do decyzji PO.
2. Brak opisu stanu obecnego (AS-IS) i uzasadnienia biznesowego (Z-1).
3. Wymagania niefunkcjonalne tylko te wynikające z kodu; brak wydajności, dostępności, RPO/RTO (NFR-012–017).
4. Brak decyzji o własności obiektów (wspólne czy prywatne dla autora) — Z-26.
5. Brak podstawy prawnej i retencji danych osobowych, w tym loginów operatorów w historii zadań ([RODO](bezpieczenstwo/RODO.md)).
6. UX: ślepe ścieżki dla roli Podgląd, usuwanie bez potwierdzenia, utrata danych formularza po błędzie
   ([znane ograniczenia](05-decyzje-i-ograniczenia.md#znane-ograniczenia)).

## [DEV] Jakość kodu, testy, architektura

| Obszar | Stan | Uwagi |
|---|---|---|
| Architektura | ✅ | monolit Django 5.2 LTS, 8 aplikacji z czytelnym podziałem; logika obliczeniowa bez bazy ([ARCHITEKTURA](architektura/ARCHITEKTURA.md)) |
| Testy | ✅ | 676 testów Python + testy JS, CI na PostgreSQL; testy ról i 403 |
| Pokrycie | ⚠️ | pomiar w tym PR: **92,7%** łącznie (linie i gałęzie), logika domenowa (`scenario/sim`, `ml`, `twin/layout.py`, `twin/design_*`) ok. **97%**; najsłabiej: stanowisko renderujące (23%); brak progu w CI (Z-28) |
| Lint | ⚠️ | ruff z wąskim zestawem reguł (F, E9, B); brak formatowania i typowania |
| Konfiguracja | ✅ | typowane zmienne środowiskowe, walidacja przy starcie |
| Kontener | ✅ | obraz slim, wieloetapowy, użytkownik nie-root, przypięte wersje zależności |
| Wydajność | ⚠️ | symulacja, import danych, ML i szkic AI w trakcie żądania (limit 120 s); import zadań w wątku procesu |
| CI/CD | ⚠️ | brakowało SAST, skanu kontenera i Dependabota (dodane w tym PR); auto-merge gałęzi `claude/**` bez zatwierdzenia |
| Operacje | ❌ | brak kopii zapasowych i procedury odtworzenia (dodana procedura w [RUNBOOK](operacje/RUNBOOK.md)) |
| Testy E2E | ❌ | brak testów w przeglądarce dla kluczowych ścieżek |

Dług techniczny: T-1…T-16 w [05-decyzje-i-ograniczenia.md](05-decyzje-i-ograniczenia.md#dług-techniczny-i-prace-przed-wdrożeniem-produkcyjnym).

## [SEC] Top 10 ryzyk

| Nr | Ryzyko | Waga | Rejestr | Działanie |
|---|---|---|---|---|
| 1 | Historia repozytorium zawiera dane rzeczywistego obiektu i prywatny e-mail autora | **krytyczna** | R-01 | decyzja PO: przepisanie historii albo nowe repozytorium (US-010) |
| 2 | Demo publiczne na instancji z danymi rzeczywistymi udostępnia je każdemu | **wysoka** | R-02 | osobna instancja demo, ostrzeżenie przy starcie (US-011) |
| 3 | Login pracownika magazynu w historii zadań — dane osobowe bez minimalizacji | **wysoka** | R-06 | decyzja PO: pseudonimizacja przy imporcie (US-012) |
| 4 | Brak kopii zapasowych | **wysoka** | R-10 | procedura dodana; automatyzacja (US-009) |
| 5 | Projektant zmieniał i usuwał cudze modele sprzętu (kontrola dostępu do obiektu) | średnia | R-03 | **naprawione** w tym PR (US-001) |
| 6 | CSP tylko w trybie raportu, z `'unsafe-inline'` | średnia | R-04 | wymuszenie po teście UI (US-005) |
| 7 | Zaufanie do `X-Forwarded-For` — obejście blokady logowania przy pominięciu proxy | średnia | R-05 | konfiguracja zaufanych proxy (US-006) |
| 8 | Długie obliczenia uruchamiane GET-em także przez rolę Podgląd / gościa | średnia | R-07 | obliczenia tylko dla Projektanta albo kolejka (US-007) |
| 9 | Brak dziennika operacji wrażliwych | średnia | R-08 | US-008 |
| 10 | Auto-merge bez zatwierdzenia człowieka | średnia | R-09 | decyzja PO: wymagane zatwierdzenie (US-013) |

Naprawione również: stanowisko renderujące mogło wysłać token po HTTP (R-17, US-003).

**Mocne strony:** escapowanie wyjścia (szablony, `safe_json`, `textContent`); parsowanie XLSX przez defusedxml;
token stanowiska porównywany w stałym czasie i jednorazowy klucz przejęcia; link publiczny z 24 losowymi bajtami,
datą ważności i nagłówkami `noindex` / `no-referrer` / `no-store`; HSTS, ciasteczka `Secure`; blokada zgadywania
haseł; scena dla Podglądu bez danych źródłowych; do AI tylko zagregowane liczby; sekrety wyłącznie w zmiennych
środowiskowych.

## Wyniki narzędzi

| Narzędzie | Wynik |
|---|---|
| pip-audit 2.9.0 (`requirements.txt`) | brak znanych podatności |
| bandit 1.8.6 (`web/`, `tools/`, bez testów i migracji) | 0 wysokich; 3 średnie — oceniono jako fałszywe alarmy lub naprawiono (B310: dodano ograniczenie schematu), oznaczone pojedynczo; 19 niskich (generatory losowe w symulacji i danych demo, `assert` w ML, `subprocess` w stanowisku) — bez działań |
| Testy (Django, SQLite) | 676 / 676 zielonych przed zmianami; **686 / 686** po zmianach (10 nowych testów US-001…US-003) |
| semgrep, trivy | nie uruchomiono lokalnie (brak dostępu do rejestru reguł i demona Dockera); w CI tego PR: semgrep — raport w artefakcie; trivy — system bazowy 0 podatności, 4 × HIGH w bibliotekach wbudowanych w `pip` → `pip` usunięty z obrazu (R-19) |

## Kolejne kroki

Backlog z priorytetami: [HISTORYJKI.md](analiza/HISTORYJKI.md). Decyzje wymagane od PO: [ZALOZENIA.md](analiza/ZALOZENIA.md)
i pytania w [WIZJA.md](analiza/WIZJA.md#pytania-ba-do-po--seria-1).
