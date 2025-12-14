"""
Email generation and sending API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.api.middleware.auth import get_current_user
from src.models.user import User
from src.schemas.campaign import GenerateEmailsRequest, GenerateEmailsResponse
from src.schemas.email import SendEmailsRequest, SendEmailsResponse, EmailStatusResponse
from src.services.email_service import EmailService
from src.schemas.common import ApiResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/campaigns/{campaign_id}/generate-emails", response_model=ApiResponse)
async def generate_emails(
    campaign_id: str,
    request: GenerateEmailsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate personalized emails for campaign leads."""
    try:
        from uuid import UUID
        campaign_id_uuid = UUID(campaign_id)
        
        email_service = EmailService(db)
        generated, failed = await email_service.generate_emails_for_campaign(
            campaign_id_uuid,
            current_user.id,
            lead_ids=request.lead_ids
        )
        
        return ApiResponse(
            status="success",
            message=f"Generated {generated} emails, {failed} failed",
            data=GenerateEmailsResponse(
                generated=generated,
                failed=failed
            ).model_dump()
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Error generating emails", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating emails: {str(e)}"
        )


@router.post("/campaigns/{campaign_id}/send", response_model=ApiResponse)
async def send_emails(
    campaign_id: str,
    request: SendEmailsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send emails for campaign leads via Resend."""
    try:
        from uuid import UUID
        campaign_id_uuid = UUID(campaign_id)
        
        email_service = EmailService(db)
        sent, failed, errors = await email_service.send_emails_for_campaign(
            campaign_id_uuid,
            current_user.id,
            campaign_lead_ids=request.campaign_lead_ids
        )
        
        return ApiResponse(
            status="success",
            message=f"Sent {sent} emails, {failed} failed",
            data=SendEmailsResponse(
                sent=sent,
                failed=failed,
                errors=errors[:10]  # Limit errors
            ).model_dump()
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Error sending emails", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending emails: {str(e)}"
        )

