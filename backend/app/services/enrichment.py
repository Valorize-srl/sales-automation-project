"""
Company enrichment service - Orchestrate email enrichment from websites.

This service coordinates the process of finding and saving contact emails
for companies by scraping their websites.
"""

import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.services.email_finder import EmailFinder

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of company enrichment operation."""
    company_id: int
    company_name: str
    status: str  # "completed" | "failed" | "skipped"
    emails_found: list[str]
    error: Optional[str] = None


class CompanyEnrichmentService:
    """Orchestrate company data enrichment."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_finder = EmailFinder()

    async def close(self):
        """Close resources."""
        await self.email_finder.close()

    async def enrich_company(
        self,
        company: Company,
        force: bool = False
    ) -> EnrichmentResult:
        """
        Enrich single company with email data from website.

        Process:
        1. Check if company has website
        2. Skip if recently enriched (< 7 days) unless force=True
        3. Use EmailFinder to scrape website for emails
        4. Merge with existing email from Apollo
        5. Update company record with results
        6. Return enrichment result

        Args:
            company: Company model instance
            force: Force re-enrichment even if recently enriched

        Returns:
            EnrichmentResult with status and emails found
        """
        logger.info(f"Enriching company: {company.name} (ID: {company.id})")

        # Check if company has website
        if not company.website:
            logger.debug(f"Company {company.name} has no website, skipping")
            company.enrichment_status = "not_needed"
            return EnrichmentResult(
                company_id=company.id,
                company_name=company.name,
                status="skipped",
                emails_found=[],
                error="No website URL"
            )

        # Check if recently enriched (skip unless forced)
        if not force and company.enrichment_date:
            days_since_enrichment = (datetime.utcnow() - company.enrichment_date).days
            if days_since_enrichment < 7:
                logger.debug(
                    f"Company {company.name} enriched {days_since_enrichment} days ago, skipping"
                )
                return EnrichmentResult(
                    company_id=company.id,
                    company_name=company.name,
                    status="skipped",
                    emails_found=json.loads(company.generic_emails) if company.generic_emails else [],
                    error="Recently enriched"
                )

        # Mark as pending
        company.enrichment_status = "pending"

        try:
            # Find emails on website
            finder_result = await self.email_finder.find_emails_on_website(company.website)

            if finder_result.error:
                # Enrichment failed
                logger.warning(
                    f"Failed to enrich {company.name}: {finder_result.error}"
                )
                company.enrichment_status = "failed"
                company.enrichment_date = datetime.utcnow()

                return EnrichmentResult(
                    company_id=company.id,
                    company_name=company.name,
                    status="failed",
                    emails_found=[],
                    error=finder_result.error
                )

            # Merge emails found with existing Apollo email
            all_emails = set(finder_result.emails)

            # Add existing email if not already in list
            if company.email and company.email not in all_emails:
                all_emails.add(company.email)

            # Determine enrichment source
            has_apollo_email = bool(company.email)
            has_web_emails = len(finder_result.emails) > 0

            if has_apollo_email and has_web_emails:
                enrichment_source = "both"
            elif has_web_emails:
                enrichment_source = "web_scrape"
            elif has_apollo_email:
                enrichment_source = "apollo"
            else:
                enrichment_source = None

            # Update company record
            company.generic_emails = json.dumps(sorted(all_emails))
            company.enrichment_source = enrichment_source
            company.enrichment_date = datetime.utcnow()
            company.enrichment_status = "completed"

            # If company has no primary email but we found one, set it
            if not company.email and finder_result.emails:
                company.email = finder_result.emails[0]
                # Extract email domain
                if '@' in company.email:
                    company.email_domain = company.email.split('@')[1].lower()

            logger.info(
                f"Enriched {company.name}: found {len(finder_result.emails)} emails"
            )

            return EnrichmentResult(
                company_id=company.id,
                company_name=company.name,
                status="completed",
                emails_found=sorted(all_emails)
            )

        except Exception as e:
            logger.error(f"Error enriching {company.name}: {e}", exc_info=True)
            company.enrichment_status = "failed"
            company.enrichment_date = datetime.utcnow()

            return EnrichmentResult(
                company_id=company.id,
                company_name=company.name,
                status="failed",
                emails_found=[],
                error=str(e)
            )

    async def enrich_companies_batch(
        self,
        companies: list[Company],
        max_concurrent: int = 3,
        force: bool = False
    ) -> list[EnrichmentResult]:
        """
        Enrich multiple companies concurrently with rate limiting.

        This method processes companies in batches to avoid overwhelming
        target servers and our own resources.

        Args:
            companies: List of Company instances to enrich
            max_concurrent: Maximum number of concurrent enrichments (default: 3)
            force: Force re-enrichment even if recently enriched

        Returns:
            List of EnrichmentResults
        """
        logger.info(
            f"Starting batch enrichment of {len(companies)} companies "
            f"(max_concurrent={max_concurrent})"
        )

        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_semaphore(company: Company) -> EnrichmentResult:
            """Wrapper to apply semaphore rate limiting."""
            async with semaphore:
                result = await self.enrich_company(company, force=force)
                # Small delay between requests to same domain
                await asyncio.sleep(0.5)
                return result

        # Create tasks for all companies
        tasks = [enrich_with_semaphore(company) for company in companies]

        # Execute concurrently with rate limiting
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions that occurred
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Exception enriching company {companies[i].name}: {result}"
                )
                final_results.append(
                    EnrichmentResult(
                        company_id=companies[i].id,
                        company_name=companies[i].name,
                        status="failed",
                        emails_found=[],
                        error=str(result)
                    )
                )
            else:
                final_results.append(result)

        # Summary
        completed = sum(1 for r in final_results if r.status == "completed")
        failed = sum(1 for r in final_results if r.status == "failed")
        skipped = sum(1 for r in final_results if r.status == "skipped")

        logger.info(
            f"Batch enrichment complete: {completed} completed, "
            f"{failed} failed, {skipped} skipped"
        )

        return final_results
