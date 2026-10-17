# Czyszczenie historii repozytorium (R-01)

**[SEC] + [DEV]** · decyzja PO: przepisać historię · operację wykonuje **PO** na swoim komputerze —
jest nieodwracalna i wymaga uprawnień właściciela repozytorium. Ten dokument celowo **nie przytacza**
wrażliwych wartości (zob. [Do anonimizacji](../05-decyzje-i-ograniczenia.md#do-anonimizacji), A-8 i A-9).

## Co trzeba usunąć

| Nr | Co | Gdzie |
|---|---|---|
| A-8 | dane rzeczywistego obiektu (liczba lokalizacji, typy składowania, kody procesów, daty decyzji) | wcześniejsze wersje plików reguł zadań magazynowych i adresowania — przed commitem z 2026-10-12 „generic example codes…”; przejrzeć także commit z 2026-10-09 „Przygotowanie repo do upublicznienia” i wcześniejsze |
| A-9 | prywatny adres e-mail autora | metadane autora ponad stu commitów |
| A-1…A-7, A-10…A-12 | nazwisko, domena, nazwy projektu źródłowego w bieżących plikach | bieżąca wersja plików — **poprawione 2026-10-17** (poza A-1 — zostaje, wymóg licencji — i A-6 — do potwierdzenia przez PO) |

## Dlaczego nie wystarczy „force push”

GitHub przechowuje commity z zamkniętych i scalonych PR-ów (`refs/pull/*`). Po przepisaniu historii
i force-pushu stare commity **nadal są dostępne** przez strony dawnych PR-ów i bezpośrednie linki, a forki
mają własne kopie. Dlatego zalecana jest opcja A.

## Opcja A (zalecana): nowe repozytorium z jedną migawką

1. **Scal PR #68** (i ewentualne inne) do `main`, sprawdź, że CI jest zielone.
2. **Kopia zapasowa** starego repozytorium w bezpiecznym miejscu poza GitHubem:
   `git clone --mirror <adres-starego-repo> twinema-backup.git` — przechowuj ją prywatnie i zaszyfrowaną,
   bo zawiera usuwane dane.
3. **Ustaw adres e-mail zastępczy** (GitHub → Settings → Emails → „Keep my email addresses private”, adres
   `…@users.noreply.github.com`) i włącz „Block command line pushes that expose my email”.
4. **Utwórz migawkę** w świeżym katalogu:
   ```sh
   git clone <adres-starego-repo> twinema-clean && cd twinema-clean
   git checkout --orphan clean main
   git -c user.name="<nazwa publiczna>" -c user.email="<adres noreply>" \
       commit -m "TWINEMA — publiczna wersja projektu (historia sprzed tej wersji niepublikowana)"
   ```
5. **Sprawdź migawkę** przed publikacją: `gitleaks detect --source . --no-git` oraz przegląd sekcji
   „Do anonimizacji” — w bieżących plikach nie może być wartości z A-1…A-12.
6. **Opublikuj w nowym repozytorium** (nowa nazwa albo ta sama po zmianie nazwy starego):
   `git remote set-url origin <adres-nowego-repo> && git push -u origin clean:main`.
7. **Stare repozytorium**: ustaw jako prywatne albo usuń (po weryfikacji nowego). Usunięcie nie kasuje
   forków — sprawdź listę forków i w razie potrzeby poproś ich właścicieli albo GitHub Support o usunięcie.
8. **Przełącz integracje** na nowe repozytorium: Coolify (źródło aplikacji, webhook), sekrety GitHub Actions
   (`COOLIFY_WEBHOOK_URL`, `COOLIFY_API_TOKEN`, `SMOKE_URL`), ochrona gałęzi `main` z wymaganym
   zatwierdzeniem PR (R-09), Private Vulnerability Reporting (Z-22), Dependabot.
9. **Usuń nieużywany sekret** `AUTOMERGE_PAT` i unieważnij token u źródła (auto-merge wyłączony, R-09).

## Opcja B: przepisanie historii w tym samym repozytorium

Stosować tylko, jeśli adres repozytorium musi zostać zachowany.

1. Kroki 1–3 z opcji A.
2. W świeżym klonie lustrzanym, narzędziem `git filter-repo`:
   - plik zamian tekstu (`--replace-text`) przygotowany **lokalnie, poza repozytorium** — każda wrażliwa
     wartość z A-8 → `***`;
   - plik `.mailmap` (`--mailmap`) mapujący prywatny adres na adres noreply.
3. `git push --force --mirror` do repozytorium.
4. **GitHub Support**: prośba o usunięcie zbuforowanych widoków i referencji `refs/pull/*` z dawnymi commitami
   (formularz „Remove sensitive data”). Bez tego dane pozostają dostępne przez stare PR-y.
5. Każda osoba z klonem musi sklonować repozytorium od nowa (stary klon przywróciłby historię przy pushu).

## Po czyszczeniu

- Zamknij R-01 w [rejestrze ryzyk](../bezpieczenstwo/RYZYKA.md) z datą i wybraną opcją.
- Wpis w [CHANGELOG](../../CHANGELOG.md) (sekcja „Security”, bez szczegółów usuniętych danych).
- [SEC] odnotowuje w [audycie](../AUDYT.md), że historia nie zawiera danych z A-8/A-9.
