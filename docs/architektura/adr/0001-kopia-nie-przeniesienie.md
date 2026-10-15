# ADR-0001: Kopia kodu modelowania magazynu, nie przeniesienie

**Data:** 2026-10-05 · **Status:** przyjęta

## Kontekst
Kod modelowania hali, symulacji i eksportu do Blendera powstał w innym, działającym
produkcyjnie repozytorium. TWINEMA ma się skupić wyłącznie na projektowaniu magazynu,
animacji przepływów i prezentacjach.

## Decyzja
Kopiujemy potrzebne moduły do TWINEMA (czysta historia, pochodzenie w `PROVENANCE.md`).
Repozytorium źródłowe zostaje nietknięte. Dane płyną wyłącznie przez importy plików.
Wspólnej biblioteki nie tworzymy, dopóki oba repo nie edytują realnie tych samych plików.

## Skutki
- Źródło działa dalej bez zmian; brak zależności między wdrożeniami.
- Poprawki w kopiowanym kodzie nie wracają automatycznie — nowe prace projektowe toczą się tylko w TWINEMA.
- Z kopiowanego kodu usuwamy odniesienia do konkretnych firm i lokalizacji.
