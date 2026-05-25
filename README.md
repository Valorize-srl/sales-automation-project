# Miriade — Sales Automation Platform

B2B outreach platform: company sourcing, decision-maker enrichment via multiple providers, campaign orchestration on Smartlead, real-time reply ingestion via webhook, and AI-assisted reply drafting.

## Architecture

- **Backend**: Python 3.12 · FastAPI · SQLAlchemy (async) · Celery worker
- **Frontend**: Next.js 14 · TypeScript · Tailwind · shadcn/ui · Recharts
- **Database**: PostgreSQL 16 (Railway-hosted)
- **Queue / Cache**: Redis 7
- **AI**: Claude API (`claude-sonnet-4-5`) for reply drafting, CSV column mapping, LinkedIn DM discovery via web search
- **Outreach provider**: Smartlead v1 — sole provider for campaigns, sending, and reply categorization
- **Enrichment providers**: Findymail (email + LinkedIn), Apollo.io (people/company search + enrichment), native website scraper

---

## Features

### Leads — the working surface

The `/leads` page is where sourcing, enrichment, and list management live.

- **Clay-style table**: every column inline-editable (name, revenue, employee count, industry, website, LinkedIn URL, province/location, company emails as primary + chips, decision makers, DM LinkedIn, work emails, custom fields, lists).
- **Lists**: left rail with create/rename/delete + color cycling + per-list counters (companies and DM-with-email). Collapsible to a 40px rail.
- **Filter panel**: search, ICP-style filters, industry, custom fields, has-DM, has-LinkedIn-DM, list membership.
- **CSV import**: bulk import with Claude-powered column auto-mapping.
- **Bulk actions** (when selecting one or more companies): add to list, push DMs to Smartlead campaign, delete, enrich.

#### Enrichment drawer (Sheet on the right)

The "Arricchisci" button opens a side drawer split into two sections:

| Section | Tool | What it does |
|---|---|---|
| 🔍 Sourcing | **Cerca nuove persone (Apollo)** | People-first search by role / location / seniority / company keywords / size bands. Imports into a chosen lead list. |
| ✨ Enrichment | **Scrapa siti web** | Native scraper extracts emails + LinkedIn URL from each company's website. |
| | **Trova LinkedIn azienda (Findymail)** | Backfills `linkedin_url`, industry, location, email domain. Free. |
| | **Trova DM via LinkedIn (Claude + Google)** | Single broad `site:linkedin.com/in/` search by company + roles. No LinkedIn login needed. |
| | **Cerca DM per ruolo (Findymail)** | `/search/domain` returns name + email for matching roles. |
| | **Cerca DM completi (Findymail)** | Chains `/search/employees` → `/search/linkedin` to return name + LinkedIn URL + email in one shot. |
| | **Trova email per DM esistenti (Findymail)** | For each DM without email, look up via LinkedIn URL or name + domain. |

Sourcing actions work without a selection; enrichment actions are disabled when nothing is selected.

### Campaigns — Smartlead

- Create campaigns locally and push to Smartlead (creates DRAFTED on the remote, attaches schedule + settings + sequences + email accounts).
- Activate / pause / delete propagated to Smartlead.
- Push lead lists (people + companies with email) to a Smartlead campaign in batches of 400.
- Auto-sync every 90 seconds: pulls the campaign list from Smartlead and refreshes per-campaign metrics (sent / opens / replies). No manual "Sync" button.
- Live indicator pulse in the page header.

### Replies — real-time via webhook

- Smartlead webhook (`POST /api/webhooks/smartlead?token=…`) ingests reply / bounce / unsubscribe / campaign status events. Authenticated via shared secret (Smartlead does not sign payloads).
- `lead_category` from Smartlead's native categories (Interested, Meeting Request, Not Interested, Out Of Office, Information Request, Wrong Person, Do Not Contact, Not Now, Objection, Unsubscribe, custom) is stored verbatim on `EmailResponse` and shown as the primary badge in `/responses`.
- Mapped onto our 4-bucket `Sentiment` enum (`INTERESTED / POSITIVE / NEUTRAL / NEGATIVE`) using Smartlead's own `sentiment_type` field when present.
- AI reply drafting via Claude. Manual approval workflow: draft → review/edit → send via Smartlead `reply-to-thread`.
- Polling fallback every 30 s as defensive refresh — no manual refresh button.

### Dashboard

- KPI cards: people, companies, active campaigns, emails sent, opens, replies, converted.
- Time-range chart (sent / opens / replies) over 7d, 30d, custom, or all.
- **Reply intent breakdown** — bar chart of Smartlead lead categories within the window.
- **Top campaigns by reply rate** — top 5 with ≥ 5 emails sent.

### MCP Server

Streamable-HTTP MCP endpoint at `POST /mcp/` exposes the data model as tools so Claude (Desktop / Code / Agent SDK) and other MCP-compatible clients can operate Miriade with natural language. Per-client API keys (`mir_…` prefix, sha256-hashed at rest, optional scopes / `client_tag` / expiry). See [MCP usage](#mcp-server) below.

### Usage & Cost Tracking

Every Apollo search, Findymail lookup, Claude call, and (when applicable) Apify run is logged with credit / token counts and USD cost, grouped per `client_tag` on `/usage`.

---

## API Integrations

| Service | Purpose |
|---|---|
| **Smartlead v1** | Campaigns CRUD, sending, sequences, email-accounts management, warmup, reply-to-thread, webhook delivery of reply / bounce / unsubscribe / campaign-status events |
| **Findymail** | DM email lookup by LinkedIn URL or name+domain, company info backfill (LinkedIn URL + industry + domain), `/search/domain` for role-based DM search, `/search/employees` → `/search/linkedin` chain |
| **Apollo.io** | People search by role / location / seniority / company filters, credit consumption tracking |
| **Anthropic Claude** | CSV column auto-mapping, AI reply drafting, LinkedIn DM discovery via `web_search_20260209` server tool |
| **Native scraper** | URL list → emails + LinkedIn URL extraction (in-process httpx, no third-party) |

---

## Costs

| Service | Unit | Cost | Notes |
|---|---|---|---|
| **Claude API** (Sonnet 4.5) | Input tokens | $3.00 / 1M | CSV mapping, AI replies, LinkedIn DM discovery |
| **Claude API** (Sonnet 4.5) | Output tokens | $15.00 / 1M | |
| **Apollo.io** | Per result | $0.10 / credit | 1 credit = 1 person returned (with email) |
| **Findymail** | Per match | ~$0.04 | 1 credit per email found |
| **Smartlead** | Subscription | $174 / mo (Smart plan) | Managed in Smartlead dashboard, not tracked in-app |

### Typical operation costs

| Operation | Approximate cost |
|---|---|
| Apollo search "CEO Milano" returning 25 people | ~$2.50 |
| Findymail "Cerca DM completi" on 1 company, max 3 | ~6 credits (~$0.25) |
| AI reply generation | $0.01 – $0.05 |
| CSV column auto-mapping | ~$0.01 |
| Native website scrape per URL | free |

---

## Local Development

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (optional, for IDE support)
- Node.js 20+ (optional, for IDE support)

### Quick start

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

### Environment variables

**Backend** (`backend/.env`):

```
DATABASE_URL=postgresql+asyncpg://sales_user:sales_password@localhost:5432/sales_automation
REDIS_URL=redis://localhost:6379/0

# AI
ANTHROPIC_API_KEY=sk-ant-...

# Outreach
SMARTLEAD_API_KEY=...
SMARTLEAD_WEBHOOK_SECRET=...     # shared secret embedded in the webhook URL on Smartlead (?token=…)

# Enrichment
APOLLO_API_KEY=...
FINDYMAIL_API_KEY=...

# Webhook base for outbound URLs
WEBHOOK_BASE_URL=https://your-host.up.railway.app

# MCP — generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
MCP_MASTER_KEY=replace-me
MCP_ENABLED=true

APP_ENV=development
```

**Frontend** (`frontend/.env`):

```
NEXT_PUBLIC_API_URL=http://localhost:8000
AUTH_PASSWORD=...
AUTH_SECRET=...
```

### Services

| Service    | URL                        |
|------------|----------------------------|
| Frontend   | http://localhost:3000      |
| Backend    | http://localhost:8000      |
| API Docs   | http://localhost:8000/docs |
| PostgreSQL | localhost:5432             |
| Redis      | localhost:6379             |

### Database migrations

```bash
# Generate a new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec backend alembic upgrade head
```

Migrations run automatically on container startup.

---

## Project Structure

```
backend/
  app/
    api/                # FastAPI route handlers
      campaigns.py      # Smartlead-backed campaign CRUD
      companies.py      # Companies + enrichment endpoints
      people.py         # Person endpoints
      lead_lists.py     # Lead list management
      responses.py      # Email responses (replies arrive via webhook)
      webhooks.py       # POST /webhooks/smartlead — real-time reply ingestion
      tools.py          # Apollo Search People + import-leads + CSV export
      scraper.py        # Native website scraper
      analytics.py      # Dashboard stats + intent breakdown + top campaigns
      usage.py          # Cost tracking per client_tag
      settings.py       # Key-value settings store
    models/             # SQLAlchemy models (Company, Person, LeadList, Campaign, EmailResponse, …)
    schemas/            # Pydantic request/response schemas
    services/
      smartlead.py            # Smartlead client (campaigns, leads, replies, analytics)
      smartlead_categories.py # In-memory cache: Smartlead lead_category → Sentiment
      findymail.py            # Findymail client (search-linkedin / -domain / -employees / -company)
      apollo.py               # Apollo client (search_people / search_organizations / enrich)
      linkedin_via_claude.py  # Claude + Google web_search DM finder
      website_scraper.py      # Native scraper (no Apify)
      sentiment.py            # Claude-based reply drafting
    mcp/                # MCP server (streamable-http)
    db/                 # Engine + session config
    config.py
  alembic/versions/     # Migrations (036 → drop prospecting_tools)
  Dockerfile

frontend/
  app/
    dashboard/          # KPIs + intent breakdown + top campaigns
    campaigns/          # Real-time campaign list (90s auto-sync)
    leads/              # Clay table + lists rail + enrichment drawer
    responses/          # Real-time replies (webhook + 30s fallback)
    replies-analytics/  # Sentiment trends
    usage/              # Cost tracking
    settings/           # Exchange rate (everything else moved)
    login/
  components/
    leads/              # Clay table, lead-lists-sidebar (collapsible),
                        # enrichment-drawer, all enrichment + sourcing dialogs
    campaigns/          # Campaign list + create/edit + push-leads
    responses/          # Responses table + detail dialog
    layout/             # Sidebar, header
    ui/                 # shadcn primitives
  lib/api.ts            # Typed REST client
  types/index.ts        # Shared TypeScript types
  Dockerfile
```

---

## Deployment

Deployed on **Railway** with three services:

- **Backend** — FastAPI; runs `alembic upgrade head` on boot.
- **Frontend** — Next.js (standalone build).
- **Worker** — Celery for background tasks.

**Postgres + Redis** are Railway plugins. The Smartlead webhook must be registered manually pointing to `https://<host>/api/webhooks/smartlead?token=<SMARTLEAD_WEBHOOK_SECRET>` (Smartlead has no per-event HMAC signing as of 2026; we authenticate via the token in the URL).

---

## MCP Server

Miriade exposes a [Model Context Protocol](https://modelcontextprotocol.io) server at `POST /mcp/` (streamable-HTTP transport).

### Tool catalog

Grouped by domain (see `backend/app/mcp/tools/`):

| Domain | Representative tools |
|---|---|
| **people** | `list_people`, `get_person`, `create_person`, `update_person`, `delete_person`, `bulk_tag_people`, `import_people`, `export_people_csv` |
| **companies** | `list_companies`, `get_company`, `create_company`, `update_company`, `delete_company`, `bulk_delete_companies`, `push_company_dms_to_campaign` |
| **lead_lists** | `list_lead_lists`, `create_lead_list`, `update_lead_list`, `delete_lead_list`, `add_companies_to_list`, `remove_companies_from_list` |
| **campaigns** | `list_campaigns`, `get_campaign`, `create_campaign`, `activate_campaign`, `pause_campaign`, `push_people_to_campaign`, `campaign_analytics` |
| **responses** | `list_responses`, `get_response`, `generate_ai_reply`, `approve_and_send_reply`, `ignore_response` |
| **apollo** | `apollo_search_people`, `apollo_credits_status` |
| **analytics** | `dashboard_stats`, `cost_breakdown`, `list_client_tags` |
| **activity** | `list_activity` |

### 1. Configure the master key

Set `MCP_MASTER_KEY` in `backend/.env` (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`). This key only mints / lists / revokes API keys — it is **not** the key MCP clients use.

### 2. Create an API key

```bash
curl -X POST https://<host>/api/admin/api-keys \
  -H "x-master-key: $MCP_MASTER_KEY" \
  -H "content-type: application/json" \
  -d '{"name": "my-laptop", "client_tag": "internal"}'
```

The plaintext `raw_key` (prefixed `mir_…`) is returned **once** — copy it immediately.

### 3. Connect a client

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "miriade": {
      "type": "http",
      "url": "https://<host>/mcp/",
      "headers": { "Authorization": "Bearer mir_..." }
    }
  }
}
```

**Claude Code / Claude Agent SDK / Cursor**: equivalent config pointing to `https://<host>/mcp/` with `Authorization: Bearer mir_...`.

### 4. Revoke / rotate

```bash
curl https://<host>/api/admin/api-keys \
  -H "x-master-key: $MCP_MASTER_KEY"                       # list

curl -X DELETE https://<host>/api/admin/api-keys/<id> \
  -H "x-master-key: $MCP_MASTER_KEY"                       # revoke
```

Keys are hashed at rest (sha256). Revoked keys are soft-deleted with `revoked_at` and `is_active=false` — they stop working on the next request.
