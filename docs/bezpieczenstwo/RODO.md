# Ochrona danych osobowych (RODO)

**[SEC] + [BA]** · wersja 0.1 · status: propozycja — podstawy prawne, administratora danych i okresy
przechowywania musi potwierdzić PO (z inspektorem ochrony danych, jeśli jest wyznaczony).

System **nie jest systemem kadrowym ani CRM** — dane osobowe są w nim tylko pomocniczo. Poniżej rejestr czynności
przetwarzania odtworzony z kodu.

## Rejestr czynności przetwarzania

| Nr | Czynność | Kategorie osób | Dane | Cel | Proponowana podstawa (art. 6 RODO) | Okres przechowywania — propozycja | Stan w kodzie |
|---|---|---|---|---|---|---|---|
| CP-1 | Konta użytkowników | pracownicy i współpracownicy zespołu projektowego, decydenci | login, e-mail, imię, nazwisko, skrót hasła, grupa, daty logowania | dostęp do systemu i rozliczalność | 6(1)(f) prawnie uzasadniony interes albo 6(1)(b) umowa | do odebrania dostępu + 30 dni | konto usuwa Administrator; obiekty zostają bez autora |
| CP-2 | Ochrona logowania | osoby logujące się | login, adres IP, user agent, czas | bezpieczeństwo (blokada zgadywania haseł) | 6(1)(f) | 30 dni | wpisy django-axes bez automatycznego czyszczenia |
| CP-3 | Logi serwera i monitoring błędów | użytkownicy i goście | adres IP, adres URL, identyfikator żądania, ślad błędu bez danych osobowych | utrzymanie i bezpieczeństwo | 6(1)(f) | 30 dni (logi), według ustawień usługi monitoringu | retencja po stronie platformy hostingowej |
| CP-4 | Historia zadań magazynowych | pracownicy magazynu (operatorzy) | login operatora z systemu magazynowego, czasy potwierdzeń zadań | projektowanie hali na rzeczywistym ruchu | do ustalenia ([Z-24](../analiza/ZALOZENIA.md)) | do usunięcia partii; propozycja: maks. 12 miesięcy | pole zapisywane w całości, używane jako etykieta wózka w animacji; partię usuwa Projektant |
| CP-5 | Demo publiczne | goście | adres IP w logach | prezentacja systemu | 6(1)(f) | jak CP-3 | wspólne konto demo, bez danych identyfikujących gościa |

## Ocena ryzyka

- **CP-4 jest najważniejszym ryzykiem.** Login operatora z czasami zadań pozwala odtworzyć tempo pracy
  konkretnej osoby — to profilowanie wydajności pracowników, które wymaga podstawy prawnej, informacji dla
  pracowników i zwykle uzgodnienia z przedstawicielami załogi. Projekt hali nie potrzebuje tożsamości osób,
  tylko rozróżnienia zasobów. Rekomendacja [SEC]: **pseudonimizacja przy imporcie** (stały identyfikator
  zastępczy zamiast loginu) albo **pominięcie pola** — decyzja PO (R-06, US-012).
- Dane kont (CP-1, CP-2) są minimalne; brak automatycznej retencji wpisów prób logowania (US-008 obejmuje
  przegląd retencji logów).

## Prawa osób

| Prawo | Realizacja dziś | Luka |
|---|---|---|
| Dostęp i kopia danych (art. 15, 20) | Administrator odczytuje konto w panelu administracyjnym | brak eksportu danych jednej osoby; dla CP-4 — brak wyszukiwania po loginie operatora |
| Sprostowanie (art. 16) | Administrator edytuje konto | — |
| Usunięcie (art. 17) | usunięcie konta; usunięcie partii zadań | brak usunięcia danych jednego operatora z historii zadań |
| Sprzeciw (art. 21) | — | dla CP-4 zależny od decyzji o pseudonimizacji |

Po pseudonimizacji (US-012) prawa z CP-4 realizuje się po stronie systemu magazynowego (źródła), a TWINEMA
nie przechowuje danych pozwalających zidentyfikować osobę bez informacji dodatkowych.

## Zasady

- **Minimalizacja:** nowe funkcje nie zbierają danych osobowych bez historyjki z oceną [SEC].
- **Dane testowe:** wyłącznie syntetyczne; w testach nie używa się loginów przypominających prawdziwe osoby
  (A-10 w [Do anonimizacji](../05-decyzje-i-ograniczenia.md#do-anonimizacji)).
- **Podmioty przetwarzające:** platforma hostingowa, monitoring błędów (opcjonalnie), usługa AI (opcjonalnie,
  bez danych osobowych) — umowy powierzenia do potwierdzenia przez PO.
