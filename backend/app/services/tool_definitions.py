"""Tool definitions for Claude tool_use API.

Each tool is a dict following Claude's tool schema format.
These are passed to the Claude API at call time.
"""

# --- ICP Tools ---

SAVE_ICP_TOOL = {
    "name": "save_icp",
    "description": "Save the ICP that has been collaboratively defined through conversation. "
                   "Use this when the user confirms the ICP is complete or asks to save it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Descriptive name for this ICP"},
            "description": {"type": "string"},
            "industry": {"type": "string"},
            "company_size": {"type": "string"},
            "job_titles": {"type": "string"},
            "geography": {"type": "string"},
            "revenue_range": {"type": "string"},
            "keywords": {"type": "string"},
        },
        "required": ["name", "industry", "job_titles"],
    },
}

UPDATE_ICP_DRAFT_TOOL = {
    "name": "update_icp_draft",
    "description": "Update ICP draft incrementally as user provides details. "
                   "Does NOT save to database - only builds draft in session. "
                   "Use save_icp when complete.",
    "input_schema": {
        "type": "object",
        "properties": {
            "updates": {
                "type": "object",
                "properties": {
                    "industry": {"type": "string"},
                    "company_size": {"type": "string"},
                    "job_titles": {"type": "string"},
                    "geography": {"type": "string"},
                    "revenue_range": {"type": "string"},
                    "keywords": {"type": "string"}
                }
            }
        },
        "required": ["updates"]
    }
}

# --- Search Tools ---

SEARCH_APOLLO_TOOL = {
    "name": "search_apollo",
    "description": "Search Apollo.io for people or companies. Use this when user asks to find, "
                   "search, or look for leads. After getting results, suggest next steps like enrichment.",
    "input_schema": {
        "type": "object",
        "properties": {
            "search_type": {
                "type": "string",
                "enum": ["people", "companies"],
                "description": "Type of search"
            },
            "person_titles": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Job titles to search for (for people search)"
            },
            "person_locations": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "person_seniorities": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "organization_locations": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "organization_keywords": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "organization_sizes": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "technologies": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "keywords": {
                "type": ["string", "null"]
            },
            "per_page": {
                "type": "integer",
                "default": 25
            }
        },
        "required": ["search_type"]
    }
}

SEARCH_GOOGLE_MAPS_TOOL = {
    "name": "search_google_maps",
    "description": "Cerca attivita' locali su Google Maps tramite Apify scraper. "
                   "Ritorna nome, indirizzo, telefono, sito web, rating, categoria. "
                   "Ideale per horeca, retail, studi professionali, servizi locali. "
                   "Usa questo tool come fonte primaria per trovare aziende con presenza fisica.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Cosa cercare (es. 'agenzie SEO', 'ristoranti', 'studi commercialisti')"
            },
            "location": {
                "type": "string",
                "description": "Dove cercare (es. 'Milano, Italia', 'Roma')"
            },
            "max_results": {
                "type": "integer",
                "default": 25,
                "description": "Numero massimo di risultati (default 25, max 100)"
            }
        },
        "required": ["query", "location"]
    }
}

SCRAPE_WEBSITES_TOOL = {
    "name": "scrape_websites",
    "description": "Estrae email, telefono e profili social da una lista di siti web. "
                   "Usa dopo una ricerca Google Maps per trovare contatti diretti. "
                   "Se source='last_search', prende automaticamente i siti dall'ultima ricerca.",
    "input_schema": {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista di URL da scrapare"
            },
            "source": {
                "type": "string",
                "enum": ["manual", "last_search"],
                "default": "last_search",
                "description": "Se 'last_search', prende URL dall'ultima ricerca"
            }
        }
    }
}

SEARCH_LINKEDIN_COMPANIES_TOOL = {
    "name": "search_linkedin_companies",
    "description": "Cerca profili LinkedIn aziendali. Ritorna descrizione, dipendenti, settore, "
                   "specialita', follower. Usa per arricchire dati aziendali con info LinkedIn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "URL LinkedIn aziendali da scrapare"
            },
            "company_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Nomi aziende da cercare su LinkedIn"
            }
        }
    }
}

SEARCH_LINKEDIN_PEOPLE_TOOL = {
    "name": "search_linkedin_people",
    "description": "Cerca decision maker su LinkedIn per titolo, azienda, zona. "
                   "Non richiede cookies. Usa per trovare CEO, Direttori Commerciali, "
                   "Marketing Manager e altri DM per le aziende trovate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "string",
                "description": "Titolo o ruolo (es. 'CEO', 'Direttore Commerciale')"
            },
            "company": {
                "type": "string",
                "description": "Nome azienda"
            },
            "location": {
                "type": "string",
                "description": "Zona geografica (es. 'Milano, Italia')"
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "Max risultati per ricerca"
            }
        },
        "required": ["keywords"]
    }
}

# --- Enrichment Tools (kept for non-prospecting mode) ---

ENRICH_COMPANIES_TOOL = {
    "name": "enrich_companies",
    "description": "Enrich companies from last search with contact emails from their websites. "
                   "Use when user asks to 'find emails', 'get contacts', or 'enrich companies'. "
                   "Scrapes generic emails like info@, contact@, sales@.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company_ids": {
                "type": ["array", "string"],
                "description": "Company IDs to enrich. Use 'all' for all from last search.",
                "items": {"type": "integer"}
            },
            "max_concurrent": {
                "type": "integer",
                "default": 3
            },
            "force": {
                "type": "boolean",
                "default": False
            }
        },
        "required": ["company_ids"]
    }
}

VERIFY_EMAILS_TOOL = {
    "name": "verify_emails",
    "description": "Verify email deliverability for people from last search.",
    "input_schema": {
        "type": "object",
        "properties": {
            "person_ids": {
                "type": "array",
                "items": {"type": "integer"}
            },
            "min_confidence": {
                "type": "number",
                "default": 0.7
            }
        },
        "required": ["person_ids"]
    }
}

# --- Session Tools ---

GET_SESSION_CONTEXT_TOOL = {
    "name": "get_session_context",
    "description": "Get current session state: ICP draft, last search results, stats. "
                   "Use when user asks 'what did we search for?' or 'where are we?'",
    "input_schema": {
        "type": "object",
        "properties": {
            "include_history": {
                "type": "boolean",
                "default": False
            }
        }
    }
}

IMPORT_LEADS_TOOL = {
    "name": "import_leads",
    "description": "Import leads from the last search into the database (People or Companies). "
                   "Before calling this, ask the user: 1) Import as people or companies? "
                   "2) Which client/project tag? 3) Which industry to assign?",
    "input_schema": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "enum": ["people", "companies"],
                "description": "Import as people or companies"
            },
            "client_tag": {
                "type": "string",
                "description": "Client/project tag for cost tracking"
            },
            "industry": {
                "type": "string",
                "description": "Industry to assign to imported leads"
            },
        },
        "required": ["target", "client_tag"]
    }
}

# --- Output Tools ---

GENERATE_CSV_TOOL = {
    "name": "generate_csv",
    "description": "Genera un file CSV scaricabile con i risultati aggregati della ricerca. "
                   "Usa alla fine del framework dopo aver raccolto tutti i dati. "
                   "Le colonne devono seguire il formato: Rank, Brand, Ragione_Sociale, Citta, "
                   "Provincia, Tel, Email, Sito, Fatturato, DM_Nome, DM_Ruolo, DM_LinkedIn, "
                   "Buying_Signals, Priorita, Angolo_Outreach.",
    "input_schema": {
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Array di oggetti, ogni oggetto e' una riga del CSV"
            },
            "filename": {
                "type": "string",
                "description": "Nome file senza estensione (es. 'prospecting_agenzie_seo_milano')"
            }
        },
        "required": ["data"]
    }
}


# --- Tool collections ---

TOOL_DEFINITIONS: dict[str, dict] = {
    "save_icp": SAVE_ICP_TOOL,
    "update_icp_draft": UPDATE_ICP_DRAFT_TOOL,
    "search_apollo": SEARCH_APOLLO_TOOL,
    "search_google_maps": SEARCH_GOOGLE_MAPS_TOOL,
    "scrape_websites": SCRAPE_WEBSITES_TOOL,
    "search_linkedin_companies": SEARCH_LINKEDIN_COMPANIES_TOOL,
    "search_linkedin_people": SEARCH_LINKEDIN_PEOPLE_TOOL,
    "enrich_companies": ENRICH_COMPANIES_TOOL,
    "verify_emails": VERIFY_EMAILS_TOOL,
    "get_session_context": GET_SESSION_CONTEXT_TOOL,
    "import_leads": IMPORT_LEADS_TOOL,
    "generate_csv": GENERATE_CSV_TOOL,
}

# Prospecting mode: Apify scrapers + ICP + import + CSV (no Apollo)
PROSPECTING_TOOL_NAMES = [
    "update_icp_draft",
    "save_icp",
    "search_google_maps",
    "scrape_websites",
    "search_linkedin_companies",
    "search_linkedin_people",
    "import_leads",
    "get_session_context",
    "generate_csv",
]

# All tools (includes Apollo + enrichment for non-prospecting mode)
ALL_TOOL_NAMES = list(TOOL_DEFINITIONS.keys())


def get_tools_for_mode(mode: str) -> list[dict]:
    """Return tool definition list for a given mode."""
    if mode == "prospecting":
        return [TOOL_DEFINITIONS[name] for name in PROSPECTING_TOOL_NAMES]
    return [TOOL_DEFINITIONS[name] for name in ALL_TOOL_NAMES]
