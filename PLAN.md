# Miriade - B2B Sales Automation Platform

## Context
Piattaforma che automatizza la generazione di lead e l'outreach via email B2B. L'utente definisce il proprio Ideal Customer Profile (ICP) tramite chat, cerca lead con Apollo.io, crea campagne email su Instantly, analizza il sentiment delle risposte e genera reply intelligenti tramite AI con approvazione manuale.

**Uso**: Multi-client (client tagging per separare costi e lead)
**API attive**: Instantly v2, Anthropic Claude, Apollo.io, Apify
**Accesso esterno**: MCP server (streamable-HTTP) su `/mcp` per Claude Desktop/Code e altri client MCP
**Deploy**: Railway (backend, frontend, worker) + PostgreSQL + Redis

---

## Architettura

```
┌──────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 14)                     │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌─────────────┐  │
│  │ Dashboard │ │Prospecting│ │ Campaigns  │ │ AI Agents   │  │
│  │+Analytics │ │ + Apollo  │ │ +Instantly │ │+KnowledgeBase│ │
│  └──────────┘ └───────────┘ └────────────┘ └─────────────┘  │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌─────────────┐  │
│  │ Leads    │ │ Responses │ │   Usage    │ │  Settings   │  │
│  │+LeadLists│ │+AI Replies│ │  + Costs   │ │             │  │
│  └──────────┘ └───────────┘ └────────────┘ └─────────────┘  │
└─────────────────────────┬────────────────────────────────────┘
                          │ REST API
┌─────────────────────────┴────────────────────────────────────┐
│                    BACKEND (FastAPI)                           │
│  ┌──────────────────────────────────────────────────────────┐│
│  │              AI Services (Claude API)                     ││
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐ ││
│  │  │ICP Parser│ │ Sentiment │ │AI Replier│ │CSV Mapper │ ││
│  │  └──────────┘ └───────────┘ └──────────┘ └───────────┘ ││
│  └──────────────────────────────────────────────────────────┘│
│  ┌──────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Apollo.io    │ │ Instantly  │ │  Apify   │ │  Celery  │ │
│  │ Service      │ │ Service    │ │ Enrichment│ │ Workers  │ │
│  └──────────────┘ └────────────┘ └──────────┘ └──────────┘ │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────┴────────────────────────────────────┐
│                PostgreSQL + Redis (Railway)                    │
└──────────────────────────────────────────────────────────────┘

                          ┌───────────────┐
                          │  MCP Server   │ ← mounted in FastAPI at /mcp
                          │  (FastMCP)    │   streamable-HTTP + API key auth
                          └───────────────┘
                                  ▲
                    Claude Desktop/Code, Agent SDK, Cursor,
                    n8n/Make, tool custom — qualsiasi client MCP
```

---

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) |
| AI | Claude API (Anthropic) — Sonnet 4.5 |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| Background Jobs | Celery |
| Lead Search | Apollo.io API |
| Lead Enrichment | Apollo.io + Apify (fallback) |
| Email Outreach | Instantly API v2 |
| Deploy | Railway (backend, frontend, worker) |

---

## Struttura del Progetto

```
sales-automation-project/
├── frontend/
│   ├── app/                     # Next.js App Router
│   │   ├── dashboard/           # KPI + analytics + chart
│   │   ├── campaigns/           # Gestione campagne Instantly
│   │   ├── leads/               # People, Companies, Lead Lists
│   │   ├── prospecting/         # Ricerca Apollo.io
│   │   ├── ai-agents/           # AI Agents per client
│   │   │   ├── new/             # Creazione agente
│   │   │   └── [id]/dashboard/  # Dashboard agente
│   │   ├── responses/           # Risposte email + AI replies
│   │   ├── chat/                # Chat ICP conversazionale
│   │   ├── usage/               # Costi e utilizzo API
│   │   └── settings/            # Configurazione
│   ├── components/              # Componenti UI riutilizzabili
│   │   ├── campaigns/           # Tabelle, dialog campagne
│   │   ├── leads/               # CSV import, tabelle lead
│   │   ├── responses/           # Tabelle risposte, dettagli
│   │   ├── chat/                # Apollo search, message bubble
│   │   └── ui/                  # shadcn/ui components
│   ├── lib/                     # API client, utilities
│   └── types/                   # TypeScript definitions
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point + CORS + MCP mount
│   │   ├── config.py            # Settings da env vars
│   │   ├── mcp/                 # MCP server (FastMCP)
│   │   │   ├── app.py           # Starlette app con auth middleware
│   │   │   ├── server.py        # FastMCP instance + tool registration
│   │   │   ├── middleware.py    # API key auth middleware
│   │   │   ├── keys.py          # Key generation/hashing/verification
│   │   │   ├── session.py       # DB session helper per tool
│   │   │   └── tools/           # Tool per dominio (people, companies,
│   │   │                        #   lead_lists, campaigns, responses,
│   │   │                        #   ai_agents, apollo, analytics)
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── icp.py           # Ideal Customer Profile
│   │   │   ├── person.py        # Contatti (da Apollo/CSV)
│   │   │   ├── company.py       # Aziende
│   │   │   ├── lead.py          # Lead (legacy)
│   │   │   ├── lead_list.py     # Liste di lead raggruppate
│   │   │   ├── campaign.py      # Campagne email
│   │   │   ├── email_response.py # Risposte + sentiment
│   │   │   ├── analytics.py     # Metriche giornaliere
│   │   │   ├── ai_agent.py      # AI Agent + Knowledge Base
│   │   │   ├── chat_session.py  # Sessioni chat
│   │   │   └── apollo_search_history.py # Storico ricerche + costi
│   │   ├── schemas/             # Pydantic request/response
│   │   ├── api/                 # Route handlers
│   │   │   ├── chat.py          # Chat streaming + Apollo tools
│   │   │   ├── campaigns.py     # CRUD + Instantly sync
│   │   │   ├── leads.py         # CRUD + CSV import
│   │   │   ├── people.py        # People CRUD
│   │   │   ├── companies.py     # Companies CRUD
│   │   │   ├── lead_lists.py    # Lead Lists CRUD
│   │   │   ├── responses.py     # Risposte + AI reply generation
│   │   │   ├── ai_agents.py     # AI Agents + Knowledge Base
│   │   │   ├── analytics.py     # Dashboard stats + date range
│   │   │   └── usage.py         # Cost tracking per client
│   │   ├── services/            # Business logic
│   │   │   ├── instantly.py     # Instantly API v2 client
│   │   │   ├── apollo.py        # Apollo.io search + enrichment
│   │   │   ├── ai_replier.py    # Generazione reply AI
│   │   │   ├── sentiment.py     # Analisi sentiment
│   │   │   ├── icp_parser.py    # Parsing ICP da chat
│   │   │   ├── email_generator.py # Template email AI
│   │   │   ├── csv_mapper.py    # Auto-mapping CSV (Claude)
│   │   │   ├── apify_enrichment.py # Enrichment fallback
│   │   │   └── ai_agent.py      # Gestione AI Agent
│   │   └── db/
│   │       └── database.py      # Async engine + session
│   ├── alembic/                 # Database migrations
│   └── Dockerfile
│
├── docker-compose.yml           # Dev locale
└── PLAN.md                      # Questo file
```

---

## Database Schema

### Tabelle principali

**icps** — Ideal Customer Profiles
- id, name, description, industry, company_size, job_titles, geography, revenue_range, keywords, raw_input, status

**people** — Contatti importati (da Apollo, CSV, manuale)
- id, first_name, last_name, email, phone, job_title, linkedin_url, company_id, company_name, source, client_tag

**companies** — Aziende
- id, name, domain, industry, size, revenue, location, description

**lead_lists** — Liste raggruppate di lead
- id, name, description, people (M2M)

**campaigns** — Campagne email (sync con Instantly)
- id, instantly_campaign_id, name, status, subject, body, ai_agent_id, total_sent, total_opened, total_replied

**email_responses** — Risposte ricevute con sentiment
- id, campaign_id, from_email, subject, body, sentiment, sentiment_score, ai_suggested_reply, status, ai_reply_generated

**ai_agents** — Agenti AI per client
- id, name, description, icp_config, signals_config, knowledge_base_text, apollo_credits_allocated

**analytics** — Metriche giornaliere per campagna
- id, campaign_id, date, emails_sent, opens, replies, positive_replies

**apollo_search_history** — Storico ricerche con costi
- id, query_params, results_count, apollo_credits_consumed, claude_input_tokens, claude_output_tokens, cost_total_usd, client_tag

**chat_sessions** — Sessioni chat conversazionali
- id, uuid, title, total_claude_input_tokens, total_claude_output_tokens, total_apollo_credits, total_cost_usd, client_tag

**api_keys** — Chiavi API per autenticare i client MCP
- id, name, key_hash (sha256), prefix, last_four, scopes, client_tag, is_active, last_used_at, expires_at, revoked_at

---

## Flussi Operativi

### 1. Prospecting (Ricerca Lead)
1. L'utente va in Prospecting e configura i filtri: job title, industry, location, company size, revenue
2. La ricerca usa Apollo.io People Search API
3. I risultati vengono mostrati in anteprima con selezione individuale
4. L'utente sceglie quali lead importare e assegna un client tag
5. Claude inferisce l'industry quando Apollo non la fornisce
6. Le lead vengono salvate come People nel database

### 2. Lead Lists & Gestione
1. Le lead importate sono visibili in Leads → People
2. Si possono creare Lead Lists per raggruppare lead per campagna/progetto
3. Import CSV con auto-mapping colonne via Claude
4. Enrichment via Apollo (1 credit/lead) o Apify (~$0.005/lead) come fallback

### 3. Campagne Email
1. Creare campagna con nome, subject, body (template AI generato da Claude)
2. Assegnare sender accounts (da Instantly)
3. Push lead dalla tabella People alla campagna Instantly
4. Attivare la campagna
5. Sync automatico metriche giornaliere da Instantly (sent, opens, replies, bounces)

### 4. AI Agents & Knowledge Base
1. Creare un AI Agent per client con ICP e signals config
2. Scrivere le istruzioni nella Knowledge Base (tono, stile, informazioni prodotto)
3. Connettere campagne all'agente
4. L'agente usa la Knowledge Base per generare reply personalizzate

### 5. Risposte Email & AI Auto-Reply
1. Fetch risposte da Instantly per le campagne monitorate
2. Analisi sentiment automatica: positive, negative, neutral, interested
3. Generazione reply AI basata su Knowledge Base + contesto conversazione
4. **Workflow manuale**: l'utente rivede la reply generata, la approva o modifica, poi invia
5. Filtri per campagna, sentiment, stato, data

### 6. Dashboard & Analytics
1. KPI aggregati: people, companies, campagne attive, email inviate, aperture, risposte
2. Selettore time range: 7gg, 30gg, custom, tutto
3. Grafico daily: invii vs risposte nel tempo
4. Analytics per campagna da Instantly

### 7. Tracking Costi
1. Ogni chiamata API viene tracciata con token/crediti e costo USD
2. Breakdown per client tag nella pagina Usage
3. Breakdown giornaliero con grafico costi
4. Stima costi prima dell'enrichment

### 8. Accesso via MCP (Model Context Protocol)
1. L'admin crea una API key via `POST /api/admin/api-keys` (protetto da `MCP_MASTER_KEY`)
2. La chiave plaintext (`mir_…`) viene mostrata una volta sola
3. Il client MCP (Claude Desktop/Code, Agent SDK, Cursor, n8n/Make, tool custom) si collega a `POST https://<host>/mcp/` con header `Authorization: Bearer mir_…`
4. Il server autentica via sha256 della chiave e aggiorna `last_used_at`
5. Il client può invocare i tool per fare ricerche Apollo, importare/aggiornare lead, creare campagne, generare reply AI, leggere analytics, ecc.
6. Le chiavi possono essere revocate istantaneamente via `DELETE /api/admin/api-keys/{id}`

**Cataloghi di tool MCP** (`backend/app/mcp/tools/`):
- **people**: list/get/create/update/delete/bulk_delete/bulk_tag/bulk_enrich/import/export_csv/person_campaigns
- **companies**: list/get/create/update/delete/bulk_delete
- **lead_lists**: list/get/create/update/delete + add/remove people & companies + list_people_in_list / list_companies_in_list
- **campaigns**: list/get/create/update/delete/activate/pause + push_people + campaign_analytics + generate_email_template
- **responses**: list/get + generate_ai_reply + approve_and_send_reply + approve_reply_without_sending + ignore_response
- **ai_agents**: list/get/create/update/delete + update_knowledge_base
- **apollo**: apollo_search_people, apollo_search_organizations, apollo_credits_status, import_apollo_results
- **analytics**: dashboard_stats, cost_breakdown, list_client_tags

---

## Costi API

| Servizio | Unita' | Costo | Note |
|----------|--------|-------|------|
| Claude API (Sonnet 4.5) | Input tokens | $3.00 / 1M | ICP, template, reply, CSV mapping |
| Claude API (Sonnet 4.5) | Output tokens | $15.00 / 1M | |
| Apollo.io | Per credito | $0.10 | 1 credito = 1 enrichment persona |
| Apify | Per lead | ~$0.005 | Fallback quando Apollo credits esauriti |
| Instantly | Abbonamento | Variabile | Gestito su dashboard Instantly |

### Stime Tipiche

| Operazione | Costo Approssimativo |
|------------|---------------------|
| Ricerca Apollo (senza enrichment) | Gratis (search credits) |
| Enrichment 100 lead (Apollo) | ~$10.00 |
| Enrichment 100 lead (Apify) | ~$0.50 |
| Generare reply AI | ~$0.01 - $0.05 |
| Generare template email | ~$0.01 - $0.03 |
| Conversazione ICP | ~$0.02 - $0.10 |
| Auto-mapping CSV | ~$0.01 |

---

## Stato Implementazione

### Completato
- [x] Setup progetto e infrastruttura (FastAPI, Next.js, PostgreSQL, Redis, Railway)
- [x] Chat ICP conversazionale con Claude (streaming)
- [x] Import lead CSV con auto-mapping colonne AI
- [x] Integrazione Apollo.io (search, enrichment, credits tracking)
- [x] Prospecting page con import selettivo e client tagging
- [x] Industry inference via Claude quando Apollo non fornisce il dato
- [x] People & Companies tables con CRUD
- [x] Lead Lists (creazione, gestione, assegnazione a campagne)
- [x] Integrazione Instantly v2 (campagne, lead, metriche, warmup)
- [x] Push lead (da People) a campagne Instantly
- [x] Generazione template email AI (subject + body)
- [x] Gestione account email (warmup, limiti, sending gaps)
- [x] AI Agents per client con Knowledge Base editabile
- [x] Connessione campagne ad AI Agents
- [x] Fetch risposte da Instantly
- [x] Sentiment analysis (positive, negative, neutral, interested)
- [x] Generazione reply AI con Knowledge Base
- [x] Workflow approvazione manuale reply (genera → rivedi → approva & invia)
- [x] Dashboard con KPI e grafico daily
- [x] Time range selector (7gg, 30gg, custom, tutto)
- [x] Tracking costi per client (Apollo, Claude, Apify)
- [x] Deploy su Railway (backend, frontend, worker)
- [x] Database migrations automatiche (Alembic su startup)
- [x] MCP server su `/mcp` con API key auth (sha256) e tool per tutti i domini

### Da fare
- [ ] Migrazione database a Supabase (backup automatici, PITR)
- [ ] Notifiche real-time per nuove risposte
- [ ] Scheduling automatico fetch risposte (cron/worker)
- [ ] Export dati (CSV/Excel)
- [ ] A/B testing template email
- [ ] Multi-step sequence management dalla UI
