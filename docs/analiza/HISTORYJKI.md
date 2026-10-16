# Backlog historyjek

**[BA]** · priorytety MoSCoW — propozycja do akceptacji PO. Pilne poprawki bezpieczeństwa z
[audytu](../AUDYT.md) są na początku. Historyjki funkcji już istniejących: procesy P1–P8 (WF-…).

| ID | Historyjka | Priorytet | Źródło | Status |
|---|---|---|---|---|
| US-001 | Jako Projektant chcę, aby mój model sprzętu mogli zmieniać i usuwać tylko ja i Administrator, aby nikt nie zepsuł mi parametrów floty | Must | R-03, T-4 | **zrobione** (ten PR) |
| US-002 | Jako Projektant chcę po usunięciu sprzętu wiedzieć, ile grup floty mieszanej zniknęło, aby nie stracić założeń scenariusza bez wiedzy | Must | W8 w P4, T-6 | **zrobione** (ten PR) |
| US-003 | Jako Administrator chcę, aby stanowisko renderujące łączyło się z serwerem tylko po HTTPS, aby token nie wyciekł | Must | R-17 | **zrobione** (ten PR) |
| US-010 | Jako PO chcę usunąć z historii repozytorium dane rzeczywistego obiektu i prywatny e-mail, aby publiczne repozytorium nie ujawniało danych firmowych | Must | R-01, A-8, A-9 | w toku — procedura gotowa, wykonuje PO |
| US-011 | Jako Administrator chcę ostrzeżenia przy starcie, gdy demo publiczne jest włączone na instancji z danymi spoza demo, aby nie udostępnić ich światu | Must | R-02 | **zrobione** (PR #68) |
| US-012 | Jako pracownik magazynu chcę, aby mój login z historii zadań był pseudonimizowany przy imporcie, aby nikt nie oceniał mojej wydajności bez podstawy | Must (po decyzji PO) | R-06, RODO CP-4 | **zrobione** (PR #68) |
| US-004 | Jako Projektant chcę przed usunięciem hali, scenariusza lub sprzętu zobaczyć listę obiektów usuwanych razem z nimi, aby nie stracić wyników i prezentacji | Must | T-5 | **zrobione** (PR #68) |
| US-009 | Jako Administrator chcę kopii zapasowej bazy i plików z procedurą odtworzenia, aby po awarii odzyskać dane | Must | R-10, T-16 | procedura w RUNBOOK; automatyzacja do realizacji |
| US-013 | Jako PO chcę, aby każdy merge do `main` wymagał mojego zatwierdzenia, aby żadna zmiana nie trafiła na produkcję bez akceptacji | Must | R-09 | częściowo — auto-merge usunięty (PR #68); ochronę gałęzi ustawia PO |
| US-007 | Jako Administrator chcę, aby długie obliczenia szły w tle i nie mogła ich uruchamiać rola Podgląd, aby nikt nie zablokował serwera | Should | R-07, T-1 | częściowo — Podgląd nie uruchamia obliczeń (PR #68); kolejka w tle — do realizacji |
| US-005 | Jako Administrator chcę wymuszonej polityki CSP, aby ograniczyć skutki ewentualnego XSS | Should | R-04 | do realizacji (wymaga testu UI) |
| US-006 | Jako Administrator chcę, aby nagłówek adresu klienta był brany pod uwagę tylko od proxy w sieci wewnętrznej, aby blokady logowania nie dało się obejść podmianą adresu | Should | R-05 | **zrobione** (PR #68) |
| US-008 | Jako Administrator chcę dziennika operacji wrażliwych, aby wiedzieć, kto usunął dane albo udostępnił link | Should | R-08 | do realizacji |
| US-014 | Jako SEC chcę, aby semgrep i trivy blokowały PR po triażu pierwszych wyników, aby nowe ustalenia nie przechodziły | Should | R-18 | **zrobione** (PR #68) — [triaż](../bezpieczenstwo/TRIAZ_SKANOW.md) |
| US-019 | Jako Podgląd chcę widzieć w menu tylko moduły, do których mam dostęp, aby nie trafiać na stronę braku uprawnień | Should | T-3 | **zrobione** (PR #68) |
| US-023 | Jako PO chcę progu pokrycia testami w CI, aby jakość nie spadała | Should | NFR-015 | **zrobione** — próg 80% (PR #68) |
| US-024 | Jako Projektant chcę, aby import zadań w tle przetrwał restart serwera, aby nie powtarzać importu | Should | T-2 | do realizacji |
| US-017 | Jako Administrator chcę drugiego składnika logowania i haseł ≥ 12 znaków dla kont uprzywilejowanych, aby utrudnić przejęcie konta | Could | R-11, ASVS V2 | czeka na decyzję PO |
| US-018 | Jako SEC chcę akcji CI przypiętych skrótem commita, aby podmiana tagu nie wpuściła obcego kodu | Could | R-16 | **zrobione** (PR #68) |
| US-015 | Jako Administrator chcę limitu prób dla zleceń renderu odrzucanych przez serwer, aby zlecenie nie krążyło bez końca | Could | R-14, T-11 | **zrobione** (PR #68) |
| US-020 | Jako gość chcę zrozumiałej strony, gdy link jest nieaktywny, aby wiedzieć, co się stało | Could | T-8 | **zrobione** (PR #68) |
| US-021 | Jako Projektant chcę, aby po błędzie walidacji formularz zachował wpisane dane, aby nie wpisywać ich od nowa | Could | T-10 | częściowo — formularze scenariusza (PR #68); typ regału i edycja stref do realizacji |
| US-022 | Jako Projektant chcę unikalnych nazw własnych modeli sprzętu, aby import nie kończył się błędem | Could | T-7 | do realizacji |
| US-025 | Jako Projektant chcę wiedzieć, że wynik przypięty do prezentacji został usunięty, aby nie pokazać zarządowi niepełnego pokazu | Could | T-9 | do realizacji |
| US-016 | Jako PO chcę osobnych sesji gości demo z ograniczeniem czasu, aby rozróżniać wizyty | Won't (na teraz) | R-13 | — |

## Kryteria akceptacji historyjek zrealizowanych w tym PR

**US-001**
- *Given* model sprzętu autora A, *When* Projektant B otwiera edycję albo wysyła usunięcie, *Then* dostaje 403, a model zostaje bez zmian.
- *Given* model bez autora (konto usunięte), *When* Projektant próbuje go edytować lub usunąć, *Then* 403; *When* Administrator — *Then* edycja działa.
- *Given* model autora A, *When* Projektant B otwiera kartę, *Then* nie widzi przycisków „Edytuj” i „Usuń”, ale może skopiować model.
- *Given* plik importu z nazwą cudzego modelu, *When* Projektant B importuje, *Then* wiersz jest pominięty z powodem „model innego użytkownika”; *When* importuje Administrator, *Then* model jest zaktualizowany.

**US-002**
- *Given* sprzęt używany w jednej grupie floty mieszanej, *When* autor go usuwa, *Then* komunikat mówi „Usunięto też grupy floty mieszanej z tym sprzętem: 1.”

**US-003**
- *Given* adres serwera `http://` inny niż komputer lokalny, *When* startuje stanowisko renderujące, *Then* kończy pracę z komunikatem o braku HTTPS.
- *Given* adres pliku podany w zleceniu bez HTTPS, *When* stanowisko ma go pobrać, *Then* odmawia przed wysłaniem tokenu.
- *Given* schemat inny niż http(s) (np. `file:`), *When* stanowisko dostaje taki adres, *Then* odmawia.

**US-006**
- *Given* żądanie z adresu w sieci wewnętrznej (proxy platformy), *When* liczony jest adres klienta, *Then* brany jest ostatni wpis `X-Forwarded-For`.
- *Given* żądanie wprost z internetu z podrobionym `X-Forwarded-For`, *When* liczony jest adres klienta, *Then* brany jest adres połączenia — blokady logowania nie da się obejść.

**US-011**
- *Given* `DEMO_PUBLIC=true` i w bazie import zadań, master lokalizacji albo import danych spoza demo, *When* startuje kontener, *Then* w logach jest ostrzeżenie z listą powodów, a start nie jest blokowany.
- *Given* ta sama sytuacja, *When* Administrator otwiera stronę startową, *Then* widzi baner ostrzegawczy; Podgląd i gość go nie widzą.
- *Given* tylko dane z `seed_demo` albo `DEMO_PUBLIC=false`, *Then* ostrzeżenia nie ma.

**US-019**
- *Given* rola Podgląd, *When* otwiera stronę startową, *Then* menu i kafle nie zawierają modułu zadań magazynowych (strona nadal zwraca 403).
- *Given* rola Podgląd, *When* otwiera widok hali, typy regałów i hub projektowania, *Then* nie widzi przycisków wklejania adresów, elementów hali, współrzędnych, nowego typu, generatora i importu zadań; puste stany nie zachęcają do akcji bez dostępu.

**US-004**
- *Given* hala z regałami i prezentacją 3D, *When* Projektant wybiera „Usuń”, *Then* widzi ekran z nazwą hali i liczbą regałów, wyników, prezentacji i zleceń usuwanych razem z nią; samo otwarcie ekranu niczego nie usuwa.
- *Given* scenariusz albo własny sprzęt we flocie mieszanej, *When* Projektant wybiera „Usuń”, *Then* ekran wymienia usuwane grupy floty i wyniki oraz obiekty, które tylko stracą powiązanie.
- *Given* rola Podgląd, *When* otwiera adres usunięcia, *Then* 403.

**Z-3 (obliczenia tylko dla Projektanta)**
- *Given* rola Podgląd albo gość, *When* otwiera symulację dnia bez wyniku policzonego wcześniej, *Then* nie startuje obliczenie; widzi informację „poproś Projektanta”.
- *Given* wynik policzony wcześniej przez Projektanta, *When* Podgląd go otwiera, *Then* widzi ten wynik.
- *Given* rola Podgląd, *When* otwiera kalibrację, *Then* kalibracja się nie liczy; Projektant liczy ją jak dotąd.

**US-012**
- *Given* plik historii zadań z loginem operatora, *When* Projektant go importuje albo podgląda, *Then* w bazie i na ekranie jest pseudonim „OP-…”, a login nie występuje nigdzie.
- *Given* ten sam login w dwóch importach, *Then* pseudonim jest ten sam (analiza ruchu nadal rozróżnia zasoby).
- *Given* historia zadań zapisana przed zmianą, *When* uruchamia się migracja, *Then* loginy zostają zastąpione pseudonimami; puste pola i pseudonimy zostają bez zmian.

**US-015**
- *Given* zlecenie renderu albo montażu przejęte 3 razy i porzucone, *When* serwer porządkuje zlecenia przeterminowane, *Then* zlecenie kończy się błędem z komunikatem o wyczerpaniu prób, zamiast wracać do kolejki.
- *Given* zlecenie po 1–2 porzuceniach, *Then* wraca do kolejki.

**US-020**
- *Given* nieistniejący albo wygasły adres, *When* gość go otwiera, *Then* widzi stronę „nie znaleziono” z wyjaśnieniem i przyciskiem logowania albo powrotu na start (kod 404).
- *Given* błąd serwera, *Then* użytkownik widzi stronę „błąd serwera” bez szczegółów technicznych (kod 500).

**US-021**
- *Given* formularz scenariusza z błędem walidacji, *When* Projektant go wysyła, *Then* po powrocie na kartę scenariusza formularz zawiera wpisane wartości i komunikat błędu; po odświeżeniu strony wartości nie wracają drugi raz.

**US-023**
- *Given* pokrycie logiki domenowej (`scenario/sim`, `ml`, `twin/layout.py`, `twin/design_*`) poniżej 80%, *When* działa CI, *Then* job `coverage` kończy się błędem.

**US-014**
- *Given* nowe ustalenie semgrep (reguły OWASP Top 10 i Django) albo trivy (Dockerfile; obraz: wysokie i krytyczne z poprawką), *When* działa CI, *Then* PR jest zablokowany.
- *Given* formularz POST w szablonie bez `{% csrf_token %}`, *When* działają testy, *Then* test `test_csrf_forms` wskazuje plik i linię.
- *Given* obraz produkcyjny, *Then* kontener działa jako użytkownik `app`, nie root.

**US-018**
- *Given* workflow CI, *Then* każda akcja jest przypięta pełnym skrótem commita z wersją w komentarzu; Dependabot proponuje nowe wersje po 7 dniach karencji.
