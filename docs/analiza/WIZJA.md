# Wizja produktu

**[BA]** · wersja 0.1 · status: do potwierdzenia przez PO (pytania na końcu)

## Problem

Decyzja o budowie albo przebudowie magazynu zapada bez działającego modelu: projektant ma eksporty z systemu
magazynowego i płaski rzut hali, a zarząd nie widzi, jak hala zachowa się w zwykły i szczytowy dzień, ani gdzie
powstaną kolejki aut, braki ludzi czy wózków. Opis pracy przed wdrożeniem nie jest udokumentowany ([Z-1](../00-przeglad.md#założenia-wymagające-potwierdzenia)).

## Cel

TWINEMA pozwala zaprojektować i sprawdzić układ magazynu, zanim zapadnie decyzja inwestycyjna: łączy dane
obecnego magazynu z modelem hali 2D/3D, symuluje dzień typowy i szczytowy, wskazuje wąskie gardła, obsadę,
flotę i widełki kosztów, a wynik pokazuje decydentom w przeglądarce bez danych źródłowych.

## Użytkownicy

| Użytkownik | Potrzeba | Rola w systemie |
|---|---|---|
| Projektant magazynu | szybko zbudować i sprawdzić wariant na realnych wolumenach | Projektant |
| Zarząd / decydent | zobaczyć wynik i ryzyko bez czytania arkuszy | Podgląd albo link publiczny |
| Administrator | zarządzać kontami i katalogiem systemowym | Administrator |
| Osoba z zewnątrz (np. rekruter, audytor) | ocenić rozwiązanie bez instalacji | gość demo |

Szczegóły: [INTERESARIUSZE.md](INTERESARIUSZE.md).

## Zakres

Zakres i to, czego system świadomie nie robi: [00-przeglad.md](../00-przeglad.md#zakres).

## Mierniki sukcesu — propozycja do potwierdzenia

W kodzie nie ma zapisanych mierników. [BA] proponuje poniższe jako punkt wyjścia; wartości docelowe ustala PO
([Z-27](ZALOZENIA.md)).

| Nr | Miernik | Jak mierzyć | Wartość docelowa |
|---|---|---|---|
| M-1 | Czas przygotowania jednego wariantu układu z symulacją | od wgrania danych do wyniku P95 | do ustalenia (dziś nieznany — Z-1) |
| M-2 | Liczba wariantów porównanych przed decyzją | porównania w systemie na projekt | do ustalenia |
| M-3 | Odsetek decyzji poprzedzonych pokazem 3D | prezentacje udostępnione na projekt | do ustalenia |
| M-4 | Błędy układu wykryte przed budową | błędy walidacji usunięte w edytorze | do ustalenia |
| M-5 | Zgodność symulacji z rzeczywistością | różnica KPI symulacji obecnej hali i historii (kalibracja) | do ustalenia |

## Pytania [BA] do PO — seria 1

1. Kto jest docelowym użytkownikiem poza autorem: jedna firma (wewnętrzne narzędzie), klienci (usługa) czy portfolio?
2. Które mierniki sukcesu są dla Ciebie ważne i jakie wartości docelowe?
3. Jakie są priorytety na najbliższy miesiąc: bezpieczeństwo i porządki z audytu, nowe funkcje projektowe czy film?
4. Czy obiekty (hale, scenariusze, prezentacje) mają być wspólne dla wszystkich Projektantów, czy prywatne dla autora?
5. Czy przetwarzanie loginów operatorów z historii zadań jest potrzebne, czy pseudonimizujemy je przy imporcie?
