# AGENTS.md – Misja AED (HackNation 2026)

Zasady dla ludzi i wszystkich agentów AI (Claude, Codex, Cursor, Copilot, Gemini itd.).
Ten plik jest źródłem prawdy. Pliki konkretnych narzędzi (`CLAUDE.md`, `.cursor/rules`,
`.github/copilot-instructions.md`) tylko do niego odsyłają i nie dodają sprzecznych reguł.

## Kontekst

Hackathon: ogólnopolski, otwarty zbiór danych o defibrylatorach AED dla dane.gov.pl
+ wzorcowy zakres danych (xlsx) + nazwa, logo i księga znaku akcji.
Źródło prawdy: `docs/zadanie-misja-aed.md`, `docs/regulamin-misja-aed.md`.

Kryteria oceny (priorytetyzuj według nich):
zgodność z dane.gov.pl 30%, logo i hasło 25%, kreatywność 15%,
zgodność z tematem 15%, wzorcowy zakres danych 10%, prezentacja 5%.

## Podział na obszary

Właściciel jest jedyną osobą, która zmienia dany katalog.
Agent działa w imieniu właściciela i pracuje tylko w jego obszarze.

| Katalog | Obszar | Właściciel |
|---|---|---|
| `schema/` | wzorcowy zakres danych: `aed.schema.json` (Frictionless Table Schema) + wzorcowy xlsx | Krystian Poprawa |
| `ingest/` | pobieranie, normalizacja, scalanie, walidacja i eksport danych (pipeline Python) | Mikołaj Rochowiak |
| `app/` | prototyp (mapa / formularz zgłoszeń) | Krystian Poprawa |
| `branding/` | logo (.svg/.png/.jpg/.pdf), księga znaku | Krystian Poprawa |
| `portal/` | kod źródłowy portalu dane.gov.pl (backend `mcod`, GPL v3): pierwszy commit = oryginał, potem nasze zmiany (wykaz zbiorczy AED, panel administracyjny) | Mikołaj Rochowiak (docker compose / środowisko lokalne: Tymoteusz Szymański) |
| `presentation/` | slajdy, zrzuty ekranu | TODO |
| `docs/` | opisy; pliki zadania i regulaminu tylko do odczytu | wspólny |

Zmiana w cudzym katalogu → najpierw napisz do właściciela albo załóż issue.

## Zasady pracy z gitem

- Nigdy nie wysyłaj zmian prosto na `main`. Każda zmiana: gałąź → PR → merge.
- Nazwa gałęzi: `<imię>/<obszar>-<krótki-opis>`, np. `tymek/schema-pola-adresowe`.
  Dotyczy też agentów, niezależnie od domyślnej konwencji narzędzia (`claude/...`, `codex/...`).
- Małe, częste PR-y (najlepiej < 1–2 h pracy). Przed rozpoczęciem: `git pull origin main`.
- Przed PR: `git fetch && git rebase origin/main`; konflikty rozwiązuj u siebie.
- PR scala człowiek po szybkim przejrzeniu przez inną osobę (lub sam autor, jeśli zmiana
  dotyczy tylko jego obszaru i nikt nie odpowiada w ciągu 15 min).
- Jedna osoba = jeden agent naraz na danej gałęzi. Dwa agenty równolegle →
  dwie osobne gałęzie (lub `git worktree`).
- Commity z udziałem AI mają w treści linię: `AI-Assisted: <narzędzie> <model>`.
- Zakaz `push --force` na `main` i przepisywania wspólnej historii.
- Nie wysyłaj commitów na cudzą gałąź (`<imię>/...`). Poprawki zgłaszaj przez własną
  gałąź i PR do tej gałęzi albo w komentarzu do PR.
- Po scaleniu PR usuń gałąź na GitHubie (przycisk „Delete branch”), żeby nikt nie scalił
  do niej zmian, które nie trafią już na `main`.

## Pliki wspólne – miejsca kolizji

- `README.md`, `AGENTS.md`, `CLAUDE.md`, pliki zależności (np. `package.json`,
  `requirements.txt`): zmieniaj w osobnym, małym PR i uprzedź zespół na czacie.
- Kontrakt danych (`schema/`) jest punktem styku `ingest/` i `app/`. Zmiana nazwy lub typu
  pola wymaga zgody właścicieli obu obszarów.

## Dane i technologia

- Dane tylko w formatach odczytywalnych maszynowo: CSV (UTF-8, separator `,`), JSON, GeoJSON, XLSX.
  Nigdy PDF/DOC jako nośnik danych (wyjątek: logo i księga znaku).
- Każdy rekord ma pole `zrodlo` (id z `ingest/sources.yaml`) i `data_aktualizacji`.
- Bez danych osobowych (telefony/e-maile osób prywatnych) w repo; telefon kontaktowy tylko instytucji.
- Sekrety (klucze API) tylko w `.env`, który jest w `.gitignore`.
- Stos technologiczny: Python 3.12 w `ingest/`, CLI `aed fetch|map|build|validate|export <source|all>`,
  testy `pytest` na fixture'ach bez sieci. Szczegóły: `docs/plan-techniczny.md`.
  Dane robocze (`ingest/data/raw`, `staged`) poza gitem.
- Interfejs: WCAG 2.2 AA (aktualna wersja, wymóg z treści zadania), responsywność (mobile first), język polski.

## Zasady dla agentów AI (dowolne narzędzie)

- Przed pracą przeczytaj ten plik i `docs/zadanie-misja-aed.md`.
- Na początku zadania zrób `git pull`; nie nadpisuj cudzych zmian.
- Nie commituj na `main`, nie rób `push --force`, nie scalaj PR – to robi człowiek.
- Nie zmieniaj plików wspólnych, zależności ani konfiguracji innych agentów
  (`.cursor/`, `.claude/`, `.github/copilot-*`) bez wyraźnej prośby.
- Konfiguracje lokalne/osobiste (np. `.claude/settings.local.json`) nie trafiają do repo.
- Gdy zadanie wymaga zmiany w cudzym obszarze lub w `schema/` – zatrzymaj się
  i poproś człowieka o decyzję.
- Kod po angielsku; komentarze, UI i dokumentacja po polsku.
- AI proponuje, człowiek weryfikuje i decyduje (regulamin §2 pkt 7).

## Rejestr użycia AI (regulamin §2 pkt 8)

Regulamin wymaga wskazania zakresu użycia AI, więc każdą istotną pracę z AI rejestrujemy.
Obowiązuje każdego człowieka i każdego agenta, niezależnie od narzędzia.

**W trakcie pracy – tylko lokalnie:** po istotnej pracy dopisz wiersz do
`docs/ai-usage/<imię>.md` (utwórz plik, jeśli go nie ma). Katalog `docs/ai-usage/` jest
w `.gitignore`, więc plik nie trafia do commitów ani PR-ów i nie powoduje konfliktów. Format:

| Data | Gałąź / PR | Narzędzie / model | Co zrobiło AI | Co zweryfikował / zmienił człowiek |
|---|---|---|---|---|

- Kolumnę „Co zweryfikował / zmienił człowiek” wypełniaj na bieżąco.
- Agent dopisuje wpis sam, zaraz po pracy, której dotyczy.
- Plik istnieje tylko na Twoim komputerze – rób jego kopię (np. w chmurze), żeby go nie stracić.
- Nie dopisuj wierszy do `docs/ai-usage.md` w zwykłych PR-ach.

**Na koniec – dopiero na polecenie zespołu:** gdy padnie hasło „zbieramy rejestr AI”:
1. Każdy zakłada gałąź `<imię>/ai-usage`, przenosi swoje wiersze na koniec tabeli
   w `docs/ai-usage.md` (dodając kolumnę „Osoba”) i wystawia PR na `main`.
2. Jedna wyznaczona osoba scala te PR-y po kolei i rozwiązuje konflikty w `docs/ai-usage.md`,
   zostawiając wiersze ze wszystkich stron (rejestr tylko dopisujemy, nigdy nie zmieniamy
   cudzych wierszy).
3. `docs/ai-usage.md` na `main` jest jedynym rejestrem i źródłem opisu użycia AI
   do oddania projektu.

## Checklista oddania

Patrz `README.md`. Odhaczaj w PR, który realizuje dany punkt.
