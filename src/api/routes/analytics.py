"""
Analytics API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.api.middleware.auth import get_current_user
from src.models.user import User
from src.services.analytics_service import AnalyticsService
from src.schemas.common import ApiResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/dashboard", response_model=ApiResponse)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics for the authenticated user."""
    try:
        analytics_service = AnalyticsService(db)
        stats = await analytics_service.get_dashboard_stats(current_user.id)
        
        return ApiResponse(
            status="success",
            message="Dashboard statistics retrieved successfully",
            data=stats
        )
    except Exception as e:
        logger.exception("Error getting dashboard stats", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving dashboard statistics"
        )


@router.get("/campaigns/{campaign_id}", response_model=ApiResponse)
async def get_campaign_stats(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get campaign statistics for a specific campaign."""
    try:
        from uuid import UUID
        campaign_id_uuid = UUID(campaign_id)
        
        analytics_service = AnalyticsService(db)
        stats = await analytics_service.get_campaign_stats(current_user.id, campaign_id_uuid)
        
        return ApiResponse(
            status="success",
            message="Campaign statistics retrieved successfully",
            data=stats
        )
    except ValueError as e:
        if "Campaign not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid campaign ID"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting campaign stats", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving campaign statistics"
        )

