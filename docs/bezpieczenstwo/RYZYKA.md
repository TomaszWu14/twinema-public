# Rejestr ryzyk

**[SEC]** · aktualizacja: 2026-10-15 · przegląd rejestru: co miesiąc i przy każdym PR zmieniającym przepływ danych

Skala: wpływ i prawdopodobieństwo 1–3; waga = iloczyn (1–2 niska, 3–4 średnia, 6 wysoka, 9 krytyczna).
Decyzja: **poprawka** (historyjka w backlogu), **akceptacja** (tylko PO, z datą przeglądu), **przeniesienie**, **unikanie**.
Wyjątki od zasad bezpieczeństwa są akceptacją ryzyka i wymagają wpisu tutaj.

| ID | Ryzyko | Wpływ | Prawd. | Waga | Decyzja | Właściciel | Historyjka | Status |
|---|---|---|---|---|---|---|---|---|
| R-01 | Historia repozytorium zawiera dane z rzeczywistego obiektu i prywatny adres e-mail autora (A-8, A-9) | 3 | 3 | **9 krytyczna** | do decyzji PO: przepisanie historii albo nowe repozytorium | PO | US-010 | otwarte |
| R-02 | Demo publiczne włączone na instancji z danymi rzeczywistymi udostępnia je każdemu w roli Podgląd | 3 | 2 | **6 wysoka** | poprawka: ostrzeżenie przy starcie i osobna instancja demo | SEC / DEV | US-011 | otwarte |
| R-03 | Projektant zmieniał i usuwał cudze modele sprzętu | 2 | 2 | 4 średnia | poprawka | DEV | US-001 | **zamknięte** (ten PR) |
| R-04 | CSP tylko w trybie raportu i z `'unsafe-inline'` — słaba druga linia obrony przed XSS | 2 | 2 | 4 średnia | poprawka: wymuszenie CSP po teście UI | DEV / SEC | US-005 | otwarte |
| R-05 | Zaufanie do `X-Forwarded-For` pozwala ominąć blokadę logowania, jeśli aplikacja jest osiągalna z pominięciem proxy | 2 | 2 | 4 średnia | poprawka: konfiguracja liczby zaufanych proxy; do czasu poprawki — port aplikacji niewystawiony | DEV | US-006 | otwarte |
| R-06 | Login pracownika z historii zadań przechowywany i pokazywany w animacji (dane osobowe, możliwa ocena wydajności osób) | 2 | 3 | **6 wysoka** | do decyzji PO: pseudonimizacja przy imporcie albo pominięcie pola | BA / SEC | US-012 | otwarte |
| R-07 | Długie obliczenia w żądaniu; symulację i kalibrację może uruchomić rola Podgląd (także gość demo) zapytaniem GET | 2 | 2 | 4 średnia | poprawka: obliczenia tylko dla Projektanta albo kolejka z limitem | DEV | US-007 | otwarte |
| R-08 | Brak dziennika operacji wrażliwych (usuwanie, udostępnianie linków, import) | 2 | 2 | 4 średnia | poprawka | DEV | US-008 | otwarte |
| R-09 | Auto-merge PR z gałęzi `claude/**` po zielonym CI, bez zatwierdzenia przez człowieka | 2 | 2 | 4 średnia | do decyzji PO: wymagane zatwierdzenie PR w ochronie gałęzi | PO | US-013 | otwarte |
| R-10 | Brak kopii zapasowych bazy i plików | 3 | 2 | **6 wysoka** | poprawka: procedura w [RUNBOOK](../operacje/RUNBOOK.md) + automatyzacja na platformie | DEV | US-009 | otwarte |
| R-11 | Konto Administratora bez drugiego składnika uwierzytelniania | 3 | 1 | 3 średnia | do decyzji PO | SEC | US-017 | otwarte |
| R-12 | Klucz linku publicznego trafia do logów dostępu | 1 | 2 | 2 niska | akceptacja do 2027-01-31 (logi dostępne tylko administratorowi platformy) — **wymaga potwierdzenia PO** | SEC | — | proponowana akceptacja |
| R-13 | Wspólne konto gościa demo — brak rozróżnienia gości | 1 | 2 | 2 niska | akceptacja do 2027-01-31 (dane syntetyczne, tylko odczyt) — **wymaga potwierdzenia PO** | PO | US-016 | proponowana akceptacja |
| R-14 | Zlecenie renderu odrzucane przez serwer wraca do kolejki bez limitu prób | 1 | 2 | 2 niska | poprawka | DEV | US-015 | otwarte |
| R-15 | Brak limitu kosztów usługi AI | 1 | 1 | 1 niska | akceptacja do 2027-01-31 (funkcja opcjonalna, na żądanie Projektanta) — **wymaga potwierdzenia PO** | PO | — | proponowana akceptacja |
| R-16 | Akcje GitHub przypięte tagiem zamiast skrótu commita | 2 | 1 | 2 niska | poprawka: przypięcie skrótów (Dependabot aktualizuje) | DEV | US-018 | otwarte |
| R-17 | Stanowisko renderujące mogło wysłać token po HTTP do zdalnego serwera | 2 | 1 | 2 niska | poprawka | DEV | US-003 | **zamknięte** (ten PR) |
| R-18 | Skany semgrep i trivy na razie tylko raportują — nowe ustalenia nie blokują PR | 2 | 2 | 4 średnia | przejściowo: triaż pierwszych wyników, potem tryb blokujący | SEC | US-014 | otwarte |
