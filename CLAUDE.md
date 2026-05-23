# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GuardHome is a self-hosted home LAN parental control platform. It wraps AdGuard Home as a DNS filtering backbone and adds per-child profiles, schedule enforcement, content classification, and a parent dashboard. No cloud account is required.

## Commands

### Full stack (recommended)
```bash
# First run
cp .env.example .env
bash setup.sh

# Start/stop
docker compose up -d
docker compose down

# Rebuild after code changes
docker compose build api        # or: dashboard
docker compose up -d api

# View logs
docker compose logs -f api
docker compose logs -f adguard
```

### API (FastAPI) — local dev without Docker
```bash
cd api
pip install -r requirements.txt
# Requires AdGuard running; set env vars or use .env
ADGUARD_URL=http://localhost:80 DB_PATH=./dev.db uvicorn main:app --reload
```

### Dashboard (React) — local dev without Docker
```bash
cd dashboard
npm install
npm run dev        # dev server at http://localhost:5173 — proxies /api to :8000
npm run build      # production build to dist/
```

### Interactive API docs
`http://localhost:8000/docs` — Swagger UI, available when API container is running.

## Architecture

### Three-container stack
```
AdGuard Home (:53 DNS, :80 UI) ← GuardHome API (:8000) ← Dashboard (:3001)
```
- **AdGuard Home** is the actual DNS server; GuardHome never touches its SQLite DB directly — all communication goes through `core/adguard_bridge.py` via AdGuard's REST API.
- **API container** mounts `./core` as a volume so core Python modules are live-reloaded without a rebuild during development.
- **Dashboard** is a static Vite build served by nginx; all API calls are relative paths proxied to `:8000`.

### Data flow: category toggle → blocking
1. Parent toggles a category in the dashboard (`PUT /api/children/{id}/categories`)
2. API writes to `category_rules` table in SQLite
3. `filter_manager.sync_child_rules()` is called, which enables/disables AdGuard filter list URLs via `adguard_bridge.set_filter_enabled()`
4. Per-device AdGuard client entries are updated with `blocked_services` via `adguard_bridge.update_client()`

### Data flow: DNS log → alerts
The `scheduler.py` APScheduler job `_sync_dns_log` runs every 60 seconds:
1. Pulls recent queries from AdGuard `/control/querylog`
2. Maps `client_ip` → `child_id` via the `devices` table
3. Writes to `dns_log` table
4. If a blocked domain matches VPN patterns, inserts an `alerts` row

### Three-tier content classifier (`core/classifier/`)
Domains are classified in order — first match wins, result cached in `domain_classifications`:
1. **Tier 1** (`domain_lookup.py`) — downloads category-tagged host lists to `/data/lists/`, does suffix matching in memory
2. **Tier 2** (`url_reputation.py`) — queries Cloudflare Radar or CleanBrowsing API; requires `CLOUDFLARE_TOKEN` or `CLEANBROWSING_KEY` env var
3. **Tier 3** (`ai_classifier.py`) — fetches page HTML, strips tags, sends to Claude API (`claude-haiku-4-5-20251001`) or falls back to keyword matching; requires `ANTHROPIC_API_KEY`

### Database (SQLite via aiosqlite)
Schema is at `api/db/schema.sql` — applied idempotently at startup via `init_db()`. Key relationships:
- `children` → `devices` (one-to-many via `child_id`)
- `children` → `category_rules` (per-child toggle overrides)
- `children` → `schedules` (time-based blocking windows)
- `children` → `allow_exceptions` (educational domains always allowed, bypasses schedules)

### Auth
Single bcrypt password stored in `settings` table under key `password_hash`. JWT issued on login, stored in `localStorage` as `gh_token`. All API routes except `/api/setup/*`, `/api/auth/login`, and `/health` require the Bearer token.

### iOS profile generation (`agents/ios/profile_generator/generator.py`)
Generates `.mobileconfig` XML plists using Python's `plistlib`. Downloads are served from `GET /api/agents/{child_id}/ios-profile`. The profile payload type is `com.apple.applicationaccess` (Restrictions). No Apple developer account or MDM server needed for installation.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ADGUARD_URL` | `http://adguard:80` | AdGuard container address |
| `ADGUARD_USER` | `admin` | AdGuard basic auth |
| `ADGUARD_PASS` | `guardhome` | AdGuard basic auth |
| `SECRET_KEY` | *(insecure default)* | JWT signing key — change in production |
| `DB_PATH` | `/data/guardhome.db` | SQLite file location |
| `ANTHROPIC_API_KEY` | *(unset)* | Enables Tier 3 AI classifier |
| `CLOUDFLARE_TOKEN` | *(unset)* | Enables Tier 2 Cloudflare Radar lookup |
| `CLEANBROWSING_KEY` | *(unset)* | Enables Tier 2 CleanBrowsing lookup |
| `LISTS_DIR` | `/data/lists` | Cache dir for downloaded domain lists |

## Key Design Constraints

- **AdGuard filter lists are currently global** — category toggles affect all clients, not just the toggled child. Per-client filtering via AdGuard client profiles is the Phase 2 target.
- **`core/` is mounted into the API container** at `/app/core` — import paths inside `api/` use `from core.xxx import yyy` (not relative imports).
- **`schedules.days` is stored as a JSON array string** in SQLite (e.g. `'["Mon","Tue"]'`). Always `json.loads()` before use and `json.dumps()` before write.
- **`scheduler.py` runs inside the FastAPI process** via APScheduler AsyncIOScheduler — it shares the event loop with the API. Do not add blocking I/O to scheduler jobs.
- **DNS log deduplication** relies on `INSERT OR IGNORE` — the `dns_log` table has no UNIQUE constraint yet, so duplicate entries can appear if the sync window overlaps. This is a known gap.
