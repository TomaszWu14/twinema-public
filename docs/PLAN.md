# TWINEMA — zakres i plan

> **TWINEMA** = *digital twin* + *cinema*. Aplikacja do projektowania magazynów w 3D
> (hala, regały, pola odkładcze, strefy, flota), symulacji przepływów i produkcji
> prezentacji: render w Blenderze + lektor ElevenLabs → film i deck.
>
> Odbiorcy: zarząd (przegląd możliwości, technologii i kosztów) oraz osoby oceniające
> projekt z zewnątrz (rekruterzy). Scenariusz referencyjny: **budowa nowego centrum
> dystrybucyjnego** — dane demonstracyjne, bez nazw firm i danych klientów.

Status: F0 ✅, F1 ✅ (przeszczep rdzenia), F2 ✅ (Dane), F3 ✅ (Render), F4 ✅ (ML v1), F5 ✅ (Studio: film + deck, PR #8–#11) — 2026-10-05. Następna: F6 (Szlif).

---

## 1. Decyzje

| # | Decyzja | Wybór |
|---|---|---|
| D1 | Repo | prywatne repozytorium robocze autora (adres poza dokumentacją) |
| D2 | Historia | czysta; pochodzenie kodu w `PROVENANCE.md` |
| D3 | Odbiorcy | zarząd + zewnętrzni oceniający (nacisk) → wygląd i README „portfolio-grade” |
| D4 | Logowanie | własne konta; bez SSO |
| D5 | Dane | tylko importy plików (xlsx/csv); bez pobierania z innych aplikacji |
| D6 | Render | **worker Blendera na własnym PC** (GPU, Blender już jest), pobiera zlecenia z aplikacji po HTTPS; serwer trzyma tylko aplikację i bazę. Później ten sam worker na wynajętej maszynie GPU, jeśli trzeba |
| D7 | Lektor | własny głos z ElevenLabs Voice Design (plan Creator lub wyższy) |
| D8 | Zakres | tylko projektowanie i animacja przepływów magazynu; bez paletyzacji kartonów (`palletizer`), HU, transportu |
| D9 | Relacja z projektem źródłowym | kopia kodu (fork-and-diverge), projekt źródłowy nietknięty; nic nie płynie z powrotem |

---

## 2. Zakres

### 2.1 MVP
1. **Dane** — materiały (wymiary/waga jednostek, przeliczniki), nośniki, typy regałów, lokalizacje, historia ruchów (zadania magazynowe), migawki stanów. Importy xlsx/csv z walidacją i raportem odrzuceń.
2. **Model hali** — generator „od zera” z parametrów (pojemność, wysokość hali, proporcje), widok 3D (three.js), warianty, strefy, KPI wariantu, porównanie wariantów.
3. **Symulacja** — dzień projektowy (P95), dyspozytor floty, kalibracja na realnych cyklach.
4. **ML** — prognoza wolumenów, segmentacja SKU pod rozmieszczenie, model czasu cyklu (§4).
5. **Render** — format sceny `twinema.scene` v1, worker Blendera, presety kamery, stills + animacje przepływów.
6. **Studio prezentacji** — scenariusz → lektor → ujęcia pod długość kwestii → montaż → MP4 + PDF (§5).

### 2.2 Po MVP (wsad do burzy mózgów)
- **Katalog rynku**: typy maszyn i systemów (regał paletowy, VNA, shuttle, AS/RS, AMR/AGV, przenośniki, sortery, wózki), producenci, parametry, widełki cen → CAPEX/OPEX wariantu.
- Edytor „jak w grze”: przeciąganie regałów, pól odkładczych, wydzielanie stref w 3D.
- Sezonowość roczna w prognozie (≥ 2 lata historii), wykrywanie anomalii.
- Wersja EN interfejsu i lektora; muzyka; split-screen „obecny vs wariant”.

### 2.3 Poza zakresem
Paletyzacja kartonów, kontrola HU, skanery, transport, integracje online z WMS/ERP.

---

## 3. Architektura

```
web/
  twinema/     projekt Django: config (pydantic, fail-fast), settings, urls
  core/        role (zamrożony kontrakt), middleware, health, logowanie, hub
  masterdata/  F2: Material, StockItem, ImportLog (raport importu); master lokalizacji zapisuje do twin;
               importy xlsx/csv z aliasami kolumn, wzory plików, dane demo (`manage.py demo_dane --model N`)
  twin/        F1: model hali, regały, elementy, szablony gniazd, warianty, import zadań, dzień projektowy,
               symulacja, kalibracja, prognoza, porównanie, eksport sceny — logika w czystym Pythonie
  ml/          F4: forecast (SES/Holt/Holt tłumiony/Holt-Winters vs trend log, wybór po MAPE),
               segmentation (k-means na rotacji + objętości, vs ABC×XYZ), ModelRun; ML3 (czas cyklu) → F6
  render/      F3: RenderJob (kolejka), API workera (token + jednorazowy claim, walidacja PNG/MP4),
               ekran ujęć z podglądem; presety kamery w tools/blender/twinema_render.py
  studio/      F5: Presentation, Shot, Script, VoiceTrack; pipeline TTS → render → ffmpeg
tools/blender/ design_kit, anim, twinema_render.py (presety: przelot, orbita, przejazd, plan, ogólny)
tools/render_worker.py  pętla na PC z Blenderem: przejmij zlecenie → scena → render → wyślij (stdlib)
```

Stack: Python 3.13, Django 5.2 LTS, PostgreSQL 17, Docker + Coolify, gunicorn + WhiteNoise.
Kolejka renderów = tabela RenderJob + worker odpytujący po HTTPS (bez Celery). Celery + Redis dojdą
w F5, jeśli TTS/montaż po stronie serwera tego wymagają.

**Worker renderujący (D6):** skrypt na PC z Blenderem odpytuje `/api/render/next` (token),
pobiera scenę JSON, renderuje `blender -b -P`, odsyła MP4/PNG. Serwer bez GPU i bez
otwartych portów do Redisa — wystarczy HTTPS. PC wyłączony = zlecenia czekają w kolejce.

---

## 4. Uczenie maszynowe

| # | Model | Dane | Punkt wyjścia | Cel | Miernik |
|---|---|---|---|---|---|
| ML1 | Prognoza wolumenów | tygodnie × strumień | log-trend, P50/P90 | Holt-Winters/ETS, wybór wariantu przez MAPE, przedział 80 % | MAPE backtest vs log-trend |
| ML2 | Segmentacja SKU | rotacja, pobrania, wymiary, współwystępowanie | ABC | ABC×XYZ + k-means → strefy/poziomy w generatorze | droga w symulacji vs ABC |
| ML3 | Czas cyklu | realne cykle per zasób | mediana real÷sym | gradient boosting od dystansu, wysokości, typu wózka, pory | MAE na odłożonych dniach |

Zasada: baseline + backtest zawsze widoczne; model zastępuje baseline tylko, gdy wygrywa miernik.

---

## 5. Studio prezentacji

```
KPI wariantu → Scenariusz (Claude + edycja) → Lektor (ElevenLabs, timestamps)
            → Ujęcia (Blender, długość = kwestia) → Montaż (ffmpeg: głos, napisy, plansze) → MP4 + PDF
```

- Presety kamery: przelot nad halą, orbita strefy, przejazd korytarzem, zbliżenie regału, porównanie.
- Napisy SRT z znaczników czasu lektora.
- Cache po hashu wejścia (tekst+głos / scena+ujęcie): poprawka zdania nie renderuje całego filmu.
- Statusy: szkic → tekst zatwierdzony → audio → render → montaż → gotowe (nie renderujemy przed akceptacją tekstu).
- Deck PDF 16:9 z serwera (fpdf2 + DejaVu): tytuł, liczby z KPI, ujęcie na slajd (kadr PNG z kolejki F3 + kwestia).
- Na zewnątrz (ElevenLabs/Claude) idzie wyłącznie tekst narracji.

---

## 6. Fazy

| Faza | Cel | Kryterium „done” |
|---|---|---|
| **F0 Fundament** | repo, CI/CD, logowanie, hub, health | CI zielone, deploy na Coolify, `/health/` zwraca SHA |
| **F1 Przeszczep rdzenia** | generator, model 3D, symulacja, eksport sceny | skopiowane testy czystego Pythona zielone; generator + widok 3D działają |
| **F2 Dane** | modele + importy plików | import demonstracyjnych zadań i materiałów → symulacja dnia liczy się |
| **F3 Render** | worker Blendera + presety kamery | klik „Renderuj” → MP4/PNG w aplikacji |
| **F4 ML v1** | ML1 + ML2 | backtest z MAPE; segmentacja skraca drogę vs ABC |
| **F5 Studio MVP** ✅ | pierwszy film | 2–3 min film PL z lektorem i napisami + deck PDF, z aplikacji (kod gotowy; pierwszy prawdziwy film po podpięciu kluczy i ffmpeg) |
| **F6 Szlif** | ML3, porównania, katalog rynku | wg burzy mózgów |

Ścieżka krytyczna: F0 → F1 → F2 → F3 → F5; F4 równolegle z F3.

### Po F5: budowanie przyszłego layoutu (priorytet od 2026-10-05)

Film i montaż odstawione na bok; główny cel = pokazać w przeglądarce, jak może wyglądać przyszły layout.
Kolejność: **E1** silnik edytora (walidacja + API) → **E2** edytor planu 2D (przeciąganie regałów, doków,
pól odkładczych, stref; KPI i problemy na żywo) → **E3** podgląd 3D obok edytora → **tryb prezentacji 3D**
(przelot kamery, animacja przepływów, plansze KPI, link dla roli Podgląd) → **katalog sprzętu** (CAPEX).

Decyzje: edytor pracuje na `WarehouseModel` (na nim działają 3D, animacja i symulacja); przyszły layout =
kopia modelu. Oglądanie i animacja — w przeglądarce (three.js); Blender tylko opcjonalnie do renderów.
E1: `twin/layout.py` (kolizje na obróconych prostokątach, regał w doku/bramie/polu odkładczym/stanowisku/
korytarzu = błąd, poza halą, duplikat adresu; alejki z `design_catalog.check_aisles`; KPI z `compute_kpi`),
API `magazyn/model/<pk>/uklad.json` · `uklad/sprawdz/` · `uklad/zapisz/` (blokada optymistyczna po `version`).
E2 ✅: ekran `magazyn/model/<pk>/edytor/` — plan SVG, bloki i pojedyncze elementy (ZALOZENIA E9), KPI i problemy
na żywo, cofnij/ponów, zapis.
E2b ✅ (ZALOZENIA E3–E6): wysokość w świetle (zapas 0,5 m pod konstrukcją), siatka słupów z wyjątkami, droga
pożarowa i strefa ładowania (blokują regały), drogi ruchu (ostrzeżenie), strefy specjalne temp/ADR/gabaryty/
wartość (na razie oznaczenie — reguły rozmieszczenia w S3), podkład PNG/JPG kalibrowany dwoma punktami (PDF:
zapisz stronę jako PNG — bez nowej zależności), sprzęt regału (reach/VNA/półki) wyznacza wymaganą alejkę.
E3 ✅: podgląd 3D obok planu (układ 2D | 2D + 3D | 3D), ta sama scena co widok modelu — wspólny moduł
`static/twin/js/scene-builder.js` (+ czyste `scene-data.js`); przebudowa 300 ms po zmianie (1000 regałów ≈ 0,1 s),
zaznaczenie podświetlone w 3D, ujęcia z góry / izometria / do zaznaczenia. „Utwórz przyszły layout (kopia)” →
edytor (kopia niesie słupy, wysokość, podkład, sprzęt) → „Zobacz animację przepływów”. Pełny ekran (F) w edytorze
i w widoku 3D / planie 2D modelu — wspólny `fullscreen.js` dla trybu prezentacji i scenariuszy.

Scenariusze (założenia z burzy mózgów: `docs/ZALOZENIA.md`) przeplatają się z edytorem:
**E1** → **S2a** scenariusz + plan przyjęć → **E2** → **E3** → S1 master data materiału, S2b wydania/paczki/
zwroty/cross-dock, S2c obsada i zmiany → **S3** symulacja scenariusza (wiele przebiegów, P95, wąskie gardła)
→ **S4** animacja dnia → tryb prezentacji 3D → katalog sprzętu.
S2a: aplikacja `scenario` — `Scenario` (mnożnik wzrostu, ziarno, zmiana, normy wydajności), dzień typowy
i szczytowy, `InboundStream` (kontener 40' / auto 33-pal. / solówka-bus, min/śr/max, okno awizacji, % mono,
% kontroli); `scenario/inbound.py` liczy deterministycznie palety/dzień, doki w szczycie, osobogodziny, stanowiska.
S2b ✅ (S2b + S2c razem): `OutboundStream` (auta OUT jak przyjęcia: 33-pal., solówka/bus, kurier, cross-dock;
okno załadunku z cut-off), profil dnia (zamówienia, linie, paczki, zwroty, % palet pełnych), cross-dock także
jako strumień przyjęć (bez składowania), `Shift` (1–3 zmiany per proces, przerwy, osoby); `scenario/outbound.py`
i `scenario/staffing.py` — palety OUT, doki OUT, osobogodziny 7 procesów, obsada potrzebna vs zakładana per zmiana
(podział wg zakładanej zdolności zmian), ryzyko cut-off paczek. Godziny w formularzach jako GG:MM.
S1 ✅: `masterdata` — hierarchia sztuka → karton → paleta, katalog nośników i klas wysokości/wagi (dobierane
z wyliczonej palety, gdy puste), ręczna ABC (pierwszeństwo przed ABC z historii), flagi stref specjalnych
(temperatura, ADR, gabaryt, wartość). Dla S3: nośność poziomów regału vs klasa wagi, ADR/temperatura vs strefy
specjalne z E2b, kartonów/paletę z master daty zamiast średniej normy.
S3a ✅: `scenario/sim/` — zdarzeniowa symulacja dnia na layoucie (doki z rolami z etykiet, ludzie na zmianach,
flota z ładowaniem, pola odkładcze, cut-off kurierów), wiele przebiegów → średnia i P95, wąskie gardła
z podpowiedzią „+N” z ponownej symulacji, zdarzenia przebiegu reprezentatywnego dla animacji (S4).
S3b ✅: jawna rola doku (pole elementu hali, migracja z etykiet), nośność miejsca regału, pojemność vs stan × wzrost,
strefy specjalne i nośność jako ostrzeżenia (zapotrzebowanie vs pojemność — stany nie mają przypisania do regałów
projektu), kartonów/paletę z master daty w symulacji, tabela porównania layout × scenariusz, eksport xlsx.
S4 ✅: animacja dnia w przeglądarce (`scenariusze/symulacja/<pk>/animacja/`) — scena hali (createViewer) + każdy
kontener, auto, kurier i paleta z przebiegu reprezentatywnego (InstancedMesh), stos paczek przy pakowaniu; zegar,
suwak, ×10–×300, skok do szczytu, liczniki, wąskie gardła na czerwono w oknie czasu + dymek z podpowiedzią (klik =
skok czasu i kamery), pełny ekran (F), klawiatura, tabela godzinowa jako alternatywa tekstowa.
G1 ✅: grafika 3D w przeglądarce (wspólny `scene-builder.js`) — palety z ładunkiem w regałach, ściany hali
z przekrojem, bramy i doki, posadzka z fugami i plac, pasy BHP, kadr dopasowany do hali, cienie i mgła zależne od
kamery, pojazdy z kabiną i kołami; przełącznik jakości wysoka/szybka. Ocena ~6/10 (cel 6–7/10 jak programy
symulacyjne); fotorealizm tylko offline w Blenderze (Cycles). Dalej: D1 działka → K1 katalog → tryb prezentacji.
D1 ✅: działka pod halą (`twin/site.py`) — wymiary, ograniczenia planu miejscowego (wysokość, % zabudowy, linie
zabudowy, % zieleni), dojazd i wjazdy, plac/parking/zieleń/drogi; walidacja i KPI w edytorze (tryb „Działka”), teren
w 3D, auta w animacji dnia wjeżdżają od bramy działki. Dalej: K1 katalog sprzętu → tryb prezentacji.
K1 ✅: katalog sprzętu (`equipment`, `/sprzet/`) — klasy systemowe (anonimowe) + własne modele; Ast, maks. podnoszenie
i udźwig na wysokości walidują layout, flota scenariusza z katalogu liczy czas ruchu palety i ładowanie. Koszty
(CAPEX/OPEX) — pola są, UI później. Dalej: tryb prezentacji 3D.
C1 ✅: koszty CAPEX/OPEX wariantu jako widełki (stawki `/sprzet/stawki/` + koszty sprzętu w katalogu) — karta w wyniku
symulacji, wiersze w porównaniu layout × scenariusz, arkusz w xlsx; OPEX na paletę/paczkę/zamówienie.
P1 ✅: tryb prezentacji 3D (`prezentacje/`) — zamiennik filmu dla zarządu i rekruterów: slajdy (ujęcia kamery,
plansze KPI, fragmenty animacji dnia, wąskie gardła, tekst) na jednej scenie z przelotami, szablon startowy z modelu
i wyniku symulacji, edytor slajdów dla Projektanta, odtwarzacz z pełnym ekranem dla Podglądu. Dalej (do wyboru):
plansza kosztów w prezentacji, grafika 6–7/10 (SSAO, ruch ludzi, ładowanie aut), działka-wielokąt i trasy po drogach.

---

## 7. Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| Dryf z kodem źródłowym | po F1 nowe prace projektowe tylko tu |
| Koszt ElevenLabs/Claude przy iteracjach | cache po hashu, akceptacja tekstu przed TTS, limit znaków na prezentację |
| Mało historii do ML | baseline + backtest zawsze pokazany |
| Nieobejrzane wizualnie 3D | każda faza z renderem kończy się przeglądem obrazu |
| Dane wrażliwe w demo | tylko dane syntetyczne/zanonimizowane; brak nazw firm w repo |
