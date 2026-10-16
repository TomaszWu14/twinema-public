# Wymagania

**[BA]** · wersja 0.1 · stan: wymagania odtworzone z działającego kodu + wymagania bezpieczeństwa z audytu.
Szczegółowe historyjki z kryteriami Given/When/Then dla funkcji istniejących są w procesach (identyfikatory WF-…);
tu jest indeks wymagań na poziomie zdolności systemu. Nowe historyjki: [HISTORYJKI.md](HISTORYJKI.md).

Status: **zrealizowane** (jest w kodzie i ma testy) · **częściowo** · **planowane** (w backlogu).

## Wymagania funkcjonalne

| ID | Wymaganie | Szczegóły (historyjki, reguły) | Priorytet | Status |
|---|---|---|---|---|
| FR-001 | System importuje materiały, master lokalizacji i stany z plików z raportem odrzuceń | [P1](../01-procesy/P1-dane-podstawowe.md) WF-101–103, BR-101–115 | Must | zrealizowane |
| FR-002 | System utrzymuje kartotekę materiałów, nośniki i klasy palet z ostrzeżeniami o niespójnym opakowaniu | P1 WF-104 | Must | zrealizowane |
| FR-003 | System wczytuje syntetyczne dane demo | P1 WF-105 | Should | zrealizowane |
| FR-004 | System importuje historię zadań magazynowych z podglądem przed zapisem i importem w tle | [P2](../01-procesy/P2-historia-ruchow-i-prognoza.md) WF-201–203 | Must | zrealizowane |
| FR-005 | System wyznacza dzień projektowy, kalibruje normy i prognozuje wzrost | P2 WF-204–205 | Must | zrealizowane |
| FR-006 | System porównuje do 4 wariantów hali na dniu projektowym | P2 WF-206 | Should | zrealizowane |
| FR-007 | System tworzy model hali generatorem, z pliku albo jako kopię | [P3](../01-procesy/P3-model-hali.md) WF-301, WF-305 | Must | zrealizowane |
| FR-008 | Edytor układu waliduje plan po każdej zmianie i blokuje zapis planu z błędami | P3 WF-302–304 | Must | zrealizowane |
| FR-009 | System odtwarza adresowanie regałów z mastera lokalizacji | P3 WF-306 | Should | zrealizowane |
| FR-010 | System utrzymuje katalog sprzętu z krzywą udźwigu, osprzętem i importem | [P4](../01-procesy/P4-katalog-sprzetu.md) WF-401–403 | Must | zrealizowane |
| FR-011 | System utrzymuje stawki kosztowe i liczy widełki CAPEX/OPEX | P4 WF-404 | Should | zrealizowane |
| FR-012 | System przechowuje scenariusz dnia niezależny od układu hali (min/śr./max) | [P5](../01-procesy/P5-scenariusz-i-symulacja.md) WF-501–502 | Must | zrealizowane |
| FR-013 | System symuluje dzień na wybranym układzie, podaje KPI średnią i P95 oraz wąskie gardła z podpowiedzią | P5 WF-503–504 | Must | zrealizowane |
| FR-014 | System porównuje wyniki i odtwarza animację dnia | P5 WF-505–506 | Should | zrealizowane |
| FR-015 | System tworzy prezentację 3D ze szablonu i udostępnia ją linkiem z datą ważności | [P6](../01-procesy/P6-prezentacja-3d.md) WF-601–604 | Must | zrealizowane |
| FR-016 | System przygotowuje film z napisami i deck PDF po zatwierdzeniu tekstu | [P7](../01-procesy/P7-film-i-deck.md) WF-701–704 | Could | zrealizowane (bez pełnej próby z renderem) |
| FR-017 | System ogranicza dostęp według ról i blokuje zgadywanie haseł | [P8](../01-procesy/P8-dostep-i-demo.md) WF-801–802 | Must | zrealizowane |
| FR-018 | System udostępnia demo publiczne i wejście gościa tylko do odczytu | P8 WF-803–805 | Should | zrealizowane |
| FR-019 | Własny model sprzętu zmienia i usuwa tylko jego autor albo Administrator | US-001 | Must | zrealizowane (ten PR) |
| FR-020 | Usunięcie obiektu wymaga potwierdzenia, które wymienia obiekty usuwane razem z nim | US-004 | Must | zrealizowane (PR #68) |
| FR-021 | Rola Podgląd nie widzi pozycji menu i przycisków prowadzących do stron bez dostępu | US-019 | Should | zrealizowane (PR #68) |
| FR-022 | System zapisuje dziennik operacji wrażliwych (kto, co, kiedy) | US-008 | Should | zrealizowane (PR #68) |
| FR-023 | Import historii zadań pseudonimizuje albo pomija login operatora | US-012 | Must | zrealizowane (PR #68) |

## Wymagania niefunkcjonalne

| ID | Kategoria | Wymaganie | Kryterium | Status |
|---|---|---|---|---|
| NFR-001 | Bezpieczeństwo | konfiguracja sprawdzana przy starcie | brak klucza aplikacji, za krótki token, złe hasło demo → aplikacja nie startuje | zrealizowane (N-01) |
| NFR-002 | Bezpieczeństwo | stanowisko renderujące bez otwartych portów, tylko HTTPS | token ≥ 32 znaki, jednorazowy klucz przejęcia, HTTPS poza komputerem lokalnym | zrealizowane (N-02, US-003) |
| NFR-003 | Bezpieczeństwo | weryfikacja plików wyniku renderu | sygnatura PNG/MP4, ≤ 500 MB | zrealizowane (N-03) |
| NFR-004 | Bezpieczeństwo | biblioteki przeglądarki bez CDN w czasie pracy | suma SHA-256 przy budowie | zrealizowane (N-04) |
| NFR-005 | Dostępność / utrzymanie | kontrola działania | adres kontroli zwraca stan bazy i wersję; 503 przy braku bazy | zrealizowane (N-05) |
| NFR-006 | Jakość | logika obliczeniowa testowalna bez bazy, testy w CI | testy przy każdym PR | zrealizowane (N-06) |
| NFR-007 | Bezpieczeństwo | sesja i hasła | sesja 8 h, hasło ≥ 10 znaków, blokada 5 prób / 1 h | zrealizowane (N-07) |
| NFR-008 | Bezpieczeństwo | ochrona pokazu publicznego | noindex, no-referrer, no-store | zrealizowane (N-08) |
| NFR-009 | Ochrona danych | Podgląd i goście bez danych źródłowych; do AI tylko zagregowane liczby | testy roli Podgląd | zrealizowane (N-09) |
| NFR-010 | Bezpieczeństwo | CI blokuje sekrety, podatne zależności i ustalenia SAST od wagi średniej | gitleaks, pip-audit, bandit | zrealizowane (ten PR) |
| NFR-011 | Bezpieczeństwo | CSP wymuszana, bez `'unsafe-inline'` dla skryptów | nagłówek `Content-Security-Policy` w produkcji | planowane (US-005) |
| NFR-012 | Wydajność | żadne żądanie nie przekracza limitu serwera; długie obliczenia w tle | 0 przekroczeń limitu 120 s | częściowo (PR #68): symulacje i kalibracja w kolejce zadań (US-007); reszta — T-1 |
| NFR-013 | Dostępność | kopia zapasowa bazy i plików z próbą odtworzenia | RPO / RTO do ustalenia przez PO | planowane (US-009) |
| NFR-014 | Ochrona danych | retencja danych osobowych zgodna z [RODO](../bezpieczenstwo/RODO.md) | okresy z rejestru czynności | planowane |
| NFR-015 | Jakość | próg pokrycia testami | 80% dla logiki domenowej, blokujące w CI (decyzja PO) | zrealizowane (PR #68) |
| NFR-016 | Użyteczność | interfejs po polsku, komunikaty mówią, co zrobić dalej | przegląd [BA] przy każdym PR | zrealizowane (zasada) |
| NFR-017 | Wydajność / skala | obsługa rzeczywistych wolumenów | do ustalenia (Z-5, Z-17) | do potwierdzenia |
