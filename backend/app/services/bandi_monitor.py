"""
Bandi Monitor Service — fetches government grants from RSS feeds and web sources,
analyzes them with Claude AI to extract structured data (ATECO codes, targets, deadlines).
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import anthropic
import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.bando import Bando, BandoSource, BandoStatus
from app.models.company import Company

logger = logging.getLogger(__name__)

# RSS feed URLs
FEED_SOURCES = {
    BandoSource.MIMIT: "https://www.mimit.gov.it/index.php/it/incentivi?format=feed&type=rss",
}

# Scraping URLs
SCRAPE_SOURCES = {
    BandoSource.INVITALIA: "https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese",
    BandoSource.INCENTIVI_GOV: "https://www.incentivi.gov.it/it/catalogo",
}

BANDO_ANALYSIS_PROMPT = """Sei un esperto di finanza agevolata italiana. Analizza il seguente bando/incentivo e restituisci SOLO un JSON valido (senza markdown, senza ```json```) con questa struttura esatta:

{
  "ai_summary": "Riassunto chiaro in 2-3 frasi del bando, cosa finanzia e per chi",
  "target_companies": "Descrizione delle aziende target (dimensione, tipologia, requisiti)",
  "ateco_codes": ["62.01", "28.11"],
  "deadline": "2026-06-30T00:00:00Z",
  "amount_min": 10000,
  "amount_max": 200000,
  "funding_type": "fondo perduto",
  "regions": ["nazionale"],
  "sectors": ["manifattura", "tecnologia"]
}

Regole:
- ateco_codes: lista di codici ATECO pertinenti (formato XX.XX). Se non puoi determinare i codici specifici, indica i più probabili.
- deadline: data ISO se presente, null se non specificata
- amount_min/amount_max: importi in EUR, null se non specificati
- funding_type: uno tra "fondo perduto", "credito d'imposta", "finanziamento agevolato", "garanzia", "voucher", "misto"
- regions: lista di regioni italiane o "nazionale" se applicabile a tutta Italia
- sectors: lista di settori economici pertinenti in italiano

BANDO DA ANALIZZARE:

Titolo: {title}

Descrizione: {description}

Fonte: {source}
URL: {url}"""


class BandiMonitorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_all_sources(self) -> dict:
        """Fetch bandi from all configured sources. Returns stats."""
        total_fetched = 0
        total_errors = 0

        # RSS sources
        for source, feed_url in FEED_SOURCES.items():
            try:
                count = await self._fetch_rss(source, feed_url)
                total_fetched += count
                logger.info(f"Fetched {count} bandi from {source.value} RSS")
            except Exception as e:
                logger.error(f"Error fetching RSS from {source.value}: {e}")
                total_errors += 1

        # Scraping sources
        for source, url in SCRAPE_SOURCES.items():
            try:
                count = await self._fetch_scrape(source, url)
                total_fetched += count
                logger.info(f"Fetched {count} bandi from {source.value} scraping")
            except Exception as e:
                logger.error(f"Error scraping {source.value}: {e}")
                total_errors += 1

        await self.db.commit()
        return {"fetched": total_fetched, "errors": total_errors}

    async def _fetch_rss(self, source: BandoSource, feed_url: str) -> int:
        """Fetch bandi from an RSS feed using feedparser."""
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(feed_url)
            response.raise_for_status()

        feed = feedparser.parse(response.text)
        fetched = 0

        for entry in feed.entries:
            link = entry.get("link", "")
            if not link:
                continue

            # Ensure absolute URL
            if link.startswith("/"):
                link = f"https://www.mimit.gov.it{link}"

            # Dedup check
            existing = await self.db.execute(
                select(Bando.id).where(Bando.source_url == link)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            # Parse date
            published_at = None
            if entry.get("published_parsed"):
                try:
                    from time import mktime
                    published_at = datetime.fromtimestamp(
                        mktime(entry.published_parsed), tz=timezone.utc
                    )
                except Exception:
                    pass

            # Clean description HTML
            raw_desc = entry.get("description", "") or entry.get("summary", "")
            if raw_desc:
                soup = BeautifulSoup(raw_desc, "html.parser")
                raw_desc = soup.get_text(separator=" ", strip=True)

            bando = Bando(
                source=source,
                source_url=link,
                title=entry.get("title", "Senza titolo"),
                raw_description=raw_desc[:5000] if raw_desc else None,
                published_at=published_at,
                status=BandoStatus.NEW,
            )
            self.db.add(bando)
            fetched += 1

        await self.db.flush()
        return fetched

    async def _fetch_scrape(self, source: BandoSource, url: str) -> int:
        """Scrape bandi from a web page."""
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; BandiMonitor/1.0)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Could not scrape {source.value} ({url}): {e}")
            return 0

        soup = BeautifulSoup(response.text, "html.parser")
        fetched = 0

        if source == BandoSource.INVITALIA:
            fetched = await self._parse_invitalia(soup, url)
        elif source == BandoSource.INCENTIVI_GOV:
            fetched = await self._parse_incentivi_gov(soup, url)

        await self.db.flush()
        return fetched

    async def _parse_invitalia(self, soup: BeautifulSoup, base_url: str) -> int:
        """Parse Invitalia incentivi page."""
        fetched = 0
        # Look for links to incentive pages
        for link_tag in soup.find_all("a", href=True):
            href = link_tag["href"]
            title = link_tag.get_text(strip=True)

            if not title or len(title) < 10:
                continue
            if "/cosa-facciamo/" not in href and "/incentivi" not in href.lower():
                continue

            # Build absolute URL
            if href.startswith("/"):
                href = f"https://www.invitalia.it{href}"
            elif not href.startswith("http"):
                continue

            # Dedup
            existing = await self.db.execute(
                select(Bando.id).where(Bando.source_url == href)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            bando = Bando(
                source=BandoSource.INVITALIA,
                source_url=href,
                title=title[:500],
                raw_description=None,
                status=BandoStatus.NEW,
            )
            self.db.add(bando)
            fetched += 1

        return fetched

    async def _parse_incentivi_gov(self, soup: BeautifulSoup, base_url: str) -> int:
        """Parse incentivi.gov.it catalog page."""
        fetched = 0
        for link_tag in soup.find_all("a", href=True):
            href = link_tag["href"]
            title = link_tag.get_text(strip=True)

            if not title or len(title) < 10:
                continue
            if "/it/incentivo/" not in href and "/it/catalogo/" not in href:
                continue

            if href.startswith("/"):
                href = f"https://www.incentivi.gov.it{href}"
            elif not href.startswith("http"):
                continue

            existing = await self.db.execute(
                select(Bando.id).where(Bando.source_url == href)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            bando = Bando(
                source=BandoSource.INCENTIVI_GOV,
                source_url=href,
                title=title[:500],
                raw_description=None,
                status=BandoStatus.NEW,
            )
            self.db.add(bando)
            fetched += 1

        return fetched

    async def analyze_new_bandi(self) -> int:
        """Analyze all bandi with status=NEW using Claude AI."""
        if not settings.anthropic_api_key:
            logger.warning("Anthropic API key not configured, skipping analysis")
            return 0

        result = await self.db.execute(
            select(Bando)
            .where(Bando.status == BandoStatus.NEW)
            .order_by(Bando.created_at.desc())
            .limit(20)  # Process max 20 per run to limit API costs
        )
        bandi = result.scalars().all()

        analyzed = 0
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        for bando in bandi:
            try:
                await self._analyze_single(client, bando)
                analyzed += 1
            except Exception as e:
                logger.error(f"Failed to analyze bando {bando.id} ({bando.title}): {e}")

        await self.db.commit()
        return analyzed

    async def analyze_single_bando(self, bando: Bando):
        """Analyze a single bando with AI (public API for single-bando analysis)."""
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        await self._analyze_single(client, bando)

    async def _analyze_single(self, client: anthropic.AsyncAnthropic, bando: Bando):
        """Analyze a single bando with Claude."""
        description = bando.raw_description or bando.title

        # If we have no description, try to fetch the page content
        if not bando.raw_description and bando.source_url:
            try:
                async with httpx.AsyncClient(
                    timeout=15,
                    follow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; BandiMonitor/1.0)"},
                ) as http:
                    resp = await http.get(bando.source_url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        # Remove scripts and styles
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        page_text = soup.get_text(separator=" ", strip=True)
                        description = page_text[:4000]
                        bando.raw_description = description
            except Exception as e:
                logger.warning(f"Could not fetch page for bando {bando.id}: {e}")

        prompt = BANDO_ANALYSIS_PROMPT.format(
            title=bando.title,
            description=description[:4000],
            source=bando.source.value,
            url=bando.source_url,
        )

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()

        # Try to parse JSON from response
        try:
            # Remove possible markdown code fences
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw_text)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            analysis = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse AI analysis for bando {bando.id}: {raw_text[:200]}")
            bando.ai_analysis_raw = {"raw_response": raw_text}
            bando.status = BandoStatus.ANALYZED
            bando.analyzed_at = datetime.now(timezone.utc)
            return

        # Update bando with extracted data
        bando.ai_summary = analysis.get("ai_summary")
        bando.target_companies = analysis.get("target_companies")
        bando.ateco_codes = analysis.get("ateco_codes")
        bando.funding_type = analysis.get("funding_type")
        bando.regions = analysis.get("regions")
        bando.sectors = analysis.get("sectors")
        bando.ai_analysis_raw = analysis

        # Parse deadline
        deadline_str = analysis.get("deadline")
        if deadline_str:
            try:
                bando.deadline = datetime.fromisoformat(
                    deadline_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Parse amounts
        bando.amount_min = analysis.get("amount_min")
        bando.amount_max = analysis.get("amount_max")

        bando.status = BandoStatus.ANALYZED
        bando.analyzed_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def get_stats(self) -> dict:
        """Get bandi statistics."""
        total = (await self.db.execute(
            select(sa_func.count(Bando.id))
        )).scalar() or 0

        new_count = (await self.db.execute(
            select(sa_func.count(Bando.id)).where(Bando.status == BandoStatus.NEW)
        )).scalar() or 0

        analyzed_count = (await self.db.execute(
            select(sa_func.count(Bando.id)).where(Bando.status == BandoStatus.ANALYZED)
        )).scalar() or 0

        # Expiring within 30 days
        from datetime import timedelta
        threshold = datetime.now(timezone.utc) + timedelta(days=30)
        expiring_soon = (await self.db.execute(
            select(sa_func.count(Bando.id)).where(
                Bando.deadline.isnot(None),
                Bando.deadline <= threshold,
                Bando.deadline > datetime.now(timezone.utc),
                Bando.status != BandoStatus.ARCHIVED,
            )
        )).scalar() or 0

        # Breakdown by source
        source_rows = (await self.db.execute(
            select(Bando.source, sa_func.count(Bando.id)).group_by(Bando.source)
        )).all()
        sources_breakdown = {row[0]: row[1] for row in source_rows}

        return {
            "total": total,
            "new_count": new_count,
            "analyzed_count": analyzed_count,
            "expiring_soon": expiring_soon,
            "sources_breakdown": sources_breakdown,
        }

    async def find_matching_companies(self, bando_id: int) -> list[dict]:
        """Find companies in DB that match a bando's criteria."""
        bando = await self.db.get(Bando, bando_id)
        if not bando:
            return []

        sectors = bando.sectors or []
        ateco_codes = bando.ateco_codes or []

        if not sectors and not ateco_codes:
            return []

        # Build search conditions
        from sqlalchemy import or_, Text as SAText
        conditions = []
        for sector in sectors:
            conditions.append(Company.industry.ilike(f"%{sector}%"))
        for code in ateco_codes:
            conditions.append(Company.tags.cast(SAText).ilike(f"%{code}%"))

        if not conditions:
            return []

        result = await self.db.execute(
            select(Company)
            .where(or_(*conditions))
            .limit(50)
        )
        companies = result.scalars().all()

        return [
            {
                "company_id": c.id,
                "name": c.name,
                "industry": c.industry,
                "match_reason": "Settore/ATECO compatibile",
            }
            for c in companies
        ]
