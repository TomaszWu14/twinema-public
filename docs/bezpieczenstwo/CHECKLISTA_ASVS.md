# Checklista OWASP ASVS

**[SEC]** · wybrany poziom: **ASVS 4.0.3, poziom 1** (minimum dla aplikacji internetowej), z wybranymi
wymaganiami poziomu 2 tam, gdzie dotyczą danych poufnych. Wyższy poziom — decyzja PO ([Z-25](../analiza/ZALOZENIA.md)).

Status: ✅ spełnione · ⚠️ częściowo · ❌ niespełnione · n/d nie dotyczy. Ocena na podstawie kodu z 2026-10-15.

| Rozdział | Wymaganie (skrót) | Status | Dowód / luka |
|---|---|---|---|
| V1 Architektura | dokumentacja przepływów i granic zaufania | ✅ | [THREAT_MODEL](THREAT_MODEL.md), [ARCHITEKTURA](../architektura/ARCHITEKTURA.md) |
| V2.1 Hasła | min. 12 znaków (L1) | ⚠️ | minimum 10 znaków + walidatory popularnych i numerycznych haseł; podniesienie do 12 — US-017 |
| V2.2 Ogólne | ochrona przed automatycznym zgadywaniem | ⚠️ | blokada login + IP; zależna od zaufanego proxy (R-05) |
| V2.4 Przechowywanie haseł | skrót z solą, odporny | ✅ | PBKDF2 Django |
| V2.5 Odzyskiwanie | bezpieczny reset hasła | n/d | brak samodzielnego resetu — reset przez Administratora |
| V2.8 MFA | drugi składnik (L2) | ❌ | R-11, US-017 |
| V3 Sesje | ciasteczka Secure, HttpOnly, SameSite; wylogowanie unieważnia sesję | ✅ | ustawienia produkcyjne, `LogoutView` |
| V3.3 Czas sesji | limit bezczynności | ✅ | 8 h odświeżane przy aktywności |
| V4.1 Kontrola dostępu | po stronie serwera, domyślnie odmowa | ✅ | dekoratory ról na każdym widoku; testy 403 |
| V4.2 Dostęp do obiektów | ochrona przed IDOR | ⚠️ | sprzęt: autor albo Administrator (US-001); pozostałe obiekty wspólne dla zespołu z założenia ([Z-26](../analiza/ZALOZENIA.md)) |
| V4.3 Administracja | panel administracyjny chroniony | ⚠️ | panel pod stałym adresem; bez MFA (R-11) |
| V5.1 Walidacja wejścia | walidacja po stronie serwera | ✅ | formularze Django, walidatory importów |
| V5.2 Sanityzacja | brak niebezpiecznego HTML | ✅ | autoescape, `safe_json`, `textContent`, `escapeHtml` |
| V5.3 Kodowanie wyjścia / wstrzyknięcia | brak SQL injection | ✅ | ORM; bandit bez ustaleń |
| V5.5 Deserializacja | bezpieczne parsowanie XML/JSON | ✅ | defusedxml, `json` |
| V7 Logowanie | brak sekretów w logach; dziennik zdarzeń bezpieczeństwa | ✅ | logi z identyfikatorem żądania; dziennik operacji wrażliwych dla Administratora (US-008) |
| V8 Ochrona danych | dane poufne niedostępne dla ról bez uprawnień | ✅ | scena dla Podglądu czyszczona; [klasyfikacja](KLASYFIKACJA_DANYCH.md) |
| V8.3 Dane osobowe | minimalizacja i retencja | ⚠️ | [RODO](RODO.md), R-06 |
| V9 Komunikacja | TLS, HSTS | ✅ | HSTS 1 rok, przekierowanie na HTTPS; stanowisko renderujące tylko HTTPS (US-003) |
| V10 Złośliwy kod | integralność zależności | ✅ | przypięte wersje, sumy SHA-256 bibliotek JS, pip-audit |
| V12 Pliki | limity rozmiaru, typ, przechowywanie poza katalogiem publicznym | ✅ | limity w importerach; media wydawane przez widoki |
| V13 API | uwierzytelnienie i autoryzacja API | ✅ | token stanowiska + jednorazowy klucz przejęcia; JSON-y aplikacji za rolą |
| V14.2 Zależności | aktualne komponenty | ✅ | Django 5.2 LTS, Dependabot |
| V14.4 Nagłówki | CSP, X-Content-Type-Options, Referrer-Policy, ramki | ✅ | nosniff, X-Frame-Options, Permissions-Policy; CSP wymuszana z nonce dla skryptów, `object-src 'none'`, `form-action 'self'` (US-005); style inline — T-17 |
| V14.5 Konfiguracja | brak trybu debug w produkcji, sekrety z env | ✅ | walidacja konfiguracji przy starcie; `check --deploy` w CI |
