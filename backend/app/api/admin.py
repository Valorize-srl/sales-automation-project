"""
Admin endpoints for maintenance and backfill operations.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.email_response import EmailResponse
from app.models.campaign import Campaign
from app.services.instantly import instantly_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/backfill-sender-emails")
async def backfill_sender_emails(db: AsyncSession = Depends(get_db)):
    """
    Backfill sender_email for existing EmailResponse records.

    This endpoint queries all EmailResponse records with sender_email = NULL
    and updates them by fetching the eaccount from Instantly's API.
    """
    # Query all responses with NULL sender_email but valid instantly_email_id
    result = await db.execute(
        select(EmailResponse).where(
            EmailResponse.sender_email.is_(None),
            EmailResponse.instantly_email_id.isnot(None)
        )
    )
    responses = result.scalars().all()

    logger.info(f"Found {len(responses)} responses to backfill")

    updated_count = 0
    error_count = 0
    skipped_count = 0

    for resp in responses:
        try:
            if not resp.campaign_id:
                logger.warning(f"Response {resp.id} has no campaign_id, skipping")
                skipped_count += 1
                continue

            # Get campaign to fetch instantly_campaign_id
            campaign_result = await db.execute(
                select(Campaign).where(Campaign.id == resp.campaign_id)
            )
            campaign = campaign_result.scalar_one_or_none()

            if not campaign or not campaign.instantly_campaign_id:
                logger.warning(
                    f"Response {resp.id} campaign has no instantly_campaign_id, skipping"
                )
                skipped_count += 1
                continue

            # Fetch emails from campaign and find matching one
            logger.info(
                f"Searching for email {resp.instantly_email_id} in campaign {campaign.instantly_campaign_id}"
            )

            # Fetch with pagination
            starting_after = None
            found = False
            max_pages = 10  # Limit to avoid excessive API calls

            for page in range(max_pages):
                email_data = await instantly_service.list_emails(
                    campaign_id=campaign.instantly_campaign_id,
                    email_type="received",
                    limit=100,
                    starting_after=starting_after,
                )

                items = email_data.get("items", [])

                for email_item in items:
                    if email_item.get("id") == resp.instantly_email_id:
                        # Found it! Extract eaccount
                        eaccount = email_item.get("eaccount")
                        if eaccount:
                            resp.sender_email = eaccount
                            logger.info(
                                f"Updated response {resp.id} with sender_email: {eaccount}"
                            )
                            updated_count += 1
                            found = True
                            break
                        else:
                            logger.warning(
                                f"Email {resp.instantly_email_id} has no eaccount field"
                            )
                            skipped_count += 1
                            break

                if found:
                    break

                # Check for next page
                next_cursor = email_data.get("next_starting_after")
                if not next_cursor or len(items) < 100:
                    break
                starting_after = next_cursor

            if not found:
                logger.warning(
                    f"Could not find email {resp.instantly_email_id} in Instantly API"
                )
                error_count += 1

        except Exception as e:
            logger.error(f"Error processing response {resp.id}: {str(e)}")
            error_count += 1
            continue

    # Commit all updates
    await db.commit()

    result_message = {
        "total_found": len(responses),
        "updated": updated_count,
        "errors": error_count,
        "skipped": skipped_count,
        "message": f"Backfill complete: {updated_count} updated, {error_count} errors, {skipped_count} skipped",
    }

    logger.info(result_message["message"])
    return result_message
