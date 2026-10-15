# API

**[DEV]** · System nie udostępnia publicznego API dla integracji. Są dwa rodzaje interfejsów maszynowych:
**API stanowiska renderującego** (uwierzytelnienie tokenem) i **endpointy JSON / plików** używane przez
interfejs w przeglądarce (uwierzytelnienie sesją i rolą). Kontekst: [04-integracje.md](../04-integracje.md).

## API stanowiska renderującego

Wspólne zasady:
- nagłówek `X-Worker-Token` = wartość `RENDER_WORKER_TOKEN` (≥ 32 znaki); brak lub zły token → `403`;
  pusty token na serwerze = API wyłączone;
- operacje na przejętym zleceniu wymagają nagłówka `X-Claim` z kluczem z odpowiedzi `claim`; zły klucz → `403`;
- tylko HTTPS (stanowisko odmawia `http://` poza komputerem lokalnym).

| Metoda | Ścieżka | Wejście | Odpowiedź |
|---|---|---|---|
| POST | `/api/render/claim/` | `worker=<nazwa>` (formularz) | `200` JSON zlecenia z kluczem przejęcia · `204` brak zleceń |
| GET | `/api/render/<id>/scene.json` | `X-Claim` | `200` JSON sceny 3D |
| POST | `/api/render/<id>/result/` | `X-Claim`, plik PNG/MP4 (≤ `RENDER_MAX_MB`), `log` | `200` · `400` brak pliku / zła sygnatura · `413` za duży |
| POST | `/api/render/<id>/fail/` | `X-Claim`, `error` | `200` |
| POST | `/api/studio/montage/claim/` | `worker=<nazwa>` | `200` JSON montażu · `204` brak |
| GET | `/api/studio/montage/<id>/clip/<n>/` | `X-Claim` | `200` plik MP4 klipu |
| POST | `/api/studio/montage/<id>/result/` | `X-Claim`, plik MP4 | `200` / `400` / `413` |
| POST | `/api/studio/montage/<id>/fail/` | `X-Claim`, `error` | `200` |

Zlecenie „w toku” dłużej niż `RENDER_STALE_MIN` (120 min) wraca do kolejki przy kolejnym `claim`.

## Endpointy JSON i plików interfejsu

Wymagają zalogowania i roli; rola Podgląd dostaje scenę bez danych źródłowych. Operacje zmieniające stan:
POST z tokenem CSRF.

| Metoda | Ścieżka | Rola | Zawartość |
|---|---|---|---|
| GET | `/magazyn/model/<id>/uklad.json` | każda | układ hali dla edytora |
| POST | `/magazyn/model/<id>/uklad/sprawdz/` | Projektant | walidacja planu (problemy, KPI) |
| POST | `/magazyn/model/<id>/uklad/zapisz/` | Projektant | zapis planu · `422` błędy · `409` zmiana równoległa |
| POST / GET | `/magazyn/model/<id>/uklad/podklad/`, `podklad.img` | Projektant | wgranie i odczyt podkładu |
| GET | `/magazyn/model/<id>/blender.json`, `przeplywy.json` | każda | scena 3D i przepływy (dla Podglądu bez danych źródłowych) |
| GET | `/magazyn/warianty/<id>.json` | każda | wariant projektu |
| GET | `/magazyn/zadania-ewm/<id>/status/` | Projektant | postęp importu zadań |
| GET | `/scenariusze/symulacja/<id>/zdarzenia.json`, `wyniki.xlsx` | każda | zdarzenia animacji, eksport wyniku |
| GET / POST | `/prezentacje/<id>/dane.json`, `zapisz/` | każda / Projektant | dane pokazu, zapis slajdów (≤ 512 KB) |
| GET | `/p/<klucz>/dane.json`, `zdarzenia.json` | bez logowania, aktywny link | dane pokazu publicznego |
| GET | `/render/status.json`, `/render/<id>/plik/` | każda | status kolejki, wynik renderu |
| GET | `/studio/<id>/status.json`, `deck.pdf`, `napisy.srt`, `youtube.txt` | każda | status, deck, napisy, opis |
| GET | `/dane/wzor/<rodzaj>.csv`, `/sprzet/import/wzor.xlsx`, `/ml/<id>/segmenty.csv` | każda / Projektant / Projektant | wzory i eksporty |
| GET | `/health/` | bez logowania | `{"status","db","version","time"}`; `503` bez bazy |

Zmiana endpointu lub kontraktu JSON = aktualizacja tego pliku w tym samym PR.
