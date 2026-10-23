# Ochrona danych osobowych (RODO)

**[SEC] + [BA]** · wersja 0.1 · status: propozycja — podstawy prawne, administratora danych i okresy
przechowywania musi potwierdzić PO (z inspektorem ochrony danych, jeśli jest wyznaczony).

System **nie jest systemem kadrowym ani CRM** — dane osobowe są w nim tylko pomocniczo. Poniżej rejestr czynności
przetwarzania odtworzony z kodu.

## Rejestr czynności przetwarzania

| Nr | Czynność | Kategorie osób | Dane | Cel | Proponowana podstawa (art. 6 RODO) | Okres przechowywania — propozycja | Stan w kodzie |
|---|---|---|---|---|---|---|---|
| CP-1 | Konta użytkowników | pracownicy i współpracownicy zespołu projektowego, decydenci | login, e-mail, imię, nazwisko, skrót hasła, grupa, daty logowania | dostęp do systemu i rozliczalność | 6(1)(f) prawnie uzasadniony interes albo 6(1)(b) umowa | do odebrania dostępu + 30 dni | konto usuwa Administrator; obiekty zostają bez autora |
| CP-2 | Ochrona logowania | osoby logujące się | login, adres IP, user agent, czas | bezpieczeństwo (blokada zgadywania haseł) | 6(1)(f) | 30 dni (decyzja PO, `LOGIN_ATTEMPT_RETENTION_DAYS`) | wpisy django-axes usuwa `audit_prune` przy starcie kontenera (NFR-014) |
| CP-3 | Logi serwera i monitoring błędów | użytkownicy i goście | adres IP, adres URL, identyfikator żądania, ślad błędu bez danych osobowych | utrzymanie i bezpieczeństwo | 6(1)(f) | 30 dni (logi), według ustawień usługi monitoringu | retencja po stronie platformy hostingowej |
| CP-4 | Historia zadań magazynowych | pracownicy magazynu (operatorzy) | login operatora z systemu magazynowego, czasy potwierdzeń zadań | projektowanie hali na rzeczywistym ruchu | do ustalenia ([Z-24](../analiza/ZALOZENIA.md)) | do usunięcia partii; propozycja: maks. 12 miesięcy | od 2026-10-16 (decyzja PO, US-012): przy imporcie i podglądzie login zastępowany stałym pseudonimem „OP-…” (HMAC z kluczem pochodnym klucza aplikacji); migracja zastąpiła loginy już zapisane |
| CP-5 | Demo publiczne | goście | adres IP w logach | prezentacja systemu | 6(1)(f) | jak CP-3 | wspólne konto demo, bez danych identyfikujących gościa |
| CP-6 | Dziennik operacji wrażliwych | użytkownicy z kontem | login, adres IP, czas, rodzaj operacji i nazwa obiektu | rozliczalność usunięć, importów i udostępnień (bezpieczeństwo) | 6(1)(f) | 365 dni (`AUDIT_RETENTION_DAYS`, decyzja PO — Z-33) | od US-008; wpisy usuwa `audit_prune` przy starcie kontenera; widzi tylko Administrator |
| CP-7 | Bramka odwiedzających publiczne demo | odwiedzający `/demo/` | imię, nazwisko, firma (bez IP i user-agenta) | kontrola dostępu do demo i statystyka odwiedzin portfolio | 6(1)(f) | 90 dni (`DemoVisitor.RETENTION_DAYS`) | zgoda-informacja przy formularzu; wpisy usuwa zapis kolejnego odwiedzającego i `audit_prune`; widzi tylko Administrator (panel `/admin/`) |

## Ocena ryzyka

- **CP-4 było najważniejszym ryzykiem — zamknięte decyzją PO (pseudonimizacja, US-012).** Login operatora z czasami zadań pozwala odtworzyć tempo pracy
  konkretnej osoby — to profilowanie wydajności pracowników, które wymaga podstawy prawnej, informacji dla
  pracowników i zwykle uzgodnienia z przedstawicielami załogi. Projekt hali nie potrzebuje tożsamości osób,
  tylko rozróżnienia zasobów. Rekomendacja [SEC]: **pseudonimizacja przy imporcie** (stały identyfikator
  zastępczy zamiast loginu) albo **pominięcie pola** — decyzja PO (R-06, US-012).
- Dane kont (CP-1, CP-2) są minimalne; próby logowania są usuwane po 30 dniach (decyzja PO, NFR-014).

## Prawa osób

| Prawo | Realizacja dziś | Luka |
|---|---|---|
| Dostęp i kopia danych (art. 15, 20) | Administrator odczytuje konto w panelu administracyjnym | brak eksportu danych jednej osoby; dla CP-4 — brak wyszukiwania po loginie operatora |
| Sprostowanie (art. 16) | Administrator edytuje konto | — |
| Usunięcie (art. 17) | usunięcie konta; usunięcie partii zadań | brak usunięcia danych jednego operatora z historii zadań |
| Sprzeciw (art. 21) | — | dla CP-4 nie dotyczy po pseudonimizacji (system nie identyfikuje osób) |

Po pseudonimizacji (US-012) prawa z CP-4 realizuje się po stronie systemu magazynowego (źródła), a TWINEMA
nie przechowuje danych pozwalających zidentyfikować osobę bez informacji dodatkowych.

## Zasady

- **Minimalizacja:** nowe funkcje nie zbierają danych osobowych bez historyjki z oceną [SEC].
- **Dane testowe:** wyłącznie syntetyczne; w testach nie używa się loginów przypominających prawdziwe osoby
  (A-10 w [Do anonimizacji](../05-decyzje-i-ograniczenia.md#do-anonimizacji)).
- **Podmioty przetwarzające:** platforma hostingowa, monitoring błędów (opcjonalnie), usługa AI (opcjonalnie,
  bez danych osobowych) — umowy powierzenia do potwierdzenia przez PO.
