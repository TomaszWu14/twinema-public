# 07. Ograniczenia, znane problemy, co dalej

Ścieżki względne do `web/`. Lista to obserwacje z analizy kodu, nie zobowiązania.

## Czego nie ma

| Brak | Skutek dla użytkownika |
|---|---|
| Integracja na żywo z systemem magazynowym | dane trzeba eksportować i importować ręcznie ([D1](06-decyzje.md#d1-dane-tylko-z-plików-bez-integracji-na-żywo)) |
| Automatyczna optymalizacja układu | system ocenia wariant narysowany przez projektanta, nie proponuje układu sam |
| Rejestracja i odzyskiwanie hasła | konta zakłada administrator (panel `/admin/`) |
| Własne strony błędów 404 i 500 | wygasły link publiczny albo usunięty wynik → domyślna strona Django bez nawigacji |
| Anulowanie trwającego importu zadań | jest tylko „Wstrzymaj odświeżanie” |
| Render po stronie serwera | wymaga Blendera 4.x na osobnym PC z workerem (`tools/render_worker.py`) |
| Zweryfikowany film end-to-end | Studio jest zbudowane i ma testy, a montaż z napisami sprawdzony na ffmpeg; pierwszy prawdziwy film wymaga workera z Blenderem i ffmpeg ≥ 6.1 ([D6](06-decyzje.md#d6-prezentacja-3d-w-przeglądarce-przed-filmem)) |
| Model czasu cyklu z ML | w planie; dziś prognoza wolumenów i segmentacja SKU |

## Znane problemy

### Uprawnienia i nawigacja
- Menu i część przycisków są widoczne dla roli Podgląd, choć dają jej 403: „Zadania EWM” w menu (`core/context_processors.py:22-32`), „Wklej adresy”, „Elementy hali”, „Edytuj współrzędne” w widoku hali (`twin/templates/twin/warehouse_model/view.html:146,149,176`), „Nowy typ / Edytuj / Usuń” w typach regałów (`twin/templates/twin/warehouse_map/rack_type_list.html:20,58,90`). **Decyzja: ukryć** — do zrobienia.
- Każdy Projektant może edytować i usuwać własne modele sprzętu innych Projektantów — brak sprawdzenia autora (`equipment/views.py:75-77`). **Decyzja: to niezamierzone** — do poprawy.
- Symulacja na ekranach „Symulacja dnia” i „Kalibracja” liczy się także dla roli Podgląd, a „Porównanie wariantów” nie (`twin/views/warehouse_design_sim.py:96-102`, `warehouse_compare.py:237-238`) — intencja nieustalona.

### Dane i spójność
- Usunięcie sprzętu kasuje grupy floty scenariuszy (`scenario/models.py:317`), a komunikat mówi, że scenariusze „wracają do ustawień ogólnych” (`equipment/views.py:187`) — intencja nieustalona.
- Usunięcie modelu hali kaskadowo usuwa wyniki symulacji, prezentacje 3D, prezentacje Studio i zlecenia renderu; ekran potwierdzenia wspomina tylko regały (`twin/templates/twin/warehouse_model/confirm_delete.html:22`) i nie wyświetla nazwy modelu (`twin/views/warehouse_model.py:357`).
- Zachowywanych jest 20 ostatnich wyników na scenariusz (`scenario/services.py:21`) — starsze znikają także z prezentacji 3D, bez informacji.
- Dane demo nadpisują „aktualny stan” (najnowszy import stanów wygrywa, `masterdata/services.py:124-126`).
- Ograniczenia min ≤ śr ≤ max, okien godzin i procentów są tylko w aplikacji, nie w bazie ([04](04-model-danych.md)).

### Długie operacje
- Symulacja (do 30 przebiegów × 2 dni + przebiegi podpowiedzi), import danych, ML i szkic z Claude są liczone w żądaniu; serwer ma limit 120 s (`docker-entrypoint.sh` w katalogu głównym). Szkic z Claude: 90 s × 2 próby (`studio/script_ai.py:14,52`).
- Import zadań w tle działa w wątku procesu — restart serwera zostawia import „wiszący”; po 6 h tylko etykieta, bez ponowienia (`twin/views/warehouse_tasks.py:28,125-129`).
- Zlecenie renderu odrzucone przez serwer (np. za duży plik) wraca do kolejki co 120 min bez limitu prób (`render/api.py:54-58`).

### Formularze i informacja zwrotna
- Brak potwierdzenia przy usuwaniu: scenariusza, prezentacji 3D, prezentacji Studio, zlecenia renderu, sprzętu, slajdu.
- Po błędzie walidacji wpisane dane przepadają: formularze scenariusza (`scenario/views.py:306-364`), typ regału (`twin/views/warehouse_racktype.py:28-108`), edycja stref (`twin/views/warehouse_variant_edit.py:69`).
- Komunikat sukcesu mimo pominięcia danych: współrzędne regałów (`twin/views/warehouse_model.py:212,235`), elementy hali (`twin/shared.py:150-154`), import sprzętu z samymi odrzuceniami (`equipment/views.py:124`).
- Po wygaśnięciu sesji zapis w edytorze prezentacji pokazuje „Brak połączenia z serwerem” zamiast prośby o zalogowanie.

### Dokumentacja projektowa
- `docs/PLAN.md` i `docs/ZALOZENIA.md` to zapis prac z okresu budowy (fazy F0–F6, decyzje z burzy mózgów). Niektóre szczegóły się zdezaktualizowały: `PLAN.md` opisuje `/api/render/next` (w kodzie `/api/render/claim/`) i scenę w wersji 1 (w kodzie wersja 2).

## Co dalej

Kolejność według stosunku efektu do nakładu:

1. Ukryć przed rolą Podgląd moduły i przyciski, do których nie ma dostępu.
2. Sprawdzanie autora przy edycji i usuwaniu własnego sprzętu.
3. Potwierdzenie przy usuwaniu z informacją, co zostanie usunięte razem z obiektem.
4. Własne strony 404/500 — szczególnie dla wygasłego linku publicznego.
5. Symulacja i szkic AI w tle (kolejka), żeby nie zależeć od limitu czasu żądania.
6. Z planu autora (F6): plansza kosztów w prezentacji, ruch ludzi i ładowanie aut w 3D, działka-wielokąt i trasy po drogach, porównania wariantów, katalog rynku.
