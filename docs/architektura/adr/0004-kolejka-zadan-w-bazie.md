# ADR-0004: Kolejka zadań w bazie danych

**Data:** 2026-10-16 · **Status:** przyjęta (decyzja PO) · **Role:** [DEV] + [SEC] + [BA]

## Kontekst

Symulacja dnia, kalibracja i symulacja scenariusza liczyły się w trakcie żądania HTTP, przy limicie serwera
120 s (R-07, T-1). Duży import zadań magazynowych działał w wątku procesu web i ginął przy restarcie
kontenera, a partia zostawała „w tle” bez ponowienia (T-2). Wynik symulacji trzymała pamięć podręczna jednego
procesu, więc inny proces gunicorna liczył ten sam dzień od nowa.

## Rozważane opcje

1. **Kolejka w istniejącej bazie** (tabela zadań) i proces `manage.py run_jobs` uruchamiany obok serwera.
2. **Celery + Redis**: standard branżowy, wymaga nowej usługi Redis i osobnego kontenera workera.
3. Bez zmian: wątki w procesie web.

## Decyzja

Opcja 1 (decyzja PO z 2026-10-16):
- model `core.Job`: rodzaj, parametry, stan (w kolejce / w toku / gotowe / błąd), liczba prób, wynik JSON;
- pobranie zadania to warunkowa zmiana stanu w bazie, więc kilka workerów nie weźmie tego samego zadania;
- zadanie „w toku” dłużej niż `JOB_STALE_MIN` (domyślnie 60 min) wraca do kolejki, a po 3 próbach kończy się
  błędem;
- `key` (skrót danych i parametrów) sprawia, że ten sam zestaw nie liczy się drugi raz, a wynik odczytuje każda
  rola z dostępem do ekranu (Z-3: zlecić obliczenie może tylko Projektant);
- worker startuje w tym samym kontenerze co serwer (`RUN_WORKER=true`); można go też uruchomić jako osobną
  usługę;
- ekran czekający na wynik sprawdza stan co 5 s, bez meta-refresh (WCAG 2.2.1).

Opcji 2 nie wybrano: przy kilku użytkownikach nie uzasadnia kosztu i utrzymania nowej usługi.

## Konsekwencje

- Do kolejki trafiają: symulacja dnia projektowego, kalibracja, symulacja scenariusza i import zadań większy niż
  5 MB. W trakcie żądania zostają: import danych podstawowych, ML, szkic z AI i ślad symulacji dla animacji 3D
  (T-1, częściowo).
- Komunikaty o wyniku symulacji scenariusza pokazuje karta scenariusza, a nie komunikat po żądaniu.
- Zakończone zadania są usuwane po 7 dniach; wynik liczy się wtedy od nowa.
- Uruchomienie lokalne bez workera: zadania czekają w kolejce. Trzeba uruchomić `python manage.py run_jobs`
  (opis w CONTRIBUTING).
- Przejście na Celery w przyszłości: zmiana dotyczy tylko `core/jobs.py`; widoki zlecają zadania przez `enqueue`.
