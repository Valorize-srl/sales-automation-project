# Sales Automation Project

B2B outreach automation platform with AI-powered ICP parsing, lead management, campaign orchestration, and sentiment analysis.

## Architecture

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy (async) + Celery
- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui
- **Database**: PostgreSQL 16
- **Queue/Cache**: Redis 7
- **AI**: Claude API (Anthropic)
- **Email**: Instantly API

## Local Development

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (optional, for IDE support)
- Node.js 20+ (optional, for IDE support)

### Quick Start

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

Services:
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

## Deployment

Deployed on Railway. Each service (backend, frontend, worker) is configured via `railway.toml` in its respective directory.
