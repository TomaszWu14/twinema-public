# 05. Wymagania

Wymagania **odtworzone z działającego kodu** — każde ma kryterium akceptacji i miejsce realizacji
(ścieżki względne do `web/`). Funkcji, których w kodzie nie ma, tu nie ma — są w
[07-ograniczenia.md](07-ograniczenia.md). Kolumna „Uwagi” wskazuje znane odstępstwa.

## Wymagania funkcjonalne

### Dostęp

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-01 | System rozróżnia trzy role: Administrator, Projektant, Podgląd | Gość wchodzący na dowolny ekran trafia na logowanie; zalogowany bez wymaganej roli widzi ekran „Brak dostępu” (HTTP 403); superuser przechodzi zawsze | `core/roles.py:20-41` | menu pokazuje wszystkie moduły każdej roli — [07](07-ograniczenia.md) |
| R-02 | Rola Podgląd widzi wyniki i 3D, ale nie dane źródłowe | Podgląd otwiera scenariusz, symulację, prezentację; lista materiałów, raport importu, zadania EWM i CSV segmentów zwracają 403; scena 3D nie zawiera SKU, HU, partii, ilości ani kodów lokalizacji | `masterdata/views.py:74,95`, `twin/shared.py:25`, `ml/views.py:61`, `twin/views/warehouse_blender.py:19-40` | |
| R-03 | Ochrona przed zgadywaniem hasła | Po 5 nieudanych próbach dla pary login + IP logowanie jest blokowane na 1 h | `twinema/settings.py:173-177` | strona blokady domyślna z biblioteki |

### Dane podstawowe

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-04 | Import materiałów, mastera lokalizacji i stanów z pliku | Akceptowane `.xlsx/.xlsm/.csv/.txt` do 25 MB i 300 000 wierszy; plik większy, pusty albo w innym formacie → komunikat, nic nie jest zapisane | `masterdata/views.py:51-71`, `masterdata/importers.py:100-131` | import synchroniczny |
| R-05 | System rozpoznaje kolumny po nazwach i aliasach | Brak kolumny wymaganej (materiały: kod; lokalizacje: kod lokalizacji; stany: kod lokalizacji i materiału) → „Brak wymaganych kolumn: … Pobierz wzór pliku”; raport pokazuje, które pole rozpoznano w której kolumnie | `masterdata/importers.py:67,134-146`, `masterdata/services.py:21-24` | |
| R-06 | Błędne wiersze nie blokują importu | Wiersz z ujemną liczbą, złą datą, złym kodem albo nieznanym nośnikiem jest odrzucony z numerem i powodem; pozostałe wiersze są zapisane w jednej transakcji; raport pokazuje „zapisano X z Y, odrzucono Z” | `masterdata/importers.py:170-225`, `masterdata/services.py:31-62` | |
| R-07 | Import lokalizacji tworzy nowy aktywny master | Po imporcie poprzednie mastery są nieaktywne; najnowszy import stanów jest aktualnym stanem | `masterdata/services.py:107-126` | brak ograniczenia w bazie — [04](04-model-danych.md) |
| R-08 | Spójność danych materiału jest sprawdzana, ale nie blokuje zapisu | Sztuki nie mieszczą się w kartonie, karton nie mieści się na nośniku, waga ponad nośność → ostrzeżenie w panelu „Spójność danych”; zapis możliwy | `masterdata/packaging.py:46-73` | tolerancje 2% i 10% bez uzasadnienia |

### Historia ruchów (zadania magazynowe)

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-09 | Podgląd pliku przed importem | Po wgraniu pliku (do 300 MB) system pokazuje rozpoznane kolumny, mapowanie procesów, próbkę 15 zadań i błędne wiersze z pierwszych 2000; nic nie trafia do bazy przed „Importuj cały plik”; brak wymaganych kolumn ukrywa przycisk importu | `twin/views/warehouse_tasks.py:65-105` | |
| R-10 | Rodzaj ruchu wyznaczany z procesu z możliwością nadpisania | Kolejność: nadpisanie użytkownika → słownik wyjątków → pierwsza cyfra procesu → działanie → kategoria → przesunięcie; zadania anulowane są pomijane | `twin/ewm_tasks.py:72-78,245-268` | |
| R-11 | Duży import w tle ze statusem | Plik do 5 MB importuje się od razu; większy w tle, raport odświeża status co 5 s; błąd → status „Błąd”, zapisane wiersze usunięte, komunikat z numerem wiersza | `twin/views/warehouse_tasks.py:23-44,107-157`, `twin/ewm_tasks_import.py:63-101` | restart serwera zostawia import „wiszący” |

### Model hali i edytor

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-12 | Model hali z generatora albo z pliku | Generator z 13 parametrów tworzy halę z regałami i dokami; plik kodów lokalizacji tworzy regały, plik geometrii — regały z pozycjami; nierozpoznane linie są zgłaszane | `twin/views/warehouse_generator.py:46-62`, `twin/views/warehouse_model.py:26-96` | |
| R-13 | Edytor wykrywa kolizje | Dwa regały nachodzące na siebie o więcej niż 2 cm → błąd w panelu „Problemy”; kliknięcie problemu zaznacza element | `twin/layout.py:41,298-301` | |
| R-14 | Regał nie może stać poza halą ani w strefie bez regałów | Regał poza obrysem (tolerancja 5 cm) albo w doku, bramie, polu odkładczym, korytarzu, drodze pożarowej, strefie ładowania → błąd; na drodze pieszej lub wózków → ostrzeżenie | `twin/layout.py:33-34,42,267-310` | |
| R-15 | Regał mieści się w wysokości hali i zasięgu sprzętu | Regał wyższy niż wysokość w świetle minus 0,5 m → błąd; najwyższa belka ponad maks. podnoszenie sprzętu → błąd; nośność ponad udźwig na tej wysokości → ostrzeżenie | `twin/layout.py:40,312-371` | |
| R-16 | Szerokość alejki zależy od sprzętu | Alejka węższa niż wymagana (reach 3,0 m, VNA 1,8 m, półki 2,0 m albo wartość z katalogu) → ostrzeżenie | `twin/design_catalog.py:23-31,169-215` | |
| R-17 | Planu z błędem nie da się zapisać; równoległa edycja nie nadpisuje zmian | Przycisk „Zapisz” nieaktywny przy błędach; serwer odrzuca plan z błędem (422); gdy model zmienił ktoś inny, zapis zwraca 409 i propozycję ponownego wczytania | `twin/views/warehouse_layout.py:128-149`, `static/twin/js/layout-editor.js:193-230,287` | |
| R-18 | Hala spełnia ograniczenia działki | Hala poza liniami zabudowy, procent zabudowy ponad maksimum, wysokość budynku ponad limit, zieleń poniżej minimum → błąd; za mały plac przed dokiem (35 m dla tira, 20 m dla busa) → ostrzeżenie | `twin/site.py:31-33,282-440` | |

### Scenariusz i symulacja

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-19 | Nowy scenariusz ma dzień typowy i szczytowy z wartościami domyślnymi | Po „Utwórz” scenariusz ma plan przyjęć, wydań i obsady; dzień szczytowy = typowy × 1,3 (bez linii na zamówienie) | `scenario/models.py:133-200` | wartości domyślne syntetyczne |
| R-20 | Wolumeny są trójkami min/śr/max | Zapis odrzucony, gdy nie jest spełnione 0 ≤ min ≤ śr ≤ max; okno godzin poza 0–24 albo od ≥ do → błąd; procenty poza 0–100 → błąd | `scenario/models.py:46-52,177-281` | walidacja tylko w aplikacji; po błędzie wpisane dane przepadają |
| R-21 | Zmiana może przechodzić przez północ | Koniec ≤ początek = zmiana przez północ; przerwa dłuższa niż zmiana → błąd | `scenario/models.py:331-354` | |
| R-22 | Symulacja dnia na wybranym układzie | Projektant wybiera model hali, dzień i 1–30 przebiegów; wynik zawiera KPI (średnia i P95), oś czasu, wąskie gardła i pojemność | `scenario/views_sim.py:86-105`, `scenario/sim/__init__.py:63-69` | liczona synchronicznie |
| R-23 | Wąskie gardło ma podpowiedź naprawy | Czekanie P95 > 20 min (krytyczne > 60), paczki spóźnione > 1% albo czekanie na flotę > 30 min → wąskie gardło z propozycją „+N osób / doków / wózków” sprawdzoną dodatkową symulacją | `scenario/sim/report.py:125-238` | progi bez uzasadnienia w dokumentacji |
| R-24 | Pojemność układu porównana ze stanem | Brak miejsc albo wypełnienie > 100% → błąd; > 90% → ostrzeżenie; palety cięższe niż nośność miejsc → ostrzeżenie | `scenario/placement.py:22-117` | |
| R-25 | Animacja dnia z dostępną alternatywą | Odtwarzanie ×10–×300, „Skok do szczytu”, wąskie gardła wyróżnione; bez WebGL komunikat i tabela godzinowa jako tekst | `scenario/views_play.py:106-130`, `scenario/templates/scenario/play.html` | |
| R-26 | Porównanie wyników | Do 6 wyników w tabeli z różnicą % względem pierwszego i wyróżnieniem najlepszego; eksport xlsx | `scenario/views_compare.py:142-161` | powyżej 6 obcinane bez komunikatu |
| R-27 | Prognoza wzrostu z oceną trafności | Przy ≥ 16 tygodniach historii model z najniższym MAPE (backtest 8 tygodni) daje mnożnik P50/P90; przy krótszej historii — komunikat z powodem | `ml/forecast.py:19-22,120-176` | |

### Katalog sprzętu

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-28 | Klasy systemowe chronione | Klasę systemową edytuje tylko administrator i nie można jej usunąć; Projektant może ją skopiować jako własny model | `equipment/views.py:75-77,153-191` | własne modele innych Projektantów nie są chronione |
| R-29 | Udźwig zależy od wysokości i osprzętu | Udźwig nominalny do pierwszego punktu krzywej, dalej liniowo; osprzęt obniża udźwig | `equipment/catalog.py:33-70` | |

### Pokaz dla zarządu

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-30 | Prezentacja 3D ze szablonu | „Utwórz ze szablonu” tworzy slajdy: działka, hala, strefy, doki, wyniki, szczyt, wąskie gardła, podsumowanie; wynik symulacji musi dotyczyć wybranej hali; maks. 60 slajdów, zapis do 512 KB | `scenario/views_showcase.py:48-52,101-116,226-239`, `scenario/showcase.py:13-87` | |
| R-31 | Publiczny link z datą ważności | Link ważny 1, 7, 14, 30 albo 90 dni; nowy link unieważnia poprzedni; wyłączony lub wygasły → 404; strona ma nagłówki noindex, no-referrer, no-store | `scenario/views_showcase.py:139-221` | 404 bez wyjaśnienia dla odbiorcy |

### Film (Studio)

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane | Uwagi |
|---|---|---|---|---|
| R-32 | Tekst zatwierdzany przed renderem | Teksty edytowalne tylko w szkicu; zatwierdzenie wymaga co najmniej jednego tekstu; render przed zatwierdzeniem nie rusza | `studio/views.py` (`approve`, `render_shots`) | |
| R-33 | Kolejność etapów | Render dopiero po zatwierdzeniu tekstu; montaż dopiero, gdy każde ujęcie ma aktualny render; długość ujęcia = czas czytania napisu | `studio/views.py` (`render_shots`, `montage_create`), `studio/captions.py` | film bez lektora ([D14](06-decyzje.md)) |
| R-34 | Do usługi AI idą tylko zagregowane liczby | Szkic z Claude dostaje wyłącznie zdania z KPI modelu, bez nazw, materiałów i lokalizacji | `studio/script.py:30-52`, `studio/script_ai.py:46-73` | |
| R-35 | Poprawka jednej kwestii nie powtarza całej pracy | Render i montaż mają klucz z hasha wejścia; ten sam klucz = wynik z pamięci; poprawka tekstu bez zmiany długości ujęcia nie renderuje klipu ponownie | `studio/models.py`, `studio/views.py` (`render_shots`, `montage_input_key`) | |

## Wymagania niefunkcjonalne

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane |
|---|---|---|---|
| N-01 | Konfiguracja sprawdzana przy starcie | Brak klucza Django przy wyłączonym trybie debug, za krótki token workera albo hasło demo → aplikacja nie startuje z czytelnym błędem | `twinema/config.py:59-67` |
| N-02 | Serwer nie wystawia portów dla workera | Worker sam odpytuje serwer po HTTPS z tokenem (min. 32 znaki) i jednorazowym kluczem przejęcia zlecenia | `render/api.py:33-127`, `tools/render_worker.py` |
| N-03 | Wynik renderu jest weryfikowany | Plik bez sygnatury PNG lub MP4 albo większy niż limit (500 MB) jest odrzucany | `render/api.py:25,104-116` |
| N-04 | Front nie zależy od CDN w czasie działania | Biblioteki JS pobierane przy budowie ze sprawdzeniem SHA-256; niezgodna suma przerywa budowę | `scripts/fetch_vendor.sh` |
| N-05 | Monitorowanie stanu | `/health/` zwraca 200 i stan bazy; brak bazy → 503 | `core/health_urls.py:8-20` |
| N-06 | Logika obliczeniowa testowalna bez bazy | Symulacja, ML, geometria i walidacja układu to czysty Python; pakiet testów (666) przechodzi w CI razem z lintem | `scenario/sim/`, `ml/`, `twin/layout.py`, `.github/workflows/ci.yml` |
| N-07 | Bezpieczeństwo sesji | Sesja 8 h odświeżana przy żądaniu; hasło co najmniej 10 znaków | `twinema/config.py:34`, `twinema/settings.py:149-158` |
