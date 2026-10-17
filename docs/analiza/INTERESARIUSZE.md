# Interesariusze

**[BA]** · wersja 0.1 · interesariusze zakładani na podstawie ról w kodzie, niezweryfikowani w wywiadach
([Z-2](../00-przeglad.md#założenia-wymagające-potwierdzenia)).

| Interesariusz | Interes / potrzeba | Wpływ | Zaangażowanie | Kontakt z systemem |
|---|---|---|---|---|
| Product Owner | wartość produktu, priorytety, akceptacja ryzyk | wysoki | decyduje | wszystkie role |
| Projektant magazynu | sprawny model hali i wiarygodna symulacja | wysoki | użytkownik kluczowy | rola Projektant |
| Zarząd / decydent inwestycji | zrozumiały wynik i ryzyko, bez danych źródłowych | wysoki | odbiorca | rola Podgląd, link publiczny |
| Administrator systemu | bezpieczny dostęp, konta, katalog systemowy | średni | utrzymuje | rola Administrator, panel administracyjny |
| Kierownik operacji magazynu | obsada zmian i flota zgodne z rzeczywistością | średni | konsultuje założenia scenariusza | pośrednio (wyniki) |
| Pracownicy magazynu (operatorzy) | ochrona ich danych osobowych w historii zadań | niski wpływ, wysoki interes | informowani | dane w imporcie zadań ([RODO](../bezpieczenstwo/RODO.md)) |
| Dział IT / właściciel systemu magazynowego | poprawne eksporty, brak obciążenia systemu źródłowego | średni | dostarcza dane | pośrednio (pliki) |
| Inspektor ochrony danych (jeśli wyznaczony) | zgodność z RODO | średni | opiniuje | — |
| Osoba z zewnątrz (rekruter, audytor) | ocena dojrzałości rozwiązania i procesu | niski | obserwuje | gość demo, repozytorium |

## Macierz RACI dla kluczowych decyzji

R — wykonuje, A — zatwierdza, C — konsultowany, I — informowany.

| Decyzja | PO | BA | DEV | SEC | Projektant | Zarząd |
|---|---|---|---|---|---|---|
| Zakres i priorytety backlogu | A | R | C | C | C | I |
| Wymagania i kryteria akceptacji | A | R | C | C | C | — |
| Architektura i ADR | A | C | R | C | — | — |
| Akceptacja ryzyka bezpieczeństwa | A | I | C | R | — | — |
| Wydanie i merge | A | C | R | C | I | I |
| Wybór układu hali do inwestycji | C | — | — | — | R | A |
