# B2B Multi-Agent Outreach Platform

## Context
Tool personale che automatizza la generazione di lead e l'outreach via email B2B. L'utente definisce il proprio Ideal Customer Profile (ICP) tramite chat o upload documento, e il sistema si occupa automaticamente di: trovare lead in target, creare campagne email su Instantly, analizzare il sentiment delle risposte e suggerire reply intelligenti tramite AI.

**Uso**: Personale (singolo utente, niente autenticazione)
**API disponibili ora**: Instantly (già attiva), Anthropic Claude
**API future**: Apollo.io (da aggiungere per scraping automatico)
**Scraping iniziale**: Import manuale CSV + predisposizione architettura per Apollo.io

---

## Architettura Generale

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                │
│  ┌──────────┐ ┌───────────┐ ┌────────────────────┐  │
│  │ Chat ICP │ │ Dashboard │ │ Campaign Manager   │  │
│  │ + Upload │ │ + Analytics│ │ + Sentiment View  │  │
│  └──────────┘ └───────────┘ └────────────────────┘  │
└─────────────────────────┬───────────────────────────┘
                          │ REST API
┌─────────────────────────┴───────────────────────────┐
│                  BACKEND (FastAPI)                    │
│  ┌────────────────────────────────────────────────┐  │
│  │           AI ORCHESTRATOR (Claude)              │  │
│  │  ┌─────────┐ ┌───────────┐ ┌──────────────┐  │  │
│  │  │ ICP     │ │ Sentiment │ │ AI Replier   │  │  │
│  │  │ Parser  │ │ Analyzer  │ │              │  │  │
│  │  └─────────┘ └───────────┘ └──────────────┘  │  │
│  └────────────────────────────────────────────────┘  │
│  ┌──────────────┐ ┌────────────┐ ┌────────────────┐ │
│  │ Scraping     │ │ Instantly  │ │ Background     │ │
│  │ Service      │ │ Service    │ │ Workers (Celery)│ │
│  └──────────────┘ └────────────┘ └────────────────┘ │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────┐
│              PostgreSQL + Redis (Railway)             │
└─────────────────────────────────────────────────────┘
```

---

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | Python 3.12 + FastAPI |
| AI | Claude API (Anthropic) |
| Database | PostgreSQL (Railway) |
| Cache/Queue | Redis (Railway) |
| Background Jobs | Celery |
| Auth | Nessuna (uso personale) |
| Scraping | Import CSV manuale + Apollo.io API (futuro) |
| Email Outreach | Instantly API |
| Deploy | Railway (tutti i servizi) |

---

## Struttura del Progetto

```
b2b-outreach-platform/
├── frontend/                    # Next.js App
│   ├── src/
│   │   ├── app/                 # App Router (pages)
│   │   │   ├── chat/            # Chat ICP
│   │   │   ├── dashboard/       # Dashboard principale
│   │   │   ├── leads/           # Gestione lead
│   │   │   ├── campaigns/       # Gestione campagne
│   │   │   ├── settings/        # Impostazioni account
│   │   ├── components/          # Componenti UI
│   │   ├── lib/                 # Utilities, API client
│   │   ├── types/               # TypeScript types
│   ├── package.json
│   ├── next.config.js
│
├── backend/                     # FastAPI App
│   ├── app/
│   │   ├── main.py              # Entry point FastAPI
│   │   ├── config.py            # Settings & env vars
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── icp.py
│   │   │   ├── lead.py
│   │   │   ├── campaign.py
│   │   │   ├── email_response.py
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── api/                 # API routes
│   │   │   ├── chat.py
│   │   │   ├── leads.py
│   │   │   ├── campaigns.py
│   │   │   ├── analytics.py
│   │   ├── services/            # Business logic
│   │   │   ├── orchestrator.py  # AI Orchestrator principale
│   │   │   ├── icp_parser.py    # Parsing ICP da chat/doc
│   │   │   ├── scraper.py       # Multi-source lead scraping
│   │   │   ├── instantly.py     # Instantly API client
│   │   │   ├── sentiment.py     # AI Sentiment Analysis
│   │   │   ├── replier.py       # AI Reply Suggestions
│   │   ├── workers/             # Celery tasks
│   │   │   ├── scraping_tasks.py
│   │   │   ├── campaign_tasks.py
│   │   │   ├── sentiment_tasks.py
│   │   ├── db/                  # Database config
│   │       ├── database.py
│   │       ├── migrations/      # Alembic migrations
│   ├── requirements.txt
│   ├── Dockerfile
│
├── docker-compose.yml           # Dev locale
├── railway.toml                 # Config Railway
```

---

## Database Schema (PostgreSQL)

### Tabelle principali:

**icps** — Ideal Customer Profiles definiti
- id, name, description, industry, company_size, job_titles, geography, revenue_range, keywords, raw_input, status, created_at

**leads** — Lead trovate/importate
- id, icp_id, first_name, last_name, email, company, job_title, linkedin_url, phone, source (csv/apollo), verified, score, created_at

**campaigns** — Campagne Instantly
- id, icp_id, instantly_campaign_id, name, status, subject_lines, email_templates, total_sent, total_opened, total_replied, created_at

**email_responses** — Risposte ricevute
- id, campaign_id, lead_id, message_body, direction (inbound/outbound), sentiment (positive/negative/neutral/interested), sentiment_score, ai_suggested_reply, human_approved_reply, status, created_at

**analytics** — Metriche aggregate
- id, campaign_id, date, emails_sent, opens, replies, positive_replies, meetings_booked

---

## Flusso Operativo Dettagliato

### 1. Definizione ICP (Chat + Upload)
- L'utente accede alla chat e descrive il suo cliente ideale
- Oppure carica un documento (PDF, DOCX, TXT)
- Claude analizza l'input e estrae i parametri strutturati dell'ICP:
  - Settore/Industry
  - Dimensione azienda
  - Job titles target
  - Geografia
  - Range fatturato
  - Keywords specifiche
- La chat è interattiva: Claude fa domande di follow-up se mancano informazioni
- L'ICP viene salvato su DB

### 2. Import/Scraping Lead
- **Fase 1 (ora)**: Import manuale CSV con mapping colonne automatico
  - Upload file CSV dalla UI
  - Claude analizza le colonne e le mappa ai campi lead
  - Deduplicazione per email
- **Fase 2 (futuro - con Apollo API key)**:
  - L'Orchestratore traduce l'ICP in query Apollo.io
  - Apollo People Search API → filtra per title, industry, company size, location
  - Scraping automatico in background tramite Celery
- Le lead vengono deduplicate (per email) e salvate su PostgreSQL
- Ogni lead riceve uno score di qualità (completezza dati, match con ICP)

### 3. Creazione Campagna Instantly
- L'Orchestratore genera email templates personalizzati tramite Claude:
  - Subject lines (A/B testing)
  - Email body con personalizzazione per lead
  - Follow-up sequence (3-5 step)
- Crea la campagna via Instantly API
- Carica le lead dal DB alla campagna Instantly
- Lancia la campagna

### 4. AI Sentiment Analysis
- Worker Celery in polling sulle risposte via Instantly API
- Ogni risposta viene analizzata da Claude:
  - **Positive/Interested**: Lead interessata, vuole saperne di più
  - **Neutral**: Risposta generica, richiede follow-up
  - **Negative**: Non interessata, unsubscribe
  - **Meeting Request**: Vuole un meeting
- Score numerico 1-10 + categorizzazione
- Risultati salvati su DB

### 5. AI Replier
- Per ogni risposta, Claude genera una reply suggerita basata su:
  - Sentiment della risposta
  - Contesto dell'ICP originale
  - Storico conversazione
  - Obiettivo (booking meeting, qualificazione, ecc.)
- L'utente vede la reply suggerita nella dashboard
- Può approvarla, modificarla o scartarla
- Una volta approvata, viene inviata via Instantly

---

## Step di Implementazione

### Step 1: Setup Progetto e Infrastruttura ✅
- Inizializzare repo con struttura frontend/ + backend/
- Setup FastAPI con SQLAlchemy + Alembic
- Setup Next.js con Tailwind + shadcn/ui
- Configurare PostgreSQL e Redis su Railway
- Configurare variabili d'ambiente
- Docker compose per sviluppo locale

### Step 2: Chat ICP
- UI chat nel frontend (conversazione con Claude)
- Endpoint streaming per la chat
- Parsing ICP strutturato da conversazione
- Upload e parsing documenti (PDF, DOCX)
- Salvataggio ICP su DB
- Pagina di review/edit dell'ICP generato

### Step 3: Import Lead (CSV + futuro Apollo)
- UI upload CSV con drag & drop
- Parsing CSV e mapping colonne automatico (Claude)
- Logica di deduplicazione e scoring lead
- Predisposizione interfaccia scraper per Apollo.io (futuro)
- Task Celery per import/scraping asincrono
- UI gestione lead (tabella, filtri, export)

### Step 4: Integrazione Instantly
- Client API Instantly (campagne, lead, analytics)
- Generazione template email con Claude
- Creazione campagna automatica
- Caricamento lead da DB a Instantly
- UI gestione campagne

### Step 5: AI Sentiment Analysis
- Worker polling risposte da Instantly
- Prompt engineering per sentiment analysis con Claude
- Classificazione e scoring risposte
- Salvataggio risultati su DB
- UI vista sentiment (badge colori, filtri)

### Step 6: AI Replier
- Generazione reply suggerite con Claude
- UI approvazione/modifica reply
- Invio reply approvate via Instantly
- Storico conversazioni

### Step 7: Dashboard e Analytics
- Dashboard principale con KPI
- Grafici campagne (open rate, reply rate, sentiment)
- Pipeline lead (funnel visualization)
- Export dati (CSV)

### Step 8: Polish e Deploy
- Error handling robusto
- Rate limiting API esterne
- Logging e monitoring
- Deploy su Railway (frontend, backend, DB, Redis)
- Test end-to-end

---

## Verifica e Testing

1. **Test manuale flusso completo**:
   - Creare ICP via chat → Importare lead CSV → Verificare lead su DB → Creare campagna → Verificare su Instantly → Simulare risposta → Verificare sentiment → Verificare reply suggerita

2. **Test unitari**: Logica di scraping, sentiment, replier

3. **Test integrazione**: API Instantly, import CSV

4. **Test E2E frontend**: Flusso critico chat → dashboard

---

## API Esterne Necessarie

**Disponibili ora:**
- **Instantly**: API key (già attiva)

**Da procurare:**
- **Anthropic (Claude)**: API key per AI → necessaria subito
- **Apollo.io**: API key per scraping automatico → da aggiungere in futuro
