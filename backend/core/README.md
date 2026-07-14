# Core

Shared infrastructure layer consumed by every other package. Zero dependencies on other project packages.

## Files

| File | Responsibility |
|------|---------------|
| `config.py` | Pydantic-settings: loads all env vars from `.env`, provides cached `get_settings()` singleton |
| `database.py` | SQLite connection management, schema creation, upsert logic, pipeline lock, dataset CRUD |
| `queries.py` | All read-only SQL queries consumed by the API layer |

## Design Principles

- **Pure infrastructure** — no business logic, no platform-specific code
- **Settings singleton** — `get_settings()` is LRU-cached, called from every layer
- **SQLite-first** — single-file database, zero external DB dependencies
- **Auto-migration** — `_apply_migrations()` adds missing columns on startup
