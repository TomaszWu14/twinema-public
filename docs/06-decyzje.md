# 06. Dziennik decyzji

Decyzje projektowe widoczne w kodzie. Przy każdej podane jest źródło uzasadnienia. Gdzie uzasadnienia
nie zapisano w trakcie prac, jest to powiedziane wprost — opisane są wtedy tylko kontekst i skutki,
które wynikają z kodu.

| ID | Decyzja | Uzasadnienie zapisane? |
|---|---|---|
| [D1](#d1-dane-tylko-z-plików-bez-integracji-na-żywo) | Dane tylko z plików, bez integracji na żywo | tak — ADR-0001 |
| [D2](#d2-kopia-kodu-zamiast-przeniesienia-albo-wspólnej-biblioteki) | Kopia kodu zamiast przeniesienia albo wspólnej biblioteki | tak — ADR-0001 |
| [D3](#d3-scenariusz-niezależny-od-układu-hali) | Scenariusz niezależny od układu hali | tak — `ZALOZENIA.md` #20 |
| [D4](#d4-wolumeny-jako-minśrmax-wiele-przebiegów-wynik-p95) | Wolumeny jako min/śr/max, wiele przebiegów, wynik P95 | częściowo |
| [D5](#d5-kolejka-renderów-bez-celery-worker-odpytuje-serwer) | Kolejka renderów bez Celery, worker odpytuje serwer | tak — `PLAN.md` D6 |
| [D6](#d6-prezentacja-3d-w-przeglądarce-przed-filmem) | Prezentacja 3D w przeglądarce przed filmem | tak — `PLAN.md` |
| [D7](#d7-rola-podgląd-bez-danych-źródłowych) | Rola Podgląd bez danych źródłowych | tak — `ZALOZENIA.md` #25 |
| [D8](#d8-błąd-layoutu-blokuje-zapis-ostrzeżenie-nie) | Błąd layoutu blokuje zapis, ostrzeżenie nie | nie |
| [D9](#d9-klucze-integracji-jako-tekst-zamiast-kluczy-obcych) | Klucze integracji jako tekst zamiast kluczy obcych | nie |
| [D10](#d10-obliczenia-synchroniczne-w-żądaniu) | Obliczenia synchroniczne w żądaniu | nie |
| [D11](#d11-logika-obliczeniowa-bez-django) | Logika obliczeniowa bez Django | częściowo |
| [D12](#d12-biblioteki-js-w-repozytorium-nie-z-cdn) | Biblioteki JS w repozytorium, nie z CDN | tak — `fetch_vendor.sh` |
| [D13](#d13-do-ai-tylko-zagregowane-liczby-tekst-zatwierdza-człowiek) | Do AI tylko zagregowane liczby, tekst zatwierdza człowiek | częściowo |

---

### D1. Dane tylko z plików, bez integracji na żywo

- **Kontekst:** dane magazynu są w systemie magazynowym (SAP EWM / WMS). TWINEMA ma służyć do projektowania, nie do bieżącej pracy.
- **Rozważane opcje:** ADR rozważa sposób przejęcia kodu (D2). Integracja przez API z systemem magazynowym nie jest w dokumentach opisana jako rozważona opcja.
- **Dlaczego ta:** „Dane płyną wyłącznie przez importy plików” — brak zależności między wdrożeniami ([ADR-0001](adr/0001-kopia-nie-przeniesienie.md)).
- **Skutki:** każdy import ma raport odrzuceń (R-06); dane mogą być nieaktualne — aktualizacja = ponowny import; model danych musi tolerować kody, których nie ma w drugim zbiorze (D9).

### D2. Kopia kodu zamiast przeniesienia albo wspólnej biblioteki

- **Kontekst:** część kodu (modelowanie hali, symulacja, eksport do Blendera) powstała w innym repozytorium autora.
- **Rozważane opcje:** przeniesienie, kopia, wspólna biblioteka.
- **Dlaczego ta:** źródło działa dalej bez zmian; wspólna biblioteka dopiero wtedy, gdy oba repozytoria realnie edytują te same pliki ([ADR-0001](adr/0001-kopia-nie-przeniesienie.md)).
- **Skutki:** poprawki nie wracają automatycznie do źródła; pochodzenie kodu opisane w `PROVENANCE.md`; z kopii usunięto odniesienia do firm i lokalizacji.

### D3. Scenariusz niezależny od układu hali

- **Kontekst:** projektant porównuje obecny i przyszły układ.
- **Rozważane opcje:** parametry wolumenów zapisane przy modelu hali albo osobny obiekt „Scenariusz”.
- **Dlaczego ta:** „ten sam scenariusz testuje różne layouty” — porównanie wariantów na tych samych danych ([ZALOZENIA.md](ZALOZENIA.md) #1 i #20).
- **Skutki:** wynik symulacji (`ScenarioRun`) to para scenariusz × model hali; tabela porównania pokazuje różnicę % przy identycznym wejściu (R-26). Usunięcie hali usuwa jej wyniki ([04](04-model-danych.md)).

### D4. Wolumeny jako min/śr/max, wiele przebiegów, wynik P95

- **Kontekst:** liczba aut, palet i zamówień zmienia się z dnia na dzień.
- **Rozważane opcje:** nieudokumentowane. Oczywista alternatywa to jedna wartość średnia.
- **Dlaczego ta:** „Liczby […] zawsze edytowalne, zwykle jako min / średnio / max”; „ziarno zapisane w scenariuszu (powtarzalnie); KPI z kilkunastu przebiegów: średnia i najgorszy przypadek (P95)” ([ZALOZENIA.md](ZALOZENIA.md) nagłówek i 10D). Wybór rozkładu trójkątnego w kodzie (`scenario/sim/plan.py`) nie ma zapisanego uzasadnienia.
- **Skutki:** walidacja 0 ≤ min ≤ śr ≤ max we wszystkich trójkach (R-20); symulacja trwa dłużej (1–30 przebiegów); wynik pokazuje najgorszy przypadek, nie tylko przeciętny dzień.

### D5. Kolejka renderów bez Celery, worker odpytuje serwer

- **Kontekst:** render w Blenderze wymaga GPU; serwer aplikacji go nie ma.
- **Rozważane opcje:** Celery + Redis albo tabela zleceń + worker na PC odpytujący serwer po HTTPS.
- **Dlaczego ta:** „Serwer bez GPU i bez otwartych portów do Redisa — wystarczy HTTPS. PC wyłączony = zlecenia czekają w kolejce” ([PLAN.md](PLAN.md), decyzja D6). Celery miało dojść, jeśli TTS lub montaż po stronie serwera tego wymagają — nie doszło.
- **Skutki:** token workera i jednorazowy klucz przejęcia (N-02); zlecenie „w toku” wraca do kolejki po 120 min, ale tylko przy kolejnym zgłoszeniu workera; bez workera zlecenia czekają bez końca ([07](07-ograniczenia.md)).

### D6. Prezentacja 3D w przeglądarce przed filmem

- **Kontekst:** po zbudowaniu Studia (film z lektorem) trzeba było wybrać kierunek dalszych prac.
- **Rozważane opcje:** dopracować film i montaż albo edytor layoutu i pokaz w przeglądarce.
- **Dlaczego ta:** „Film i montaż odstawione na bok; główny cel = pokazać w przeglądarce, jak może wyglądać przyszły layout” ([PLAN.md](PLAN.md), priorytet od 2026-10-05; [ZALOZENIA.md](ZALOZENIA.md)).
- **Skutki:** powstały edytor 2D/3D, animacja dnia i prezentacja 3D z publicznym linkiem; Studio jest zbudowane i przetestowane jednostkowo, ale nie przeszło pełnej próby z prawdziwym lektorem i renderem.

### D7. Rola Podgląd bez danych źródłowych

- **Kontekst:** pokaz ogląda zarząd albo osoba z zewnątrz.
- **Rozważane opcje:** nieudokumentowane.
- **Dlaczego ta:** Podgląd „widzi wyniki i 3D (layout, animacja dnia, KPI, wąskie gardła, scenariusze), bez danych źródłowych i bez edycji” ([ZALOZENIA.md](ZALOZENIA.md) #25).
- **Skutki:** scena 3D dla Podglądu jest czyszczona z SKU, HU, partii i kodów lokalizacji (R-02); importy i zadania magazynowe dają 403. Menu tego nie odzwierciedla — Podgląd widzi moduły, do których nie ma dostępu ([07](07-ograniczenia.md)).

### D8. Błąd layoutu blokuje zapis, ostrzeżenie nie

- **Kontekst:** edytor sprawdza plan po każdej zmianie.
- **Rozważane opcje:** nieudokumentowane.
- **Dlaczego ta:** uzasadnienie nie zostało zapisane. Kod rozdziela problemy na dwie klasy: błąd (kolizja, regał poza halą, w doku, za wysoki) i ostrzeżenie (za wąska alejka, droga piesza, nośność).
- **Skutki:** w bazie nie może się znaleźć plan fizycznie niemożliwy (R-17); plan z ostrzeżeniami da się zapisać i zasymulować. Dodatkowo blokada optymistyczna: równoległa zmiana modelu → 409.

### D9. Klucze integracji jako tekst zamiast kluczy obcych

- **Kontekst:** stan magazynu wskazuje materiał i lokalizację.
- **Rozważane opcje:** nieudokumentowane.
- **Dlaczego ta:** uzasadnienie nie zostało zapisane. Kod opisuje to jako zasadę: „Klucze integracji to stringi (kod materiału, kod lokalizacji), bez FK do modelu hali” (`web/masterdata/models.py:3-4`, `web/twin/models.py:2`).
- **Skutki:** każdy plik można wgrać niezależnie, w dowolnej kolejności (zgodne z D1); baza nie pilnuje spójności — stan może wskazywać materiał albo lokalizację, których nie ma ([04](04-model-danych.md)).

### D10. Obliczenia synchroniczne w żądaniu

- **Kontekst:** symulacja, import danych, przebiegi ML i szkic AI trwają od sekund do minut.
- **Rozważane opcje:** nieudokumentowane. Kolejka zadań istnieje tylko dla renderu (D5) i dużych importów zadań magazynowych (wątek w tle).
- **Dlaczego ta:** uzasadnienie nie zostało zapisane.
- **Skutki:** prosta architektura bez brokera; ryzyko przekroczenia limitu 120 s serwera przy dużych symulacjach i przy szkicu z Claude ([07](07-ograniczenia.md)).

### D11. Logika obliczeniowa bez Django

- **Kontekst:** symulacja, ML, geometria i walidacja układu to najważniejsza i najbardziej złożona część systemu.
- **Rozważane opcje:** nieudokumentowane.
- **Dlaczego ta:** „Czysty Python (bez ORM) — testowalny bez bazy” (docstringi modułów, np. `web/twin/ewm_levels.py`, `web/studio/script.py`).
- **Skutki:** szybkie testy jednostkowe (N-06); widoki tylko przygotowują dane i wywołują logikę.

### D12. Biblioteki JS w repozytorium, nie z CDN

- **Kontekst:** scena 3D (three.js) i wykresy (ECharts).
- **Rozważane opcje:** ładowanie z CDN w przeglądarce albo pobranie przy budowie.
- **Dlaczego ta:** „aplikacja nie zależy od CDN w runtime (CSP, awarie CDN)” (`web/scripts/fetch_vendor.sh`).
- **Skutki:** sumy SHA-256 sprawdzane przy budowie (N-04); lokalnie trzeba raz uruchomić skrypt.

### D13. Do AI tylko zagregowane liczby, tekst zatwierdza człowiek

- **Kontekst:** Studio może poprosić Claude o szkic narracji filmu.
- **Rozważane opcje:** nieudokumentowane.
- **Dlaczego ta:** `web/studio/script.py`: zdania z ZAGREGOWANYMI liczbami — „Tylko to (bez nazw modelu, materiałów, lokalizacji) wolno wysłać do modelu językowego”; `web/studio/models.py`: „nic nie idzie do lektora ani renderu przed akceptacją”. Powód (ochrona danych, kontrola treści) nie jest zapisany wprost.
- **Skutki:** prompt zawiera tylko zdania z KPI modelu (R-34); status „tekst zatwierdzony” jest bramką przed lektorem (R-32).
