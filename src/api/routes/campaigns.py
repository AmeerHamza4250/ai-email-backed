"""
Campaigns API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.api.middleware.auth import get_current_user
from src.models.user import User
from src.schemas.campaign import (
    CampaignCreate, CampaignResponse, CampaignListResponse, GenerateEmailsRequest
)
from src.services.campaign_service import CampaignService
from src.schemas.common import ApiResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=ApiResponse)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new campaign."""
    try:
        campaign_service = CampaignService(db)
        campaign = await campaign_service.create_campaign(
            current_user.id,
            campaign_data,
            lead_ids=campaign_data.lead_ids
        )
        
        return ApiResponse(
            status="success",
            message="Campaign created successfully",
            data=CampaignResponse.model_validate(campaign).model_dump()
        )
    except Exception as e:
        logger.exception("Error creating campaign", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating campaign: {str(e)}"
        )


@router.get("", response_model=ApiResponse)
async def list_campaigns(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all campaigns for the authenticated user."""
    try:
        campaign_service = CampaignService(db)
        campaigns, total = await campaign_service.get_campaigns(
            current_user.id,
            page=page,
            page_size=page_size
        )
        
        return ApiResponse(
            status="success",
            message="Campaigns retrieved successfully",
            data=CampaignListResponse(
                campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
                total=total,
                page=page,
                page_size=page_size
            ).model_dump()
        )
    except Exception as e:
        logger.exception("Error listing campaigns", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving campaigns"
        )


@router.get("/{campaign_id}", response_model=ApiResponse)
async def get_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get campaign details."""
    try:
        from uuid import UUID
        campaign_id_uuid = UUID(campaign_id)
        
        campaign_service = CampaignService(db)
        campaign = await campaign_service.get_campaign_by_id(
            current_user.id,
            campaign_id_uuid
        )
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        return ApiResponse(
            status="success",
            message="Campaign retrieved successfully",
            data=CampaignResponse.model_validate(campaign).model_dump()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid campaign ID"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting campaign", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving campaign"
        )

