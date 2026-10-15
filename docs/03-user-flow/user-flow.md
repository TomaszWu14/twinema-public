# User flow — mapa ekranów i przejść

Mapa ekranów odtworzona z adresów, widoków i szablonów aplikacji. Ekrany mają numery **E-n** pogrupowane
obszarami: E-1…E-9 wejście, E-100 modele hal, E-200 dane podstawowe, E-300 historia ruchów i projektowanie,
E-400 uczenie maszynowe, E-500 sprzęt, E-600 scenariusze, E-700 prezentacje 3D, E-800 film, E-900 render.

**Uprawnienia w skrócie:** „każda rola” = Administrator, Projektant i Podgląd; „Projektant” = Projektant
i Administrator. Szczegóły ról: [P8](../01-procesy/P8-dostep-i-demo.md).

**Wspólne zasady ekranów:**
- wszystkie ekrany są pełnymi stronami (bez okien modalnych);
- pasek nawigacji z 10 modułami jest taki sam dla każdej roli — rola Podgląd widzi też moduły, które
  dają jej stronę braku uprawnień ([ograniczenia](../05-decyzje-i-ograniczenia.md#znane-ograniczenia));
- strzałka na diagramie = akcja użytkownika; linia przerywana = przejście przez link skopiowany poza system.

## Mapa obszarów

```mermaid
flowchart LR
    W([Wejście i demo]) --> START[E-2 Start]
    START --> HAL[Modele hal E-100]
    START --> DAT[Dane podstawowe E-200]
    START --> HIS[Historia ruchów E-300]
    START --> ML[Uczenie maszynowe E-400]
    START --> EQ[Sprzęt E-500]
    START --> SC[Scenariusze E-600]
    START --> SH[Prezentacje 3D E-700]
    START --> ST[Film E-800]
    START --> RE[Render E-900]
```

Diagram pokazuje, że wszystkie obszary są dostępne ze strony startowej; szczegóły każdego obszaru — niżej.

## UF-1. Wejście, logowanie i demo publiczne

```mermaid
flowchart LR
    G([Gość]) -->|"adres chroniony"| E1[E-1 Logowanie]
    G -->|"adres demo"| E6[E-6 Strona demo]
    G -->|"aktywny link publiczny"| E702[E-702 Pokaz publiczny]
    G -->|"link nieaktywny"| E404[Strona nie znaleziono]
    E1 -->|"logowanie poprawne"| E2[E-2 Start]
    E1 -->|"błędne dane"| E1
    E1 -->|"5 błędów w 1 h"| E5[E-5 Blokada logowania]
    E1 -->|"wersja demo"| E6
    E6 -->|"obejrzyj pokaz"| E702
    E6 -->|"wejdź jako gość"| E2
    E2 -->|"moduł bez uprawnień"| E3[E-3 Brak dostępu]
    E3 -->|"wróć na start"| E2
    E2 -->|"wyloguj"| E1
```

Gość bez konta ma trzy drogi: logowanie, publiczny pokaz z linku albo strona demo. „Wejdź jako gość” jest
widoczne tylko przy włączonym demo publicznym i loguje na konto demo z rolą Podgląd.

## UF-2. Modele hal — tworzenie i edycja

```mermaid
flowchart LR
    E100[E-100 Projektowanie] --> E101[E-101 Modele magazynu]
    E100 --> E103[E-103 Generator hali]
    E101 -->|"nowy model z pliku"| E102[E-102 Nowy model]
    E101 --> E103
    E101 -->|"edytor"| E109[E-109 Edytor układu]
    E101 -->|"kopia jako przyszły layout"| E109
    E101 -->|"usuń"| E110[E-110 Usunięcie modelu]
    E102 -->|"plik kodów"| E104[E-104 Współrzędne regałów]
    E102 -->|"plik geometrii"| E106[E-106 Wizualizacja]
    E103 -->|"utwórz"| E106
    E104 -->|"wklej adresy"| E105[E-105 Wklej adresy]
    E105 -->|"ustaw regały"| E104
    E104 -->|"zapisz lub pomiń"| E106
    E109 -->|"zobacz animację"| E106
    E110 -->|"potwierdź"| E101
```

Model hali powstaje generatorem (E-103) albo z pliku (E-102). Plik kodów lokalizacji prowadzi przez
rozmieszczenie regałów (E-104, E-105), plik geometrii — od razu do wizualizacji. Edytor (E-109) przy zapisie
odrzuca plan z błędami albo zmieniony równolegle przez inną osobę.

## UF-3. Model hali — ekrany pomocnicze

```mermaid
flowchart LR
    E106[E-106 Wizualizacja] -->|"elementy hali"| E107[E-107 Elementy hali]
    E106 -->|"edycja stref"| E108[E-108 Edycja stref]
    E106 -->|"wykryj z historii"| E111[E-111 Wykrycie układu]
    E106 -->|"zgodność"| E112[E-112 Zgodność adresowania]
    E106 -->|"symuluj scenariusz"| E600[E-600 Scenariusze]
    E106 -->|"renderuj"| E900[E-900 Render]
    E111 -->|"zapisz"| E112
    E112 -->|"wykryj ponownie"| E111
    E101[E-101 Modele magazynu] --> E113[E-113 Typy regałów]
    E113 --> E114[E-114 Typ regału]
    E101 --> E115[E-115 Szablony gniazd]
    E115 --> E116[E-116 Szablon gniazda]
    E100[E-100 Projektowanie] --> E117[E-117 Warianty projektu]
```

Wizualizacja (E-106) jest węzłem, z którego Projektant przechodzi do szczegółowej edycji, odwzorowania
adresowania z mastera lokalizacji, symulacji i renderu. Typy regałów, szablony gniazd i warianty to
katalogi pomocnicze.

## UF-4. Dane podstawowe i katalog sprzętu

```mermaid
flowchart LR
    E200[E-200 Dane] -->|"importuj plik"| E202[E-202 Raport importu]
    E200 -->|"błąd pliku"| E200
    E200 -->|"materiały"| E204[E-204 Materiały]
    E204 -->|"kod materiału"| E205[E-205 Edycja materiału]
    E200 -->|"nośniki i klasy"| E206[E-206 Nośniki i klasy]
    E200 -->|"dane demo"| E106[E-106 Wizualizacja]
    E500[E-500 Katalog sprzętu] -->|"nazwa"| E505[E-505 Karta sprzętu]
    E500 -->|"dodaj model"| E501[E-501 Formularz sprzętu]
    E500 -->|"stawki"| E506[E-506 Stawki kosztowe]
    E500 -->|"import pliku"| E500
    E505 -->|"edytuj lub kopiuj"| E501
    E505 -->|"usuń"| E500
    E501 -->|"zapisz"| E505
```

Import danych zawsze kończy się raportem (E-202). Import sprzętu wraca na listę katalogu z komunikatami.
Usunięcie sprzętu nie ma ekranu potwierdzenia.

## UF-5. Historia ruchów, projektowanie i uczenie maszynowe

```mermaid
flowchart LR
    E300[E-300 Zadania magazynowe] -->|"podgląd pliku"| E301[E-301 Podgląd importu]
    E301 -->|"brak kolumn"| E300
    E301 -->|"importuj cały plik"| E303[E-303 Raport importu zadań]
    E303 -->|"usuń"| E300
    E303 -->|"dzień projektowy"| E306[E-306 Profil i dzień projektowy]
    E306 --> E307[E-307 Symulacja dnia na modelu]
    E306 --> E308[E-308 Kalibracja]
    E306 --> E309[E-309 Porównanie modeli]
    E306 --> E310[E-310 Prognoza wzrostu]
    E308 -->|"symuluj ze współczynnikami"| E307
    E310 -->|"symuluj P50 lub P90"| E307
    E400[E-400 Prognozy i ML] -->|"uruchom"| E402[E-402 Wynik przebiegu]
    E402 -->|"symulacja z mnożnikiem"| E307
```

Import zadań ma dwa kroki: bezpieczny podgląd (bez zapisu) i właściwy import. Duży plik importuje się w tle,
a raport (E-303) sam odświeża status.

## UF-6. Scenariusze i prezentacje 3D

```mermaid
flowchart LR
    E600[E-600 Scenariusze] -->|"utwórz lub wczytaj demo"| E601[E-601 Szczegóły scenariusza]
    E600 -->|"porównanie"| E604[E-604 Porównanie wyników]
    E601 -->|"uruchom symulację"| E601
    E601 -->|"zapisz formularz"| E601
    E601 -->|"animacja dnia"| E603[E-603 Animacja dnia]
    E601 -->|"porównaj"| E604
    E601 -->|"usuń"| E600
    E601 -->|"prezentacja 3D"| E700[E-700 Prezentacje 3D]
    E700 -->|"utwórz ze szablonu"| E701[E-701 Prezentacja i edytor slajdów]
    E701 -->|"zapisz slajdy lub link"| E701
    E701 -->|"usuń"| E700
    E701 -.->|"publiczny link"| E702[E-702 Pokaz publiczny]
```

Scenariusz (E-601) łączy definicję, uruchomienie i wyniki na jednym ekranie. Pokaz publiczny (E-702) otwiera
się z linku przekazanego poza system.

## UF-7. Film i render

```mermaid
flowchart LR
    E800[E-800 Studio] -->|"utwórz"| E801[E-801 Prezentacja filmowa]
    E801 -->|"zapisz tekst lub szkic"| E801
    E801 -->|"zatwierdź tekst"| E801
    E801 -->|"renderuj ujęcia"| E900[E-900 Render 3D]
    E801 -->|"zmontuj film"| E801
    E801 -->|"pobierz plik"| PL([Film, deck, napisy, opis])
    E801 -->|"usuń"| E800
    E900 -->|"dodaj zlecenie lub usuń"| E900
```

Prezentacja filmowa (E-801) przechodzi wszystkie etapy na jednym ekranie; zlecenia renderu są widoczne
także na liście E-900. Ekran sam odświeża status zleceń.

## Opis ekranów

### Wejście

| Ekran | Cel | Wejścia | Akcje | Warunki dostępu |
|---|---|---|---|---|
| E-1 Logowanie | uwierzytelnić użytkownika | login, hasło | zaloguj; link do demo (gdy demo publiczne włączone) | wszyscy |
| E-2 Start | wybrać moduł | — | 10 kafli modułów, nawigacja, wyloguj | zalogowany |
| E-3 Brak dostępu | wyjaśnić brak roli | — | wróć na start | zalogowany bez wymaganej roli |
| E-5 Blokada logowania | zatrzymać zgadywanie hasła | — | brak (strona standardowa biblioteki) | po 5 nieudanych próbach (login + adres IP) przez 1 h |
| E-6 Strona demo | wpuścić osobę z zewnątrz bez hasła | — | obejrzyj pokaz 3D, wejdź jako gość, obejrzyj film | wszyscy; „wejdź jako gość” tylko przy włączonym demo publicznym |
| E-702 Pokaz publiczny | pokazać prezentację 3D bez konta | klucz w adresie | przewijanie slajdów, obrót sceny | aktywny i nieprzeterminowany link |

### Modele hal

| Ekran | Cel | Wejścia | Akcje | Warunki dostępu |
|---|---|---|---|---|
| E-100 Projektowanie | poprowadzić przez kroki projektu | — | kroki 1–7 (kroki 3–7 aktywne po imporcie zadań), warianty | każda rola |
| E-101 Modele magazynu | zarządzać modelami hal | — | generator, nowy model, wizualizacja, edytor, kopia, współrzędne, usuń | lista: każda rola; akcje zmieniające: Projektant |
| E-102 Nowy model | utworzyć model z pliku | nazwa, wymiary hali, plik kodów lokalizacji lub geometrii (≤ 5 MB) | wczytaj | Projektant |
| E-103 Generator hali | utworzyć model z parametrów | 13 parametrów | przelicz, utwórz | Projektant |
| E-104 Współrzędne regałów | rozmieścić regały | X, Y, kąt, szablon, numeracja | zapisz, pomiń, wklej adresy | Projektant |
| E-105 Wklej adresy | utworzyć regały z listy adresów | lista adresów, orientacja, punkt startu | ustaw regały | Projektant |
| E-106 Wizualizacja | obejrzeć model w 3D i 2D | — | animacja przepływów, eksport sceny, przejścia do edycji, symulacji i renderu | każda rola (Podgląd widzi scenę bez danych źródłowych) |
| E-107 Elementy hali | edytować doki, strefy i drogi tabelą | rodzaj, rola doku, położenie, wymiary | zapisz, wróć | Projektant |
| E-108 Edycja stref | przesunąć i przebudować strefy | przesunięcie, gniazda, poziomy | zapisz, usuń strefę | Projektant |
| E-109 Edytor układu | narysować i sprawdzić układ | plan 2D, działka, słupy, podkład | cofnij, ponów, zapisz; problemy i KPI na żywo | Projektant |
| E-110 Usunięcie modelu | potwierdzić usunięcie | — | potwierdź, anuluj | Projektant |
| E-111 Wykrycie układu | zaproponować szablony i rzędy z mastera lokalizacji | — | zapisz | Projektant |
| E-112 Zgodność adresowania | sprawdzić zgodność modelu z masterem | — | eksport xlsx, wykryj ponownie | Projektant |
| E-113 / E-114 Typy regałów | utrzymać wzorce regałów | kod, wymiary, poziomy | nowy, edytuj, usuń | lista: każda rola; zmiany: Projektant |
| E-115 / E-116 Szablony gniazd | utrzymać wzorce adresowania | poziomy: litera, wysokość, typ, podział | nowy, edytuj, usuń | lista: każda rola; zmiany: Projektant |
| E-117 Warianty projektu | porównać warianty KPI | plik wariantu (≤ 5 MB) | porównaj (do 6), importuj, utwórz z modelu, usuń | lista i porównanie: każda rola; zmiany: Projektant |

### Dane podstawowe i sprzęt

| Ekran | Cel | Wejścia | Akcje | Warunki dostępu |
|---|---|---|---|---|
| E-200 Dane | wczytać dane podstawowe | plik materiałów, lokalizacji lub stanów | importuj, pobierz wzór, dane demo, historia importów | ekran: każda rola; import i dane demo: Projektant |
| E-202 Raport importu | pokazać wynik importu | — | — | Projektant (raport zawiera dane źródłowe) |
| E-204 Materiały | przeglądać kartotekę | filtry | otwórz materiał | Projektant |
| E-205 Edycja materiału | poprawić dane materiału | wymiary, cechy, klasy, ABC | zapisz | Projektant |
| E-206 Nośniki i klasy | utrzymać słowniki palet | nośniki, klasy wysokości i wagi | zapisz | Projektant |
| E-500 Katalog sprzętu | przeglądać sprzęt | filtr typu i producenta, plik importu | otwórz, dodaj, importuj, stawki | lista: każda rola; dodawanie i import: Projektant |
| E-501 Formularz sprzętu | wpisać parametry | typ, nazwa, parametry, osprzęt, koszty | zapisz, anuluj | Projektant; edycja własnego modelu: jego autor albo Administrator; klasa systemowa: tylko Administrator |
| E-505 Karta sprzętu | obejrzeć parametry i krzywą udźwigu | — | edytuj, kopiuj, usuń | każda rola; kopiowanie: Projektant; edycja i usuwanie: autor modelu albo Administrator (klas systemowych nie da się usunąć) |
| E-506 Stawki kosztowe | utrzymać widełki kosztów | od, do | zapisz | Projektant |

### Historia ruchów, projektowanie i ML

| Ekran | Cel | Wejścia | Akcje | Warunki dostępu |
|---|---|---|---|---|
| E-300 Zadania magazynowe | wczytać eksport zadań | plik (≤ 300 MB), strefa czasowa, nadpisania mapowania | podgląd pliku, lista importów | Projektant |
| E-301 Podgląd importu | sprawdzić plik przed zapisem | — | importuj cały plik, wgraj inny | Projektant |
| E-303 Raport importu zadań | śledzić import i jego wynik | — | dzień projektowy, animacja, usuń | Projektant |
| E-306 Profil i dzień projektowy | wyznaczyć dzień, na który projektujemy | percentyl P90/P95/P99 | przejścia do symulacji, kalibracji, porównania, prognozy | każda rola |
| E-307 Symulacja dnia na modelu | sprawdzić układ na dniu projektowym | model, mnożnik, flota, kalibracja | symuluj | każda rola |
| E-308 Kalibracja | wyznaczyć normy z historii | model obecnej hali | policz, symuluj ze współczynnikami | każda rola |
| E-309 Porównanie modeli | porównać do 4 modeli na jednym dniu | modele | porównaj | ekran: każda rola; obliczenie: Projektant |
| E-310 Prognoza wzrostu | ocenić przyszły wolumen | horyzont | przelicz, symuluj P50/P90, porównaj | każda rola |
| E-400 Prognozy i ML | uruchomić modele ML | partia, parametry | uruchom prognozę lub segmentację | ekran: każda rola; uruchomienie: Projektant |
| E-402 Wynik przebiegu | obejrzeć prognozę albo segmenty | — | symulacja z mnożnikiem; eksport segmentów | każda rola; eksport segmentów: Projektant |

### Scenariusze, prezentacje, film i render

| Ekran | Cel | Wejścia | Akcje | Warunki dostępu |
|---|---|---|---|---|
| E-600 Scenariusze | zarządzać scenariuszami | nazwa | utwórz, wczytaj demo, porównanie | lista: każda rola; tworzenie: Projektant |
| E-601 Szczegóły scenariusza | zdefiniować dzień, uruchomić symulację, ocenić wynik | przyjęcia, wydania, flota, zmiany, normy, model, dzień, liczba przebiegów | zapisz, uruchom, animacja, kopiuj, usuń | podgląd: każda rola; zmiany i uruchomienie: Projektant |
| E-603 Animacja dnia | zobaczyć przebieg dnia w 3D | tempo ×10–×300 | odtwórz, skok do szczytu, mapa ciepła | każda rola |
| E-604 Porównanie wyników | porównać wyniki obok siebie | do 6 wyników | porównaj, eksport xlsx | każda rola |
| E-700 Prezentacje 3D | utworzyć pokaz | tytuł, model, wynik | utwórz ze szablonu | lista: każda rola; tworzenie: Projektant |
| E-701 Prezentacja i edytor slajdów | przygotować i udostępnić pokaz | slajdy, ujęcia kamery, ważność linku | zapisz, zastąp szablonem, utwórz lub wyłącz link, usuń | oglądanie: każda rola; edycja i link: Projektant |
| E-800 Studio | utworzyć film | model, tytuł | utwórz | lista: każda rola; tworzenie: Projektant |
| E-801 Prezentacja filmowa | przejść od tekstu do filmu | teksty ujęć | szkic z szablonu lub z AI, zatwierdź, wróć do edycji, renderuj, zmontuj, pobierz film, deck, napisy, opis | oglądanie i pobieranie: każda rola; etapy: Projektant |
| E-900 Render 3D | zlecić i śledzić render | model, ujęcie, wynik, rozdzielczość, długość 2–60 s | dodaj do kolejki, usuń, pobierz wynik | lista i pobieranie: każda rola; zlecanie i usuwanie: Projektant |

## Ścieżki alternatywne w nawigacji

| Sytuacja | Zachowanie |
|---|---|
| Gość otwiera dowolny chroniony adres | przekierowanie do E-1; wyjątki: E-6, E-702, adres kontroli działania serwera |
| Zalogowany bez roli | widzi E-2, każdy moduł kończy się E-3 |
| Podgląd otwiera ekran Projektanta | E-3 (także z przycisków i pozycji menu, które są dla niego widoczne) |
| Błąd walidacji formularza | trzy różne zachowania: ten sam ekran z danymi (E-102, E-116, E-205, E-501); powrót z komunikatem i utratą wpisanych danych (E-601, E-108, E-114); cicha korekta (E-104 pomija wiersz, E-107 wstawia wartości domyślne) |
| Opuszczenie ekranu z niezapisanymi zmianami | ostrzeżenie przeglądarki w E-109 i E-701 |
| Długa operacja | import zadań > 5 MB w tle z odświeżaniem statusu; render i montaż przez kolejkę z odświeżaniem; symulacja, import danych, ML i szkic z AI — w trakcie żądania ([Z-6](../00-przeglad.md#założenia-wymagające-potwierdzenia)) |
| Link publiczny nieaktywny albo usunięty obiekt | standardowa strona „nie znaleziono” bez nawigacji |

## Podstawa w kodzie

`web/*/urls.py`, `web/core/views.py` (start, demo), `web/core/roles.py` (role), `web/core/context_processors.py`
(nawigacja), widoki modułów `web/twin/views/`, `web/masterdata/views.py`, `web/equipment/views.py`,
`web/scenario/views*.py`, `web/studio/views.py`, `web/render/views.py`, `web/ml/views.py`.
