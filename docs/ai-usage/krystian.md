# Rejestr użycia AI – Krystian

| Data | Narzędzie / model | Co zrobiło AI | Co zweryfikował / zmienił człowiek |
|---|---|---|---|
| 2026-11-21 | Claude (claude.ai) / claude-opus-5-5 | Burza mózgów: licencje (ODbL vs CC0), publikacja przez Harvester dane.gov.pl, narracja na pitch, ryzyka, zakres na 24 h. | Krystian: wnioski potraktował jako materiał do dyskusji w zespole; nic nie przyjęto bez akceptacji zespołu. |
| 2026-11-21 | Claude Code / claude-opus-5-5 | Streszczenie treści zadania, regulaminu i kryteriów oceny jury; prowadzenie notatek z postępów na gałęzi `krystian/postepy`. | Krystian: zlecił strukturę notatek, zdecydował o usunięciu zbędnej gałęzi `core`. |
| 2026-11-21 | Claude Code / claude-opus-5-5 | Przegląd planu technicznego Mikołaja: streszczenie i 8 uwag (licencja, Harvester, wymagane pola, reguła dat przeglądu, kody szafek, geokodowanie, brakujące obszary). | Krystian: uwagi do omówienia w zespole; plan techniczny uznał za nadrzędny dokument projektu. |
| 2026-11-21 | Claude Code / claude-opus-5-5 | Porównanie `AGENTS.md` z planem technicznym i przygotowanie poprawek (WCAG 2.2 AA, GeoJSON, pole `zrodlo`, stos technologiczny, opisy obszarów `schema/` i `ingest/`). | Krystian: zdecydował o treści każdej poprawki; scalił PR #5. Tymek scalił zmiany do `main` (PR #6). |
| 2026-11-21 | Claude Code / claude-opus-5-5 | Założenie gałęzi `krystian/schema-v0-1` pod wzorcowy schemat danych v0.1. | Krystian: wybrał schemat v0.1 jako pierwsze zadanie. |
| 2026-11-21 | Claude Code / claude-opus-5-5 | Schemat v0.1: `schema/aed.schema.json` (39 pól wg planu technicznego), 3 fikcyjne przykładowe rekordy, generator wzorcowego XLSX (`build_xlsx.py`), testy `pytest` i `schema/README.md` z regułami biznesowymi. | Krystian: zdecydował o dwóch zmianach względem planu (`godziny_dostepnosci` = `nieznane` dopuszczalne, reguła dat przeglądu 12 miesięcy). Do przejrzenia przez zespół w PR. |
