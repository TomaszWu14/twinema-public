# Model danych — widok techniczny

**[DEV]** · Pełny model (ERD w 4 obszarach, słownik encji z cyklem życia, glosariusz, skutki usuwania, reguły
integralności) jest w [02-dane/model-danych.md](../02-dane/model-danych.md) — jedno źródło prawdy.
Ten plik zbiera zasady techniczne i zasady zmian.

## Zasady

- **ORM Django, migracje w repozytorium.** CI sprawdza `makemigrations --check`; migracje danych (`RunPython`)
  zakładają klasy systemowe sprzętu i stawki domyślne.
- **Klucze integracji jako tekst** (kod materiału, kod lokalizacji) bez kluczy obcych — pliki wgrywa się
  niezależnie ([D9](../05-decyzje-i-ograniczenia.md#d9-klucze-integracji-jako-tekst-zamiast-kluczy-obcych)).
- **Pola JSON** dla struktur zmiennych (slajdy, wynik symulacji, geometria działki, warianty) — walidowane w
  aplikacji, nie w bazie.
- **Kaskady usuwania** opisane w [skutkach usuwania](../02-dane/model-danych.md#skutki-usuwania);
  zmiana zachowania kaskady = ADR.
- **Autor obiektu** (`created_by`, `uploaded_by`) — klucz do konta z `SET_NULL`; dla własnych modeli sprzętu
  autor decyduje o prawie edycji ([ADR-0003](adr/0003-wlasnosc-modeli-sprzetu.md)).

## Zmiany w modelu danych

1. Opis zmiany w `02-dane/model-danych.md` (ERD, słownik, skutki usuwania) przed kodem.
2. [SEC] ocenia klasę nowych danych ([klasyfikacja](../bezpieczenstwo/KLASYFIKACJA_DANYCH.md)).
3. Migracja odwracalna, jeśli to możliwe; migracja danych z funkcją odwrotną albo `noop` z uzasadnieniem.
4. Uruchamianie migracji na danych produkcyjnych tylko za zgodą PO, po kopii zapasowej ([RUNBOOK](../operacje/RUNBOOK.md)).
