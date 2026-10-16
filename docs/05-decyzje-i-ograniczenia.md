# Decyzje, ograniczenia i dług techniczny

Dokument zbiera decyzje projektowe widoczne w kodzie, znane ograniczenia rozwiązania oraz listę prac
wymaganych przed wdrożeniem produkcyjnym. Przy każdej decyzji podano, czy jej uzasadnienie zostało zapisane
w trakcie prac. Gdy nie — opisano tylko kontekst i skutki wynikające z kodu.

## Dziennik decyzji

| ID | Decyzja | Uzasadnienie zapisane? |
|---|---|---|
| [D1](#d1-dane-tylko-z-plików-bez-integracji-na-żywo) | Dane tylko z plików, bez integracji na żywo | tak — ADR-0001 |
| [D2](#d2-kopia-kodu-zamiast-przeniesienia-albo-wspólnej-biblioteki) | Kopia kodu zamiast przeniesienia albo wspólnej biblioteki | tak — ADR-0001 |
| [D3](#d3-scenariusz-niezależny-od-układu-hali) | Scenariusz niezależny od układu hali | tak — założenia projektu |
| [D4](#d4-wolumeny-jako-minśrmax-wiele-przebiegów-wynik-p95) | Wolumeny jako min/śr/max, wiele przebiegów, wynik P95 | częściowo |
| [D5](#d5-kolejka-renderów-bez-celery-worker-odpytuje-serwer) | Kolejka renderów bez brokera, stanowisko odpytuje serwer | tak — plan projektu |
| [D6](#d6-prezentacja-3d-w-przeglądarce-przed-filmem) | Prezentacja 3D w przeglądarce przed filmem | tak — plan projektu |
| [D7](#d7-rola-podgląd-bez-danych-źródłowych) | Rola Podgląd bez danych źródłowych | tak — założenia projektu |
| [D8](#d8-błąd-layoutu-blokuje-zapis-ostrzeżenie-nie) | Błąd układu blokuje zapis, ostrzeżenie nie | nie |
| [D9](#d9-klucze-integracji-jako-tekst-zamiast-kluczy-obcych) | Klucze integracji jako tekst zamiast powiązań w bazie | nie |
| [D10](#d10-obliczenia-synchroniczne-w-żądaniu) | Obliczenia w trakcie żądania | nie |
| [D11](#d11-logika-obliczeniowa-bez-django) | Logika obliczeniowa oddzielona od aplikacji WWW | częściowo |
| [D12](#d12-biblioteki-js-w-repozytorium-nie-z-cdn) | Biblioteki przeglądarki w obrazie aplikacji, nie z CDN | tak — skrypt budowy |
| [D13](#d13-do-ai-tylko-zagregowane-liczby-tekst-zatwierdza-człowiek) | Do AI tylko zagregowane liczby, tekst zatwierdza człowiek | częściowo |
| [D14](#d14-film-bez-lektora-napisy-w-obrazie-i-opcjonalna-muzyka) | Film bez lektora: napisy w obrazie i opcjonalna muzyka | tak — decyzja właściciela |
| [D15](#d15-demo-publiczne-przez-konto-gościa-w-roli-podgląd) | Demo publiczne przez konto gościa w roli Podgląd | częściowo |

---

### D1. Dane tylko z plików, bez integracji na żywo

- **Kontekst:** dane magazynu są w systemie magazynowym. System ma służyć do projektowania, nie do bieżącej pracy.
- **Rozważane opcje:** w dokumentach rozważono sposób przejęcia kodu (D2); integracja przez API z systemem magazynowym nie jest opisana jako rozważona opcja.
- **Uzasadnienie:** dane płyną wyłącznie przez importy plików — brak zależności między wdrożeniami ([ADR-0001](architektura/adr/0001-kopia-nie-przeniesienie.md)).
- **Konsekwencje:** każdy import ma raport odrzuceń; dane mogą być nieaktualne — aktualizacja oznacza ponowny import; model danych musi tolerować kody, których nie ma w drugim zbiorze (D9).

### D2. Kopia kodu zamiast przeniesienia albo wspólnej biblioteki

- **Kontekst:** część kodu (modelowanie hali, symulacja, eksport sceny 3D) powstała we wcześniejszym projekcie autora.
- **Rozważane opcje:** przeniesienie, kopia, wspólna biblioteka.
- **Uzasadnienie:** źródło działa dalej bez zmian; wspólna biblioteka dopiero wtedy, gdy oba projekty realnie edytują te same pliki ([ADR-0001](architektura/adr/0001-kopia-nie-przeniesienie.md)).
- **Konsekwencje:** poprawki nie wracają automatycznie do źródła; w kopii zostały pozostałości nazewnictwa z projektu źródłowego (sekcja [Do anonimizacji](#do-anonimizacji)).

### D3. Scenariusz niezależny od układu hali

- **Kontekst:** Projektant porównuje obecny i przyszły układ.
- **Rozważane opcje:** parametry wolumenów zapisane przy modelu hali albo osobny obiekt „Scenariusz”.
- **Uzasadnienie:** ten sam scenariusz testuje różne układy — porównanie wariantów na tych samych danych ([założenia projektu](ZALOZENIA.md), pkt 1 i 20).
- **Konsekwencje:** wynik symulacji to para scenariusz × model hali; porównanie pokazuje różnicę % przy identycznym wejściu; usunięcie hali usuwa jej wyniki ([P5](01-procesy/P5-scenariusz-i-symulacja.md)).

### D4. Wolumeny jako min/śr/max, wiele przebiegów, wynik P95

- **Kontekst:** liczba aut, palet i zamówień zmienia się z dnia na dzień.
- **Rozważane opcje:** nieudokumentowane; oczywista alternatywa to jedna wartość średnia.
- **Uzasadnienie:** liczby są zawsze edytowalne jako min / średnio / max; ziarno losowania zapisane w scenariuszu (powtarzalność); KPI z kilkunastu przebiegów: średnia i najgorszy przypadek P95 ([założenia projektu](ZALOZENIA.md)). Wybór rozkładu trójkątnego nie ma zapisanego uzasadnienia.
- **Konsekwencje:** walidacja 0 ≤ min ≤ śr ≤ max we wszystkich trójkach; obliczenie trwa dłużej (1–30 przebiegów); wynik pokazuje najgorszy przypadek, nie tylko przeciętny dzień.

### D5. Kolejka renderów bez Celery, worker odpytuje serwer

- **Kontekst:** render w Blenderze wymaga karty graficznej, której serwer aplikacji nie ma.
- **Rozważane opcje:** zewnętrzny broker zadań (Celery z Redisem) albo tabela zleceń i stanowisko renderujące odpytujące serwer po HTTPS.
- **Uzasadnienie:** serwer bez karty graficznej i bez otwartych portów do brokera — wystarczy HTTPS; wyłączone stanowisko oznacza, że zlecenia czekają w kolejce ([plan projektu](PLAN.md), decyzja D6).
- **Konsekwencje:** token stanowiska i jednorazowy klucz przejęcia zlecenia; zlecenie „w toku” wraca do kolejki po 120 min, ale tylko przy kolejnym odpytaniu; bez stanowiska zlecenia czekają bez końca.

### D6. Prezentacja 3D w przeglądarce przed filmem

- **Kontekst:** po zbudowaniu modułu filmu trzeba było wybrać kierunek dalszych prac.
- **Rozważane opcje:** dopracować film i montaż albo edytor układu i pokaz w przeglądarce.
- **Uzasadnienie:** głównym celem jest pokazać w przeglądarce, jak może wyglądać przyszły układ ([plan projektu](PLAN.md)).
- **Konsekwencje:** powstały edytor 2D/3D, animacja dnia i prezentacja 3D z publicznym linkiem; moduł filmu jest zbudowany i przetestowany automatycznie, ale nie przeszedł pełnej próby z renderem z Blendera.

### D7. Rola Podgląd bez danych źródłowych

- **Kontekst:** pokaz ogląda zarząd albo osoba z zewnątrz.
- **Rozważane opcje:** nieudokumentowane.
- **Uzasadnienie:** Podgląd widzi wyniki i 3D (układ, animację dnia, KPI, wąskie gardła, scenariusze), bez danych źródłowych i bez edycji ([założenia projektu](ZALOZENIA.md), pkt 25).
- **Konsekwencje:** scena 3D dla Podglądu jest czyszczona z kodów materiałów, jednostek ładunkowych, partii i kodów lokalizacji; importy i zadania magazynowe dają stronę braku uprawnień. Menu tego nie odzwierciedla.

### D8. Błąd layoutu blokuje zapis, ostrzeżenie nie

- **Kontekst:** edytor sprawdza plan po każdej zmianie.
- **Rozważane opcje:** nieudokumentowane.
- **Uzasadnienie:** niezapisane. Kod rozdziela problemy na błędy (kolizja, regał poza halą, w doku, za wysoki dla sprzętu) i ostrzeżenia (za wąska alejka, droga piesza, nośność, udźwig).
- **Konsekwencje:** w bazie nie może się znaleźć plan fizycznie niemożliwy; plan z ostrzeżeniami da się zapisać i zasymulować; równoległa zmiana modelu przez dwie osoby jest wykrywana i druga zmiana odrzucana.

### D9. Klucze integracji jako tekst zamiast kluczy obcych

- **Kontekst:** stan magazynu wskazuje materiał i lokalizację.
- **Rozważane opcje:** nieudokumentowane.
- **Uzasadnienie:** niezapisane; kod opisuje to jako zasadę: klucze integracji (kod materiału, kod lokalizacji) są tekstem, bez powiązania z modelem hali.
- **Konsekwencje:** każdy plik można wgrać niezależnie, w dowolnej kolejności (zgodne z D1); baza nie pilnuje spójności — stan może wskazywać materiał albo lokalizację, których nie ma ([model danych](02-dane/model-danych.md)).

### D10. Obliczenia synchroniczne w żądaniu

- **Kontekst:** symulacja, import danych, przebiegi ML i szkic z AI trwają od sekund do minut.
- **Rozważane opcje:** nieudokumentowane; kolejka istnieje tylko dla renderu (D5) i dużych importów zadań (wątek w tle).
- **Uzasadnienie:** niezapisane.
- **Konsekwencje:** prosta architektura bez brokera; ryzyko przekroczenia limitu 120 s serwera przy dużych symulacjach i szkicu z AI ([Z-6](00-przeglad.md#założenia-wymagające-potwierdzenia)).

### D11. Logika obliczeniowa bez Django

- **Kontekst:** symulacja, ML, geometria i walidacja układu to najbardziej złożona część systemu.
- **Rozważane opcje:** nieudokumentowane.
- **Uzasadnienie:** logika napisana bez dostępu do bazy danych, żeby dało się ją testować bez bazy (opisy modułów).
- **Konsekwencje:** szybkie testy automatyczne; ekrany tylko przygotowują dane i wywołują logikę.

### D12. Biblioteki JS w repozytorium, nie z CDN

- **Kontekst:** scena 3D i wykresy korzystają z zewnętrznych bibliotek przeglądarkowych.
- **Rozważane opcje:** ładowanie z CDN w przeglądarce albo pobranie przy budowie.
- **Uzasadnienie:** aplikacja nie zależy od CDN w czasie pracy (polityka bezpieczeństwa treści, awarie CDN).
- **Konsekwencje:** sumy kontrolne sprawdzane przy budowie; lokalnie trzeba raz uruchomić skrypt pobierania.

### D13. Do AI tylko zagregowane liczby, tekst zatwierdza człowiek

- **Kontekst:** moduł filmu może poprosić usługę AI o szkic tekstów.
- **Rozważane opcje:** nieudokumentowane.
- **Uzasadnienie:** do modelu językowego wolno wysłać tylko zdania z zagregowanymi liczbami, bez nazw modelu, materiałów i lokalizacji; nic nie idzie do renderu przed akceptacją. Powód (ochrona danych, kontrola treści) nie jest zapisany wprost.
- **Konsekwencje:** zapytanie zawiera tylko zdania z KPI; status „tekst zatwierdzony” jest bramką przed renderem ([P7](01-procesy/P7-film-i-deck.md)).

### D14. Film bez lektora: napisy w obrazie i opcjonalna muzyka

- **Kontekst:** film miał lektora z syntezy mowy; pierwszy prawdziwy film wymagałby płatnego klucza, wyboru głosu i odsłuchu każdej poprawki.
- **Rozważane opcje:** lektor obowiązkowy; lektor opcjonalny obok napisów (dwie ścieżki); film tylko z napisami; rezygnacja z filmu na rzecz prezentacji 3D.
- **Uzasadnienie:** decyzja właściciela projektu — film tylko z napisami i muzyką, jedna ścieżka, bez zewnętrznej usługi i kosztu za znak.
- **Konsekwencje:** długość ujęcia liczona z tekstu (tempo czytania 2,2 słowa/s + 1,5 s, 5–60 s); napisy wypalane w obrazie, pod filmem muzyka albo cisza; poprawka tekstu = nowy montaż, nowy render tylko przy zmianie długości ujęcia; stare nagrania lektora usunięte z bazy (pliki zostają na dysku).

### D15. Demo publiczne przez konto gościa w roli Podgląd

- **Kontekst:** osoba z zewnątrz ma ocenić system bez zakładania konta i bez znajomości hasła.
- **Rozważane opcje:** tylko publiczny pokaz 3D; hasło demo podane publicznie; przycisk „wejdź jako gość” logujący na konto demo.
- **Uzasadnienie:** zapisane w kodzie częściowo — wejście gościa działa tylko po włączeniu demo publicznego i tylko na konto zwykłego Podglądu (nigdy na konto z wyższymi prawami); powód wyboru tej opcji nie jest zapisany.
- **Konsekwencje:** gość ma pełny odczyt w roli Podgląd na danych syntetycznych; wszyscy goście współdzielą jedno konto; publiczny pokaz 3D ma link ważny 10 lat ([P8](01-procesy/P8-dostep-i-demo.md)).

## Wymagania niefunkcjonalne zrealizowane w kodzie

| Nr | Wymaganie | Kryterium spełnienia |
|---|---|---|
| N-01 | Konfiguracja sprawdzana przy starcie | brak klucza aplikacji w trybie produkcyjnym, za krótki token stanowiska renderującego, hasło demo krótsze niż 8 znaków albo adres filmu demo bez https → aplikacja nie startuje i podaje czytelny powód |
| N-02 | Serwer nie wystawia portów dla stanowiska renderującego | stanowisko samo łączy się po HTTPS z tokenem (≥ 32 znaki) i jednorazowym kluczem przejęcia zlecenia |
| N-03 | Wynik renderu jest weryfikowany | plik bez sygnatury PNG/MP4 albo większy niż 500 MB jest odrzucany |
| N-04 | Przeglądarka nie zależy od CDN w czasie pracy | biblioteki pobierane przy budowie ze sprawdzeniem sumy kontrolnej; niezgodna suma przerywa budowę |
| N-05 | Monitorowanie stanu | adres kontroli działania zwraca stan bazy i wersję; brak bazy → kod błędu 503 |
| N-06 | Logika obliczeniowa testowalna bez bazy | symulacja, ML, geometria i walidacja układu mają testy automatyczne uruchamiane w CI przy każdej zmianie |
| N-07 | Bezpieczeństwo sesji i haseł | sesja 8 h odświeżana przy aktywności; hasło ≥ 10 znaków; 5 nieudanych logowań → blokada na 1 h |
| N-08 | Ochrona pokazu publicznego | strona pokazu nie jest indeksowana, nie przekazuje adresu innym serwisom i nie jest przechowywana przez pośredników |
| N-09 | Ochrona danych źródłowych | rola Podgląd i goście nie widzą kodów materiałów, lokalizacji, jednostek ładunkowych i partii; do usługi AI trafiają tylko zagregowane liczby |

## Znane ograniczenia

### Funkcje, których nie ma

| Brak | Skutek dla użytkownika |
|---|---|
| Integracja na żywo z systemem magazynowym | dane trzeba eksportować i importować ręcznie (D1) |
| Automatyczna optymalizacja układu | system ocenia wariant narysowany przez Projektanta, nie proponuje układu sam |
| Rejestracja i odzyskiwanie hasła | konta zakłada Administrator w panelu administracyjnym |
| ~~Własne strony błędów „nie znaleziono” i „błąd serwera”~~ — są (US-020) | — |
| Anulowanie trwającego importu zadań | jest tylko wstrzymanie odświeżania |
| Render na serwerze | wymaga osobnego komputera z Blenderem 4.x i stanowiskiem renderującym |
| Film sprawdzony od początku do końca | pierwszy prawdziwy film wymaga stanowiska z Blenderem i ffmpeg ≥ 6.1 (D6) |
| Interfejs w innym języku niż polski | zasada projektu; powód niezapisany |

### Uprawnienia i nawigacja

- ~~Menu i część przycisków były widoczne dla roli Podgląd, choć prowadziły do strony braku uprawnień~~ — poprawione (US-019).
- Symulacja dnia i kalibracja liczą się także dla roli Podgląd, a porównanie modeli nie — intencja nieustalona ([Z-3](00-przeglad.md#założenia-wymagające-potwierdzenia)).
- Wszyscy goście demo współdzielą jedno konto.

### Dane i spójność

- Usunięcie sprzętu kasuje grupy floty mieszanej scenariuszy bez ekranu potwierdzenia; komunikat po fakcie podaje ich liczbę ([P4](01-procesy/P4-katalog-sprzetu.md), W8). Czy grupy mają być usuwane, czy odłączane — [Z-4](00-przeglad.md#założenia-wymagające-potwierdzenia).
- Usunięcie modelu hali kaskadowo usuwa wyniki symulacji, prezentacje 3D, prezentacje filmowe i zlecenia renderu; ekran potwierdzenia wspomina tylko regały i nie wyświetla nazwy modelu.
- Zachowywanych jest 20 ostatnich wyników na scenariusz — starsze znikają także z prezentacji 3D, bez informacji.
- Dane demo nadpisują stan bieżący magazynu (najnowszy import stanów wygrywa).
- ~~Nazwa własnego modelu sprzętu nie była unikalna~~ — baza i formularz pilnują unikalności (US-022).
- Ograniczenia min ≤ śr ≤ max, okien godzin i procentów są pilnowane tylko przez aplikację, nie przez bazę; brak kontroli nakładania się zmian i duplikatów strumieni tego samego rodzaju.

### Długie operacje

- ~~Symulacja liczyła się w trakcie żądania~~ — symulacja dnia i scenariusza oraz kalibracja idą przez kolejkę zadań w bazie (US-007, ADR-0004). Do kolejki trafiają też import danych podstawowych, przebiegi ML i szkic z AI (T-1). W trakcie żądania zostaje tylko ślad symulacji dla animacji 3D (liczy go wyłącznie Projektant).
- ~~Import zadań w tle działał w wątku procesu~~ — duży import idzie przez kolejkę i po restarcie workera jest ponawiany bez dublowania wierszy (US-024).
- ~~Zlecenie renderu odrzucone przez serwer wracało do kolejki bez limitu prób~~ — po 3 próbach kończy się błędem (US-015).

### Formularze i informacja zwrotna

- Brak potwierdzenia przy usuwaniu: prezentacji 3D, prezentacji filmowej, zlecenia renderu, slajdu (hala, scenariusz i sprzęt mają ekran potwierdzenia ze skutkami — US-004).
- Po błędzie walidacji wpisane dane przepadają w formularzach typu regału i edycji stref (formularze scenariusza zachowują dane — US-021).
- Komunikat sukcesu mimo pominięcia danych: współrzędne regałów, elementy hali, import sprzętu z samymi odrzuceniami.
- Po wygaśnięciu sesji zapis w edytorze prezentacji pokazuje „Brak połączenia z serwerem” zamiast prośby o zalogowanie.

### Dokumentacja robocza

- [PLAN.md](PLAN.md) i [ZALOZENIA.md](ZALOZENIA.md) to zapis prac z okresu budowy. Część szczegółów jest nieaktualna (np. nazwa adresu pobierania zleceń i wersja sceny). Źródłem prawdy jest ta dokumentacja i kod.

## Dług techniczny i prace przed wdrożeniem produkcyjnym

Pozycje T-n mają odpowiedniki w [backlogu](analiza/HISTORYJKI.md) (kolumna „Źródło”), ryzyka — w [rejestrze ryzyk](bezpieczenstwo/RYZYKA.md).

| Nr | Praca | Powód | Priorytet |
|---|---|---|---|
| T-1 | Przenieść do kolejki ślad symulacji dla animacji 3D (reszta — symulacje, kalibracja, import danych, ML, szkic z AI — zrobione) | limit 120 s żądania przy animacji długiego dnia | niski |
| T-2 | ~~Zastąpić wątek importu zadań trwałą kolejką z ponawianiem~~ — zrobione (US-024) | — | — |
| T-3 | ~~Ukryć przed rolą Podgląd moduły i przyciski bez dostępu~~ — zrobione (US-019) | — | — |
| T-4 | ~~Sprawdzanie autora przy edycji i usuwaniu własnego sprzętu~~ — zrobione (US-001) | Projektant mógł zmienić cudzy model | — |
| T-5 | ~~Ekrany potwierdzenia usunięcia z listą obiektów usuwanych kaskadowo (model hali, scenariusz, sprzęt)~~ — zrobione (US-004) | — | — |
| T-6 | Zachowanie przy usuwaniu sprzętu używanego we flocie mieszanej: ostrzec przed usunięciem albo odłączać zamiast usuwać (komunikat poprawiony w US-002) | grupy floty znikają bez potwierdzenia | wysoki |
| T-7 | ~~Unikalna nazwa własnego modelu sprzętu w bazie~~ — zrobione (US-022) | — | — |
| T-8 | ~~Własne strony „nie znaleziono” i „błąd serwera”~~ — zrobione (US-020) | — | — |
| T-9 | ~~Informacja, że wynik przypięty do prezentacji 3D został usunięty~~ — zrobione: przypięty wynik nie wypada z limitu, a po usunięciu scenariusza prezentacja ostrzega (US-025) | — | — |
| T-10 | ~~Zachowanie danych formularza po błędzie walidacji~~ — zrobione: scenariusz, typ regału, edycja stref (US-021) | — | — |
| T-17 | Przenieść style z szablonów do plików CSS (pomiar 2026-10-16: 371 atrybutów `style=` w 51 szablonach, 40 bloków `<style>`; dymki ECharts też wstawiają `style`), potem usunąć `'unsafe-inline'` z `style-src`. Do tego czasu test nie pozwala dodawać nowych stylów w szablonach (`inline_styles_baseline.json`) | CSP dopuszcza style wstawione w stronę (mniejsze ryzyko niż skrypty) | niski |
| T-11 | ~~Limit prób dla zleceń renderu odrzucanych przez serwer~~ — zrobione (US-015) | — | — |
| T-12 | Ograniczenia spójności w bazie (min ≤ śr ≤ max, unikalność strumieni i grup floty) | dziś pilnuje tylko aplikacja | niski |
| T-13 | Osobne konta gościa albo ograniczenie sesji demo | współdzielone konto demo | niski |
| T-14 | Pełna próba filmu ze stanowiskiem renderującym | moduł filmu niesprawdzony z prawdziwym renderem | niski (moduł opcjonalny) |
| T-15 | Usunięcie pozostałości z sekcji [Do anonimizacji](#do-anonimizacji), także z historii repozytorium | ochrona danych firmowych i osobowych | wysoki — procedura gotowa: [CZYSZCZENIE_HISTORII](operacje/CZYSZCZENIE_HISTORII.md), wykonuje PO |
| T-16 | Polityka kopii zapasowych bazy i katalogu plików (podkłady, rendery, filmy) | w kodzie brak mechanizmu kopii | wysoki |

## Do anonimizacji

Poniższe miejsca zawierają dane, które mogą identyfikować osobę, firmę albo obiekt rzeczywisty. **Wartości
celowo nie są tu przytaczane** — podano tylko lokalizację i rodzaj danych.

| Nr | Miejsce | Rodzaj danych | Zalecenie |
|---|---|---|---|
| A-1 | `LICENSE` | imię i nazwisko autora | potwierdzić, czy ma zostać (wymóg licencji) |
| A-2 | `README.md`, `docs/PLAN.md` | nazwa konta autora w serwisie kodu i nazwa prywatnego repozytorium | zastąpić opisem ogólnym |
| A-3 | `README.md`, `.github/workflows/ci.yml`, `tools/render_worker.py` (opis uruchomienia) | domena autora | zastąpić przykładową domeną |
| A-4 | `PROVENANCE.md`, `docs/PLAN.md`, `docs/architektura/adr/0001-kopia-nie-przeniesienie.md` | nazwa prywatnego projektu źródłowego | zastąpić określeniem „projekt źródłowy” |
| A-5 | `web/twin/models.py` (komentarz przy masterze lokalizacji), `web/twin/blender_stock.py`, `web/twin/blender_scene.py` | nazwy aplikacji i bloków z projektu źródłowego | usunąć z komentarzy |
| A-6 | `web/twin/ewm_levels.py`, `web/twin/locations.py` | oznaczenia poziomów z obiektu źródłowego | potwierdzić, czy to konwencja ogólna, czy specyfika obiektu |
| A-7 | dane przykładowe w testach i generatorach | kod hali z obiektu źródłowego | zastąpić neutralnym kodem |
| A-8 | historia repozytorium (wcześniejsze wersje plików reguł zadań magazynowych) | liczba lokalizacji, typy składowania, kody procesów i daty decyzji z rzeczywistego obiektu | przepisać historię albo opublikować repozytorium od nowa; przejrzeć także pozostałe wczesne wersje |
| A-9 | historia repozytorium (autor zmian) | prywatny adres e-mail | ustawić adres zastępczy dla przyszłych zmian; ocenić przepisanie historii |
| A-10 | `web/twin/tests/test_ewm_tasks_parser.py`, `test_ewm_tasks_flow.py` | login testowy przypominający nazwisko | zastąpić neutralnym loginem |
| A-11 | `web/twin/views/warehouse_generator.py` (opis modułu) | ścieżka do wewnętrznego planu autora | usunąć |
| A-12 | `README.md` | przykładowe hasło demo | zastąpić symbolem zastępczym |

W danych demo (generatory materiałów, stanów, zadań i scenariusza) nie znaleziono nazw kontrahentów, materiałów
ani osób — dane są syntetyczne. Dokumentacja analityczna nie przenosi żadnej z powyższych wartości.

## Rzeczy nieustalone z kodu

Pełna lista założeń wymagających potwierdzenia: [00-przeglad.md → Założenia wymagające potwierdzenia](00-przeglad.md#założenia-wymagające-potwierdzenia).
