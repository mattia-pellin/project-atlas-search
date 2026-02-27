# Project Rules: Development & Release Workflow

Queste regole sono state definite per garantire la stabilità dei crawler e la tracciabilità delle versioni.

## 1. Modifiche al Backend
Ogni volta che viene modificato il codice del backend:
- **Test**: Devono essere eseguiti i test dei crawler (`pytest backend/test_crawlers.py`).
- **Container**: Il container locale deve essere aggiornato per permettere i test e riflettere le modifiche.

## 2. Versionamento (SemVer)
- Ad ogni modifica richiesta, deve essere effettuato un **bump dell'ultima semver** (patch version).
- La versione corrente è tracciata in `frontend/src/App.jsx`.

## 3. Gestione Git e Release
- **Commit & Push**: Ogni modifica non taggata può essere committata e pushata automaticamente.
- **Tagging & Release**: NON pushare versioni taggate online senza esplicito consenso dell'utente.
