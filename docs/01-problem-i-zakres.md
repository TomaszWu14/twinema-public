# 01. Problem i zakres

## Problem

Decyzja o budowie albo przebudowie magazynu zapada **bez wizualizacji**. Projektant ma dane
z systemu magazynowego (eksporty do arkuszy) i płaski rzut hali. Zarząd, który zatwierdza
inwestycję, nie widzi, jak hala będzie działać w zwykły i w szczytowy dzień, ani gdzie
powstaną kolejki aut, braki ludzi czy wózków.

Pytania, na które przed TWINEMA nie było jednego narzędzia:

| Pytanie | Kto pyta |
|---|---|
| Czy regały, doki i drogi zmieszczą się w hali i na działce, zgodnie z ograniczeniami? | Projektant |
| Czy ten układ obsłuży dzień szczytowy? Gdzie będzie wąskie gardło? | Projektant, zarząd |
| Ilu ludzi i wózków potrzeba na zmianę? | Projektant, kierownik operacji |
| Który z dwóch układów jest lepszy przy tych samych wolumenach? | Zarząd |
| Jak to pokazać komuś, kto nie czyta arkuszy? | Projektant → zarząd |

\<DO UZUPEŁNIENIA: jak wyglądała praca przed — narzędzia, czas przygotowania jednego wariantu,
przykład sytuacji, w której brak wizualizacji był problemem. Na podstawie wywiadu: „był brak” —
narzędzia do wizualizacji i symulacji nie było.\>

## Interesariusze

| Interesariusz | Potrzeba | Rola w systemie |
|---|---|---|
| Projektant magazynu | szybko zbudować i sprawdzić wariant układu na realnych wolumenach | `Projektant` |
| Zarząd | zobaczyć wynik i zrozumieć ryzyko bez danych źródłowych | `Podgląd` albo publiczny link |
| Administrator | zarządzać kontami i katalogiem systemowym sprzętu | `Administratorzy` |
| Osoba oceniająca projekt z zewnątrz (rekruter) | ocenić rozwiązanie bez instalacji | `Podgląd` (konto demo) |

Zarząd i rekruter to odbiorcy zakładani w projekcie (persony), nie zweryfikowani w badaniu.

## W zakresie

| Obszar | Co system robi | Dokument |
|---|---|---|
| Dane | import materiałów, mastera lokalizacji i stanów z plików xlsx/csv z raportem odrzuceń | [02](02-proces.md), [05](05-wymagania.md) |
| Historia ruchów | import zadań magazynowych z eksportu SAP EWM, profil dnia, dzień projektowy P90/P95/P99 | [02](02-proces.md) |
| Model hali | generator, import z pliku, edytor layoutu 2D/3D z walidacją na żywo, działka | [03](03-user-flow.md), [04](04-model-danych.md) |
| Scenariusz | wolumeny dnia typowego i szczytowego (min/śr/max), obsada zmian, normy, flota | [04](04-model-danych.md) |
| Symulacja | dzień pracy na wybranym układzie, KPI średnia + P95, wąskie gardła z podpowiedzią | [05](05-wymagania.md) |
| Porównanie | układ × scenariusz, eksport xlsx | [03](03-user-flow.md) |
| Prognoza | wzrost wolumenów (Holt-Winters i modele bazowe, MAPE), segmentacja SKU | [05](05-wymagania.md) |
| Katalog sprzętu | wózki, AGV/AMR: prędkości, udźwig z krzywą, wymagana alejka, koszty | [04](04-model-danych.md) |
| Pokaz | prezentacja 3D ze slajdami, link dla roli Podgląd i publiczny link z datą ważności | [03](03-user-flow.md) |
| Film (opcjonalnie) | tekst → render w Blenderze → montaż z napisami w obrazie → MP4 + deck PDF | [07](07-ograniczenia.md) |

## Poza zakresem i dlaczego

| Czego system nie robi | Dlaczego |
|---|---|
| Integracja na żywo z systemem magazynowym | dane płyną wyłącznie przez importy plików — brak zależności od systemu źródłowego ([decyzja D1](06-decyzje.md#d1-dane-tylko-z-plików-bez-integracji-na-żywo)) |
| Sterowanie pracą magazynu (zlecenia, potwierdzenia) | to narzędzie projektowe, nie WMS |
| Projekt budowlany, konstrukcja, przepisy przeciwpożarowe w pełnym zakresie | system sprawdza tylko ograniczenia potrzebne do oceny układu (wysokość, drogi pożarowe jako strefa bez regałów, linie zabudowy) |
| Optymalizacja automatyczna (system sam proponuje najlepszy układ) | system ocenia warianty narysowane przez projektanta i podpowiada, co dodać przy wąskim gardle |
| Dokładne koszty inwestycji | koszty są widełkami min–max ze stawek syntetycznych |
| Samodzielna rejestracja i odzyskiwanie hasła | konta zakłada administrator |
| Interfejs w innym języku niż polski | przyjęta zasada projektu „UI i teksty po polsku”; \<DO UZUPEŁNIENIA: powód\> |

Znane braki i problemy: [07-ograniczenia.md](07-ograniczenia.md).
