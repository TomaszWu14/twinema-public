# ADR-0003: Własność własnych modeli sprzętu

**Data:** 2026-10-15 · **Status:** przyjęta w US-001, do potwierdzenia PO (Z-26) · **Role:** [BA] + [SEC] + [DEV]

## Kontekst

Każdy Projektant mógł edytować i usuwać własne modele sprzętu innych Projektantów, a import z pliku
aktualizował model po nazwie bez względu na autora. Wcześniejsza analiza oceniła to jako niezamierzone
(R-03). Usunięcie sprzętu kasuje też grupy floty mieszanej scenariuszy, więc cudza zmiana psuje cudze wyniki.

## Rozważane opcje

1. **Autor albo Administrator** zmienia i usuwa własny model; pozostali mogą go oglądać i kopiować.
2. Wszyscy Projektanci jak dotąd (model zespołowy) + dziennik zmian.
3. Pełna własność wszystkich obiektów (hale, scenariusze, prezentacje) według autora.

## Decyzja

Opcja 1, tylko dla własnych modeli sprzętu:
- edycja i usunięcie — autor albo Administrator; model bez autora (konto usunięte) — tylko Administrator;
- import z pliku nie aktualizuje modelu innego autora ani modelu bez autora (wiersz pominięty z powodem);
  Administrator może;
- kopiowanie i podgląd bez zmian (każdy Projektant / każda rola).

Opcji 3 nie wybrano: hale, scenariusze i prezentacje są pracą zespołową ([Z-26](../../analiza/ZALOZENIA.md));
zmiana wymaga decyzji PO.

## Konsekwencje

- Projektant, który chce zmienić cudzy model, robi kopię (zachowanie jak dla klas systemowych).
- Modele osób usuniętych z systemu przechodzą pod Administratora.
- Testy: `equipment/tests/test_equipment.py::OwnModelAuthorizationTests`,
  `equipment/tests/test_import.py::test_import_does_not_overwrite_other_users_model`.
