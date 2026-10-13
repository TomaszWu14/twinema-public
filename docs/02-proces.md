# 02. Proces biznesowy

Proces: **zaprojektowanie układu magazynu i uzasadnienie go przed zarządem.**

## Aktorzy

| Aktor | Typ | Udział w procesie |
|---|---|---|
| Projektant | człowiek (rola `Projektant`) | dane, model hali, scenariusz, symulacja, prezentacja |
| Zarząd | człowiek (rola `Podgląd` albo publiczny link) | ogląda pokaz, podejmuje decyzję |
| System magazynowy (WMS / SAP EWM) | system zewnętrzny | źródło plików: materiały, lokalizacje, stany, historia zadań — tylko eksport |
| Worker renderu | system (PC z Blenderem i ffmpeg) | renderuje ujęcia i montuje film (opcjonalnie) |
| Anthropic Claude | usługa zewnętrzna | szkic tekstów filmu (opcjonalnie) |

## PRZED — bez aplikacji

Stan przed: **brak narzędzia do wizualizacji i symulacji** (wywiad z autorem). Szczegóły kroków
i czasy są do uzupełnienia — diagram pokazuje tylko to, co wynika z problemu.

```mermaid
flowchart TD
    A([Potrzeba: nowa hala albo przebudowa]) --> B["Eksport danych z systemu magazynowego do arkuszy"]
    B --> C["Wolumeny i obsada liczone ręcznie<br/>DO UZUPEŁNIENIA: narzędzie, czas"]
    C --> D["Układ hali na płaskim rzucie<br/>DO UZUPEŁNIENIA: narzędzie"]
    D --> E{"Czy układ obsłuży szczyt?"}
    E -- "brak narzędzia do sprawdzenia:<br/>ocena ekspercka" --> F["Prezentacja dla zarządu:<br/>liczby i rzut, bez wizualizacji pracy hali"]
    F --> G{"Zarząd rozumie ryzyko?"}
    G -- "pytania wracają do projektanta" --> C
    G -- "tak" --> H([Decyzja])
```

**Gdzie proces się sypie (z opisu problemu):**
- brak sposobu, by sprawdzić dzień szczytowy przed budową — ryzyko wychodzi dopiero w eksploatacji;
- każda zmiana układu = ręczne przeliczenie od nowa;
- zarząd ocenia liczby, nie widzi przepływu;
- \<DO UZUPEŁNIENIA: konkretny przykład z praktyki\>.

## PO — z aplikacją

```mermaid
flowchart TD
    start([Projekt hali: nowa albo przebudowa]) --> D1

    subgraph DANE["1. Dane (Projektant)"]
        D1[Import materiałów xlsx/csv] --> D2[Import mastera lokalizacji]
        D2 --> D3[Import stanów]
        D3 --> DQ{Odrzucone wiersze?}
        DQ -- tak --> DR[Raport importu: wiersz + powód] --> D1
        DQ -- nie --> D4[(Dane podstawowe)]
        DE[Import zadań EWM: podgląd, potem import] --> D5[(Historia ruchów)]
    end

    subgraph HALA["2. Model hali (Projektant)"]
        H0{Skąd model?}
        H0 -- od zera --> H1[Generator hali z parametrów]
        H0 -- z danych --> H2[Plik kodów lokalizacji albo geometrii]
        H0 -- przebudowa --> H3[Kopia istniejącej hali jako przyszły layout]
        H1 --> H4[Edytor layoutu 2D/3D]
        H2 --> H4
        H3 --> H4
        H4 --> HV{Błędy layoutu?<br/>kolizje, wysokość, drogi, działka}
        HV -- "tak: zapis zablokowany" --> H4
        HV -- nie --> H5[(Model hali)]
    end

    subgraph SCEN["3. Scenariusz (Projektant)"]
        S1[Nowy scenariusz z wartościami domyślnymi] --> S2[Plan przyjęć i wydań:<br/>dzień typowy i szczytowy, min/śr/max]
        S2 --> S3[Obsada zmian, normy, flota z katalogu]
        S3 --> SV{Walidacja}
        SV -- błąd --> S2
        SV -- ok --> S4[Przepustowość i obsada wyliczone od razu]
    end

    subgraph SIM["4. Symulacja dnia"]
        M1[Model hali × scenariusz × dzień × 1–30 przebiegów] --> M2[Symulacja zdarzeniowa]
        M2 --> M3[KPI: średnia i P95,<br/>wąskie gardła z podpowiedzią +N]
        M3 --> MQ{Wąskie gardła krytyczne?}
        MQ -- tak --> MF{Co zmienić?}
        MF -- układ --> H4
        MF -- obsada albo flota --> S3
        MQ -- nie --> M4[Porównanie układ × scenariusz, xlsx]
    end

    subgraph PROJ["4b. Projektowanie z historii (opcjonalnie)"]
        P1[Profil ruchów, dzień projektowy P90/P95/P99] --> P2[Kalibracja na obecnej hali]
        P2 --> P3[Prognoza wzrostu]
        P3 --> P4[Symulacja nowej hali z mnożnikiem P50/P90]
    end

    subgraph POKAZ["5. Pokaz dla zarządu"]
        R1[Prezentacja 3D ze szablonu] --> R2[Poprawa podpisów i ujęć kamery]
        R2 --> R3{Kto ogląda?}
        R3 -- konto Podgląd --> R4[Link wewnętrzny: tylko pokaz]
        R3 -- osoba bez konta --> R5[Publiczny link ważny 1–90 dni]
        R1 -. opcjonalnie .-> F1[Studio: tekst, render, montaż z napisami:<br/>MP4 i deck PDF]
    end

    D4 --> H0
    D4 --> S1
    H5 --> M1
    S4 --> M1
    D5 --> P1
    H5 --> P2
    M4 --> R1
    P4 --> M4
    R4 --> fin([Decyzja zarządu])
    R5 --> fin
    F1 --> fin
```

## Punkty decyzyjne

| Punkt | Kto decyduje | Na podstawie czego | Co dalej |
|---|---|---|---|
| Czy odrzucenia importu są akceptowalne? | Projektant | raport: wiersz + powód ([R-06](05-wymagania.md)) | popraw plik i zaimportuj ponownie albo kontynuuj |
| Czy mapowanie procesów EWM na rodzaje ruchu jest poprawne? | Projektant | podgląd 2000 wierszy przed importem | nadpisz mapowanie (`kod = rodzaj`) albo importuj |
| Czy layout przechodzi walidację? | system | reguły kolizji, wysokości, dróg, działki ([R-13…R-18](05-wymagania.md)) | błąd blokuje zapis; ostrzeżenie nie |
| Czy obsada pokrywa potrzebę? | Projektant | „Obsada: zakładana vs potrzebna” | zmiana zmian albo norm |
| Co zmienić przy wąskim gardle? | Projektant | wąskie gardła z podpowiedzią (+N osób, doków, wózków) | wróć do layoutu albo do scenariusza |
| Komu i na jak długo udostępnić pokaz? | Projektant | — | link dla roli Podgląd albo publiczny link z datą ważności |
| Czy zatwierdzić tekst filmu? | Projektant | teksty ujęć (szablon albo szkic z Claude) | dopiero po zatwierdzeniu render i montaż |

## Wejścia i wyjścia

| Krok | Wejście | Wyjście |
|---|---|---|
| Dane | pliki xlsx/csv z systemu magazynowego | materiały, master lokalizacji, stany, raport importu |
| Historia ruchów | eksport zadań magazynowych (do 300 MB) | partia zadań, statystyki, profil dnia |
| Model hali | parametry, plik albo kopia | model z regałami, elementami hali, słupami, działką |
| Scenariusz | założenia wolumenów, obsady, norm | przepustowość, obsada potrzebna |
| Symulacja | model × scenariusz | KPI, wąskie gardła, zdarzenia do animacji |
| Pokaz | wynik symulacji, model | prezentacja 3D, link |
| Film | KPI modelu, zatwierdzony tekst | MP4, napisy SRT, deck PDF |
