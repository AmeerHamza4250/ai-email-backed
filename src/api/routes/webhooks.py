"""
Webhook handlers for external services (Resend, etc.).
"""
from fastapi import APIRouter, Request, HTTPException, status, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.models.email_event import EmailEventType
from src.services.email_service import EmailService
from src.utils.logger import get_logger
from typing import Optional
import json

logger = get_logger(__name__)

router = APIRouter()


@router.post("/resend")
async def resend_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Resend webhook events."""
    try:
        body = await request.json()
        
        # Resend webhook format
        event_type = body.get("type")
        data = body.get("data", {})
        
        # Map Resend event types to our EmailEventType
        event_type_map = {
            "email.sent": EmailEventType.SENT,
            "email.delivered": EmailEventType.DELIVERED,
            "email.opened": EmailEventType.OPENED,
            "email.clicked": EmailEventType.CLICKED,
            "email.bounced": EmailEventType.BOUNCED,
            "email.complained": EmailEventType.BOUNCED,  # Treat complaints as bounces
        }
        
        our_event_type = event_type_map.get(event_type)
        
        if not our_event_type:
            logger.warning(f"Unknown Resend event type: {event_type}")
            return {"status": "ignored"}
        
        # Extract email_id from webhook data
        email_id = data.get("email_id") or data.get("id")
        
        if not email_id:
            logger.warning("No email_id in webhook data")
            return {"status": "ignored"}
        
        # Find campaign_lead by resend_message_id
        from sqlalchemy import select
        from src.models.campaign_lead import CampaignLead
        
        stmt = select(CampaignLead).where(
            CampaignLead.resend_message_id == str(email_id)
        )
        
        result = await db.execute(stmt)
        campaign_lead = result.scalar_one_or_none()
        campaign_lead_id = None
        
        if campaign_lead:
            campaign_lead_id = campaign_lead.id
        else:
            # Fallback: try to find via email events
            from src.models.email_event import EmailEvent
            
            stmt = select(EmailEvent).where(
                EmailEvent.event_data["email_id"].astext == str(email_id)
            ).order_by(EmailEvent.created_at.desc()).limit(1)
            
            result = await db.execute(stmt)
            email_event = result.scalar_one_or_none()
            
            if email_event:
                campaign_lead_id = email_event.campaign_lead_id
                # Fetch the campaign_lead for updating flags
                stmt = select(CampaignLead).where(CampaignLead.id == campaign_lead_id)
                result = await db.execute(stmt)
                campaign_lead = result.scalar_one_or_none()
            else:
                logger.warning(f"Could not find campaign_lead for email_id: {email_id}")
                return {"status": "ignored"}
        
        if not campaign_lead_id:
            logger.warning(f"Could not determine campaign_lead_id for email_id: {email_id}")
            return {"status": "ignored"}
        
        # Create new event for this webhook
        email_service = EmailService(db)
        await email_service.track_email_event(
            campaign_lead_id=campaign_lead_id,
            event_type=our_event_type,
            metadata={"resend_data": data, "email_id": email_id}
        )
        
        # Update campaign_lead flags based on event type
        if campaign_lead:
            if our_event_type == EmailEventType.OPENED:
                campaign_lead.opened = True
            elif our_event_type == EmailEventType.CLICKED:
                campaign_lead.clicked = True
            elif our_event_type == EmailEventType.BOUNCED:
                campaign_lead.bounced = True
            await db.commit()
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.exception("Error processing Resend webhook", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )

