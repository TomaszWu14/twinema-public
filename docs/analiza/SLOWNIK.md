# Słownik pojęć

**[BA]** · Pojęcia domenowe z odpowiednikami w kodzie (materiał, regał, scenariusz, wynik symulacji itd.) są w
[glosariuszu modelu danych](../02-dane/model-danych.md#glosariusz-domeny) — to jedno źródło, tu bez powtórzeń.
Poniżej pojęcia procesowe, analityczne i bezpieczeństwa używane w dokumentacji.

| Pojęcie | Znaczenie |
|---|---|
| Dzień typowy / szczytowy | dwa dni scenariusza: przeciętny i najbardziej obciążony |
| Dzień projektowy | dzień z historii ruchów o liczbie zadań równej wybranemu percentylowi (P90/P95/P99) — na niego projektuje się halę |
| P95 | wartość, której nie przekracza 95% przebiegów symulacji — miara „złego, ale realnego” dnia |
| Przebieg | jedno losowe odtworzenie dnia w symulacji (1–30 na wynik) |
| Wąskie gardło | zasób (doki, ludzie, wózki, miejsca), który ogranicza przepustowość dnia; system podaje przy nim propozycję poprawy |
| Kalibracja | wyznaczenie norm wydajności z historii ruchów obecnej hali |
| Klasa systemowa sprzętu | anonimowy wzorzec wózka z przybliżonymi parametrami, utrzymywany przez Administratora |
| Dane źródłowe | dane z systemu magazynowego (materiały, stany, lokalizacje, zadania) — klasa Poufne |
| Link publiczny | adres pokazu 3D z losowym kluczem i datą ważności, działający bez logowania |
| Gość | osoba bez konta korzystająca z demo publicznego (konto demo w roli Podgląd) |
| Stanowisko renderujące | komputer z Blenderem i ffmpeg, który pobiera zlecenia renderu i montażu |
| AS-IS / TO-BE | proces przed wdrożeniem / po wdrożeniu |
| SIPOC | dostawcy, wejścia, proces, wyjścia, odbiorcy — mapa procesu na wysokim poziomie |
| MoSCoW | priorytety: Must (musi), Should (powinno), Could (może), Won't (nie teraz) |
| Definition of Ready / Done | warunki rozpoczęcia / zakończenia historyjki ([CONTRIBUTING](../../CONTRIBUTING.md)) |
| ADR | zapis decyzji architektonicznej: kontekst, opcje, decyzja, konsekwencje |
| STRIDE | kategorie zagrożeń: podszycie (S), manipulacja (T), wyparcie się (R), ujawnienie informacji (I), odmowa usługi (D), podniesienie uprawnień (E) |
| ASVS | standard OWASP wymagań bezpieczeństwa aplikacji (poziomy 1–3) |
| SAST / SCA | statyczna analiza kodu / analiza podatności zależności |
| CSP | polityka bezpieczeństwa treści — nagłówek ograniczający, skąd przeglądarka ładuje skrypty i style |
| Pseudonimizacja | zastąpienie identyfikatora osoby identyfikatorem zastępczym bez możliwości odtworzenia bez informacji dodatkowych |
