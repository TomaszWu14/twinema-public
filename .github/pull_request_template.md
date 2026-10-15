## Co i dlaczego

<!-- Krótko: co zmienia PR i jaki problem rozwiązuje. -->

- Historyjka: US-nnn · Wymaganie: FR-nnn / NFR-nnn · Ryzyko: R-nn

## Jak przetestować

1.

<!-- Zrzuty ekranu, jeśli zmienia się interfejs. -->

## [DEV] Implementacja

- [ ] Testy dla każdego kryterium akceptacji, w tym „brak dostępu” dla ról bez uprawnień
- [ ] Lint, testy i migracje zielone lokalnie
- [ ] Dokumentacja zaktualizowana (wymagania, API, model danych, ADR jeśli dotyczy)
- [ ] Wpis w CHANGELOG.md

## [SEC] Przegląd bezpieczeństwa — wynik: ✅ / ⚠️ uwagi / ❌ blokada

- [ ] Uwierzytelnianie i sesje bez zmian albo przejrzane
- [ ] Autoryzacja sprawdzana po stronie serwera dla każdego nowego widoku i obiektu
- [ ] Walidacja wejścia; ORM bez surowego SQL z danymi użytkownika
- [ ] Wyjście escapowane (szablony, `safe_json`, `textContent`); brak nowego `|safe` / `mark_safe` na danych
- [ ] CSRF dla operacji zmieniających stan (POST)
- [ ] Upload: limit rozmiaru, walidacja typu, pliki poza katalogiem publicznym
- [ ] Brak sekretów, danych osobowych i produkcyjnych w kodzie, testach i logach
- [ ] Nagłówki bezpieczeństwa bez osłabień
- [ ] Zależności: nowe przypięte, pip-audit czysty
- [ ] Integracja z AI: tylko zagregowane dane, odpowiedź traktowana jako dane, nie polecenia
- [ ] Skany (bandit, semgrep, trivy): nowe ustalenia ocenione; fałszywe alarmy oznaczone pojedynczo z uzasadnieniem

Uwagi SEC:

## [BA] Odbiór

- [ ] Kryteria akceptacji spełnione punkt po punkcie
- [ ] Komunikaty i UI zrozumiałe dla roli docelowej
- [ ] Macierz śledzenia (docs/analiza/SLEDZENIE.md) zaktualizowana

## Ryzyka i decyzje dla PO

<!-- Co zostaje otwarte, co wymaga akceptacji. Merge tylko po akceptacji PO. -->
