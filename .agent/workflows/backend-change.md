---
description: Automated workflow for backend changes
---

# Backend Change Workflow

Follow these steps for every modification to the backend code.

1. **Bump Version**
   Increment the patch version in `frontend/src/App.jsx`. For example, from `v1.0.5` to `v1.0.6`.

2. **Update Container**
   // turbo
   Run `docker compose build --no-cache && docker compose up -d` to refresh the local environment.

3. **Run Tests**
   // turbo
   Run `./venv/bin/pytest backend/test_crawlers.py` to verify all crawlers.

4. **Git Operations**
   // turbo
   Commit the changes and push to `origin main` (do NOT push tags).
