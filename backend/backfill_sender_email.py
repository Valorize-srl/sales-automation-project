"""
Backfill sender_email for existing EmailResponse records.

This script queries all EmailResponse records with sender_email = NULL
and updates them by fetching the eaccount from Instantly's API.
"""
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.email_response import EmailResponse
from app.services.instantly import instantly_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_sender_emails():
    """Backfill sender_email for existing responses."""
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Query all responses with NULL sender_email but valid instantly_email_id
        result = await session.execute(
            select(EmailResponse).where(
                EmailResponse.sender_email.is_(None),
                EmailResponse.instantly_email_id.isnot(None)
            )
        )
        responses = result.scalars().all()

        logger.info(f"Found {len(responses)} responses to backfill")

        updated_count = 0
        error_count = 0

        for resp in responses:
            try:
                # Fetch email details from Instantly API
                # We'll use the list_emails endpoint and filter by the specific email ID
                # Note: Instantly API v2 doesn't have a direct GET /emails/{id} endpoint
                # So we need to fetch from the campaign and find the specific email

                if not resp.campaign_id:
                    logger.warning(f"Response {resp.id} has no campaign_id, skipping")
                    continue

                # Get campaign to fetch instantly_campaign_id
                from app.models.campaign import Campaign
                campaign_result = await session.execute(
                    select(Campaign).where(Campaign.id == resp.campaign_id)
                )
                campaign = campaign_result.scalar_one_or_none()

                if not campaign or not campaign.instantly_campaign_id:
                    logger.warning(f"Response {resp.id} campaign has no instantly_campaign_id, skipping")
                    continue

                # Fetch emails from campaign and find matching one
                # We'll search through received emails
                logger.info(f"Fetching emails for campaign {campaign.instantly_campaign_id} to find email {resp.instantly_email_id}")

                # Fetch with pagination
                starting_after = None
                found = False
                max_pages = 10  # Limit to avoid infinite loop

                for page in range(max_pages):
                    email_data = await instantly_service.list_emails(
                        campaign_id=campaign.instantly_campaign_id,
                        email_type="received",
                        limit=100,
                        starting_after=starting_after
                    )

                    items = email_data.get("items", [])

                    for email_item in items:
                        if email_item.get("id") == resp.instantly_email_id:
                            # Found it! Extract eaccount
                            eaccount = email_item.get("eaccount")
                            if eaccount:
                                resp.sender_email = eaccount
                                logger.info(f"Updated response {resp.id} with sender_email: {eaccount}")
                                updated_count += 1
                                found = True
                                break
                            else:
                                logger.warning(f"Email {resp.instantly_email_id} has no eaccount field")
                                break

                    if found:
                        break

                    # Check for next page
                    next_cursor = email_data.get("next_starting_after")
                    if not next_cursor or len(items) < 100:
                        break
                    starting_after = next_cursor

                if not found:
                    logger.warning(f"Could not find email {resp.instantly_email_id} in Instantly API")
                    error_count += 1

            except Exception as e:
                logger.error(f"Error processing response {resp.id}: {str(e)}")
                error_count += 1
                continue

        # Commit all updates
        await session.commit()

        logger.info(f"Backfill complete: {updated_count} updated, {error_count} errors")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill_sender_emails())
