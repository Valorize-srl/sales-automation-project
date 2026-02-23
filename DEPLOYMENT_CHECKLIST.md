# 🚀 Deployment Checklist - Usage Tracking & Client Tagging

## ✅ Verifiche Struttura Progetto

### Backend
- [x] **Models creati:**
  - ✅ `app/models/apollo_search_history.py`
  - ✅ `app/models/settings.py`
  - ✅ Campo `client_tag` in `company.py`, `person.py`, `lead.py`

- [x] **Migrations create:**
  - ✅ `010_create_usage_tracking.py`
  - ✅ `011_add_lead_client_tag.py`
  - ✅ `012_add_people_client_tag.py`
  - ✅ `013_add_companies_client_tag.py`

- [x] **API Endpoints creati:**
  - ✅ `app/api/usage.py` (stats, history)
  - ✅ `app/api/settings.py` (get, update)
  - ✅ Router registrati in `__init__.py`

- [x] **Schemas creati:**
  - ✅ `app/schemas/usage.py`
  - ✅ `app/schemas/settings.py`

### Frontend
- [x] **Pagine create:**
  - ✅ `app/usage/page.tsx`
  - ✅ `app/settings/page.tsx`

- [x] **Componenti creati:**
  - ✅ `components/usage/usage-stats-cards.tsx`
  - ✅ `components/usage/search-history-table.tsx`
  - ✅ `components/settings/exchange-rate-settings.tsx`

- [x] **Modifiche UI:**
  - ✅ Sidebar: aggiunte voci Usage e Settings
  - ✅ Apollo search form: campo client tag
  - ✅ People/Companies tables: colonna Client/Project
  - ✅ Leads page: filtro client tag

- [x] **Dependencies:**
  - ✅ `date-fns` aggiunto al package.json

## 🔧 Verifiche da Fare su Railway

### 1. Variabili d'Ambiente Backend

Verifica che su Railway (servizio backend) siano configurate:

```bash
APOLLO_API_KEY=<your-apollo-key>  # ⚠️ CRITICO - Probabilmente mancante!
DATABASE_URL=<postgres-url>
ANTHROPIC_API_KEY=<claude-key>
CORS_ORIGINS=<frontend-url>
```

**Il problema attuale (API error: 404) è probabilmente dovuto a `APOLLO_API_KEY` mancante o errata!**

### 2. Verifica Deployment Backend

Controlla i log su Railway:

```bash
# Cerca conferma migrations eseguite:
✓ Running migrations...
✓ alembic upgrade head
✓ INFO [alembic.runtime.migration] Running upgrade 012 -> 013

# Cerca errori startup:
✗ ModuleNotFoundError
✗ ImportError
✗ Database connection failed
```

### 3. Verifica Database

Le nuove tabelle devono esistere:
- `apollo_search_history`
- `settings` (con seed: usd_eur_exchange_rate = 0.92)

Nuove colonne:
- `leads.client_tag`
- `people.client_tag`
- `companies.client_tag`

## 🧪 Test Funzionali da Eseguire

### Test 1: Health Check
```bash
curl https://<your-backend>.railway.app/health
# Expected: {"status":"ok","version":"..."}
```

### Test 2: Settings Endpoint
```bash
curl https://<your-backend>.railway.app/api/settings/usd_eur_exchange_rate
# Expected: {"key":"usd_eur_exchange_rate","value":"0.92",...}
```

### Test 3: Usage Stats (vuoto inizialmente)
```bash
curl https://<your-backend>.railway.app/api/usage/stats
# Expected: {"stats":{...},"date_range":{...}}
```

### Test 4: Apollo Search con Client Tag

1. **Via UI:**
   - Vai su AI Chat → Advanced Search
   - Compila:
     - Location: "Italy"
     - Company Keywords: "digital agency"
     - Client Tag: "Test Cliente"
   - Clicca "Search Apollo"
   - **Atteso:** Risultati mostrati (non errore 404)
   - **Se errore 404:** Verifica APOLLO_API_KEY su Railway!

2. **Verifica tracking:**
   - Vai su Usage page
   - **Atteso:** La ricerca appare nello storico con client_tag "Test Cliente"

### Test 5: Import con Client Tag

1. Dopo una ricerca Apollo con client tag:
   - Clicca "Import to People" o "Import to Companies"
   - **Atteso:** "Imported X records"

2. Vai su Leads:
   - Filtra per client tag
   - **Atteso:** Records importati visibili con client tag nella colonna

### Test 6: Filtro Client Tag

1. Su Leads page (tab People):
   - Inserisci un client tag nel campo filtro
   - **Atteso:** Lista filtrata correttamente

2. Ripeti per tab Companies

### Test 7: Exchange Rate Settings

1. Vai su Settings
2. Modifica il tasso di cambio (es: 0.95)
3. Clicca "Save Exchange Rate"
   - **Atteso:** "Exchange rate updated successfully"
4. Ricarica la pagina
   - **Atteso:** Valore salvato persiste

## ❌ Risoluzione Problema Corrente

**Errore attuale:** "Apollo search error: API error: 404"

**Causa probabile:** `APOLLO_API_KEY` non configurata su Railway

**Soluzione:**

1. Vai su Railway → Progetto → Backend service
2. Variables → Add Variable
3. Nome: `APOLLO_API_KEY`
4. Valore: La tua Apollo API key
5. Deploy → Redeploy

Oppure, se la chiave c'è ma è errata:
- Verifica che la chiave Apollo sia valida
- Prova a rigenerarla su apollo.io
- Verifica i limiti di credito Apollo

## 📊 Risultati Attesi Post-Fix

Dopo aver configurato correttamente APOLLO_API_KEY:

1. ✅ Ricerche Apollo funzionano senza errori
2. ✅ Ogni ricerca salvata in `apollo_search_history`
3. ✅ Costi calcolati correttamente (Apollo + Claude)
4. ✅ Usage page mostra statistiche accurate
5. ✅ Client tag funziona end-to-end:
   - Input in search → Saved in history → Copied to imports → Filterable in leads
6. ✅ Settings page permette modifica tasso cambio

## 🎯 Success Criteria

- [ ] Apollo searches completano senza errori
- [ ] Usage page mostra dati reali
- [ ] Client tag visibile in tutte le tabelle
- [ ] Filtri client tag funzionanti
- [ ] Settings salvabili e persistenti
- [ ] Migrations eseguite su database production
- [ ] Nuove voci sidebar (Usage, Settings) funzionanti

---

**Data verifica:** $(date)
**Deploy commit:** ba9d4cf + edfe636
**Status:** ⚠️ In attesa configurazione APOLLO_API_KEY
