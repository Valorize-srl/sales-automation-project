# Miriade - Sales Automation Platform

B2B outreach automation platform with AI-powered prospecting, campaign orchestration, intelligent email replies, and lead management.

## Architecture

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy (async) + Celery
- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui
- **Database**: PostgreSQL 16
- **Queue/Cache**: Redis 7
- **AI**: Claude API (Anthropic)
- **Email**: Instantly API v2
- **Prospecting**: Apollo.io API

## Features

### Prospecting & Lead Search
- Search leads via Apollo.io by job title, industry, location, company size, revenue
- Selective import: preview results and choose which leads to import
- Industry inference via Claude AI when Apollo data is incomplete
- Client tagging for multi-client management
- Apollo credits tracking and per-client cost breakdown

### Lead Management
- **People & Companies**: dedicated tables for contacts and organizations
- **Lead Lists**: group leads into reusable lists, assign to campaigns
- **CSV Import**: bulk import with AI-powered column auto-mapping (Claude)
- **Enrichment**: enrich contacts and companies via Apollo.io and Apify
- **Filtering**: by ICP, client tag, lead list, status

### Campaign Orchestration
- Create and manage email campaigns synced with Instantly
- AI-generated email templates (subject + body) via Claude
- Push leads (from People table) to Instantly campaigns
- Campaign lifecycle: draft, active, paused, completed, scheduled
- Daily analytics sync from Instantly (sent, opens, replies, bounces)
- Email account management: warmup tracking, daily limits, sending gaps

### AI Agents
- Create independent AI agents per client
- Configure ICP, signals, and prospecting parameters
- **Knowledge Base**: editable text area to instruct the AI on reply tone and content; supports PDF upload
- Connect agents to campaigns for reply generation
- Per-agent dashboards with stats and connected campaigns

### Email Responses & AI Auto-Reply
- Fetch replies from Instantly campaigns
- Sentiment analysis: positive, negative, neutral, interested
- AI-generated reply drafts based on Knowledge Base instructions
- **Manual approval workflow**: generate reply, review, approve & send
- Filter responses by campaign, sentiment, status, date range
- Visual indicators for AI-generated replies in campaign table

### Dashboard & Analytics
- KPI cards: people, companies, active campaigns, emails sent, opens, replies
- Time range selector: 7 days, 30 days, custom date range, all time
- Daily chart: sent vs replies over time
- Per-campaign daily analytics from Instantly

### Chat & ICP Definition
- Conversational ICP creation via Claude
- Session-based chat with message history
- Apollo search context integration

### Usage & Cost Tracking
- API usage statistics (Apollo, Claude, Apify)
- Per-client cost summaries
- Search history with credit consumption

## Costs

The platform tracks costs per API call and aggregates them per client in the Usage page.

| Service | Unit | Cost | Notes |
|---------|------|------|-------|
| **Claude API** (Sonnet 4.5) | Input tokens | $3.00 / 1M tokens | ICP parsing, email templates, AI replies, CSV mapping, industry inference |
| **Claude API** (Sonnet 4.5) | Output tokens | $15.00 / 1M tokens | |
| **Apollo.io** | Per credit | $0.10 | 1 credit = 1 person enrichment (email reveal) |
| **Apify** | Per lead | ~$0.005 | Waterfall Contact Enrichment, used as fallback when Apollo credits are exhausted |
| **Instantly** | Subscription | Varies | Not tracked in-app; managed via Instantly dashboard |

### Cost Tracking Features
- **Per-client breakdown**: every search and AI call is tagged with a `client_tag`, costs are grouped by client in `/usage`
- **Daily breakdown**: usage stats page shows cost-per-day chart
- **Enrichment cost estimation**: before enriching leads, the platform estimates Apollo credits needed and shows the projected cost
- **Automatic logging**: every Apollo search, Claude call, and Apify enrichment is logged with token/credit counts and USD cost

### Typical Cost Estimates

| Operation | Approximate Cost |
|-----------|-----------------|
| Apollo search (no enrichment) | Free (search credits) |
| Enrich 100 leads (Apollo) | ~$10.00 |
| Enrich 100 leads (Apify fallback) | ~$0.50 |
| Generate AI reply to an email | ~$0.01 - $0.05 |
| Generate email template | ~$0.01 - $0.03 |
| ICP parsing conversation | ~$0.02 - $0.10 |
| CSV column auto-mapping | ~$0.01 |

> Costs depend on message length and complexity. Actual values may vary based on API pricing changes.

## API Integrations

| Service | Purpose |
|---------|---------|
| **Instantly v2** | Campaign sync, lead upload, metrics, warmup, email replies |
| **Apollo.io** | Lead search, contact enrichment, credit tracking |
| **Anthropic Claude** | ICP parsing, email templates, AI replies, CSV mapping, industry inference |
| **Apify** | Company enrichment and web scraping |

## Local Development

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (optional, for IDE support)
- Node.js 20+ (optional, for IDE support)

### Quick Start

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

### Environment Variables

**Backend** (`backend/.env`):
```
DATABASE_URL=postgresql+asyncpg://sales_user:sales_password@localhost:5432/sales_automation
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
INSTANTLY_API_KEY=...
APOLLO_API_KEY=...
APIFY_API_TOKEN=...
APP_ENV=development
```

**Frontend** (`frontend/.env`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
AUTH_PASSWORD=...
AUTH_SECRET=...
```

### Services

| Service    | URL                       |
|------------|---------------------------|
| Frontend   | http://localhost:3000      |
| Backend    | http://localhost:8000      |
| API Docs   | http://localhost:8000/docs |
| PostgreSQL | localhost:5432             |
| Redis      | localhost:6379             |

### Database Migrations

```bash
# Generate a new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec backend alembic upgrade head
```

Migrations run automatically on container startup via `alembic upgrade head` in the Dockerfile entrypoint.

## Project Structure

```
backend/
  app/
    api/          # FastAPI route handlers
    models/       # SQLAlchemy models
    schemas/      # Pydantic request/response schemas
    services/     # Business logic (Instantly, Apollo, AI, etc.)
    db/           # Database engine and session config
    config.py     # Settings from environment variables
  alembic/        # Database migrations
  Dockerfile

frontend/
  app/            # Next.js App Router pages
    dashboard/    # Analytics dashboard
    campaigns/    # Campaign management
    leads/        # Lead management and CSV import
    prospecting/  # Apollo search interface
    ai-agents/    # AI agent dashboards
    responses/    # Email response management
    chat/         # Conversational AI
    settings/     # Configuration
    usage/        # Cost tracking
  components/     # Reusable UI components
  lib/            # API client, utilities
  types/          # TypeScript type definitions
  Dockerfile
```

## Deployment

Deployed on **Railway** with three services:
- **Backend**: FastAPI application (auto-runs migrations on deploy)
- **Frontend**: Next.js application
- **Worker**: Celery for background tasks

Database: PostgreSQL 16 (external or Railway-hosted)
