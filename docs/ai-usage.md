# Rejestr użycia AI – Misja AED

Wymóg regulaminu §2 pkt 8. Zasady prowadzenia: [AGENTS.md](../AGENTS.md#rejestr-użycia-ai-regulamin-2-pkt-8).
Wiersze dopisujemy tylko na końcu tabeli, przy scalaniu PR na `main`.

| Data | Osoba | Gałąź / PR | Narzędzie / model | Co zrobiło AI | Co zweryfikował / zmienił człowiek |
|---|---|---|---|---|---|
| 2026-11-21 | Tymek | `tymek/agents-md` (#2, #6) | Claude Code / claude-opus-5-5 | Zaproponowało treść `AGENTS.md` i `CLAUDE.md`: podział na obszary, zasady pracy z gitem i PR, zasady dla agentów AI, rejestr użycia AI. | Tymek przejrzał propozycję i zlecił zmiany: zasady mają obejmować wszystkie agenty, nie tylko Claude; dodał zasady o cudzych gałęziach i usuwaniu gałęzi po scaleniu. Poprawki merytoryczne wnieśli Krystian (#5) i plan techniczny Mikołaja. |
| 2026-11-21 | Tymek | `tymek/agents-md` | Claude Code / claude-opus-5-5 | Zredagowało zasadę rejestrowania użycia AI (pliki osobiste na gałęziach, scalanie do `docs/ai-usage.md`) i utworzyło ten plik. | Tymek określił zasadę: rejestr na gałęziach, łączenie w jeden plik przy scalaniu. |
| 2026-11-21 | Mikołaj | `mikolaj/docs-plan-techniczny-v2` (wcześniej #3, #4) | Claude Code / claude-opus-5-5 | Na podstawie `docs/` przygotowało plan techniczny (`docs/plan-techniczny.md`): architekturę pipeline'u, źródła danych, zasady schematu AED, strukturę `ingest/`, deduplikację, walidację, podział pracy i ryzyka. Dopasowało plan do `AGENTS.md`, treści zadania (WCAG 2.2 AA) i schematu v0.1 Krystiana (#9). | Mikołaj zapoznał się z planem i przyjął go jako podstawę pracy; zlecił dopasowanie do zasad zespołu i ponowne wystawienie PR do przeglądu przez Tymka. Źródła, licencje i wymagania dane.gov.pl pozostają oznaczone jako do potwierdzenia. |
