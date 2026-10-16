# Klasyfikacja danych

**[SEC]** · wersja 0.1 · status: do zatwierdzenia przez PO

Klasy określają, kto może widzieć dane i jak je chronić. Klasy ustalono na podstawie modelu danych
([model-danych.md](../02-dane/model-danych.md)) i uprawnień ról ([P8](../01-procesy/P8-dostep-i-demo.md)).

## Klasy

| Klasa | Definicja | Kto widzi | Wymagana ochrona |
|---|---|---|---|
| **Publiczne** | przeznaczone do pokazania każdemu | wszyscy, także bez konta | integralność; brak danych źródłowych |
| **Wewnętrzne** | wyniki pracy projektowej, bez danych źródłowych | wszystkie role zalogowane (Administrator, Projektant, Podgląd) | logowanie, sesja, autoryzacja |
| **Poufne** | dane źródłowe magazynu i koszty | Projektant, Administrator | jak wyżej + brak w scenie dla Podglądu, brak wysyłki do AI, brak w logach |
| **Dane osobowe** | informacje o osobie fizycznej | według celu przetwarzania | jak poufne + [RODO](RODO.md): minimalizacja, retencja, prawa osób |
| **Sekrety** | klucze i tokeny dostępowe | tylko konfiguracja serwera i stanowiska | wyłącznie zmienne środowiskowe; nigdy w repozytorium, logach ani interfejsie |

## Przypisanie danych do klas

| Dane | Encja / miejsce | Klasa | Uwagi |
|---|---|---|---|
| Pokaz publiczny (slajdy, scena 3D bez danych źródłowych, KPI) | `Showcase` przez link publiczny | Publiczne | ważny do daty wygaśnięcia; link to sekret dostępowy |
| Dane i pokaz demo | `seed_demo`, konto demo | Publiczne | dane syntetyczne |
| Układ hali, regały, elementy, działka | `WarehouseModel` i powiązane | Wewnętrzne | |
| Scenariusze, wyniki symulacji, animacja dnia | `Scenario`, `ScenarioRun` | Wewnętrzne | |
| Katalog sprzętu, klasy systemowe | `Equipment` | Wewnętrzne | producent tylko w danych użytkownika |
| Prezentacje 3D i filmowe, rendery | `Showcase`, `Presentation`, `RenderJob` | Wewnętrzne | po udostępnieniu linkiem: Publiczne |
| Kartoteka materiałów (kody, nazwy, wymiary, cechy) | `Material` | **Poufne** | |
| Stany magazynu (lokalizacja, ilość, jednostka ładunkowa, partia, termin) | `StockItem` | **Poufne** | |
| Master lokalizacji | `WarehouseLocationMaster` | **Poufne** | |
| Historia zadań magazynowych | `WarehouseTask` | **Poufne** (dane osobowe pseudonimizowane) | pole „Użytkownik” zawiera pseudonim „OP-…” zamiast loginu pracownika (US-012) |
| Wyniki ML (prognoza, segmenty) | `ModelRun` | Poufne | segmenty zawierają kody materiałów |
| Stawki i koszty | `CostRate`, koszty sprzętu | Poufne | |
| Raporty importu z próbkami odrzuconych wierszy | `ImportLog.rejects` | Poufne | |
| Konta użytkowników (login, e-mail, imię, nazwisko, hasło — skrót) | `auth_user` | **Dane osobowe** | hasło jako skrót PBKDF2 |
| Autor obiektów (`created_by`, `uploaded_by`) | wiele encji | Dane osobowe (pośrednio) | identyfikator konta |
| Próby logowania (login, adres IP, user agent) | django-axes | **Dane osobowe** | |
| Logi dostępu serwera (IP, adres URL, identyfikator żądania) | stdout kontenera | **Dane osobowe** | adres pokazu publicznego zawiera klucz linku |
| Klucz aplikacji, hasło bazy, token stanowiska, klucz AI, hasło demo, adres monitoringu | zmienne środowiskowe | **Sekrety** | [config.py](../../web/twinema/config.py) waliduje przy starcie |

## Zasady obsługi

- **Rola Podgląd i goście** nie dostają danych poufnych: scena 3D jest czyszczona z kodów materiałów,
  jednostek ładunkowych, partii i kodów lokalizacji; ekrany importów i kartoteki zwracają 403.
- **Usługa AI** dostaje wyłącznie zdania z zagregowanymi liczbami (klasa Wewnętrzne).
- **Monitoring błędów** działa z wyłączonym wysyłaniem danych osobowych (`send_default_pii=False`).
- **Dane testowe i demo** są syntetyczne; danych produkcyjnych nie wolno umieszczać w repozytorium, testach ani
  zgłoszeniach (Definition of Done).
- **Pliki od użytkownika** (importy, podkłady, rendery) leżą w katalogu mediów poza katalogiem publicznym
  i są wydawane przez widoki sprawdzające rolę.
