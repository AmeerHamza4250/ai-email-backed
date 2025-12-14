"""
Campaign service for managing campaigns.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from uuid import UUID
from src.models.campaign import Campaign, CampaignStatus
from src.models.lead import Lead
from src.models.campaign_lead import CampaignLead
from src.schemas.campaign import CampaignCreate, CampaignResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CampaignService:
    """Service for campaign operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_campaign(
        self, 
        user_id: UUID, 
        campaign_data: CampaignCreate,
        lead_ids: Optional[List[UUID]] = None
    ) -> Campaign:
        """Create a new campaign."""
        new_campaign = Campaign(
            user_id=user_id,
            name=campaign_data.name,
            description=campaign_data.description,
            email_template=campaign_data.email_template,
            status=CampaignStatus.DRAFT
        )
        
        self.db.add(new_campaign)
        await self.db.flush()  # Get the ID
        
        # Add leads to campaign if provided
        if lead_ids:
            await self.add_leads_to_campaign(new_campaign.id, user_id, lead_ids)
        
        await self.db.commit()
        await self.db.refresh(new_campaign)
        
        return new_campaign
    
    async def add_leads_to_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
        lead_ids: List[UUID]
    ) -> int:
        """Add leads to a campaign."""
        # Verify campaign belongs to user
        stmt = select(Campaign).where(
            and_(Campaign.id == campaign_id, Campaign.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise ValueError("Campaign not found")
        
        # Get leads
        stmt = select(Lead).where(
            and_(Lead.id.in_(lead_ids), Lead.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        leads = result.scalars().all()
        
        # Create campaign-lead associations
        added = 0
        for lead in leads:
            # Check if already exists
            existing_stmt = select(CampaignLead).where(
                and_(
                    CampaignLead.campaign_id == campaign_id,
                    CampaignLead.lead_id == lead.id
                )
            )
            existing_result = await self.db.execute(existing_stmt)
            if existing_result.scalar_one_or_none():
                continue
            
            campaign_lead = CampaignLead(
                campaign_id=campaign_id,
                lead_id=lead.id
            )
            self.db.add(campaign_lead)
            added += 1
        
        await self.db.commit()
        return added
    
    async def get_campaigns(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[Campaign], int]:
        """Get campaigns for a user with pagination."""
        # Count total
        count_stmt = select(Campaign).where(Campaign.user_id == user_id)
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())
        
        # Get paginated results
        stmt = select(Campaign).where(
            Campaign.user_id == user_id
        ).order_by(Campaign.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(stmt)
        campaigns = result.scalars().all()
        
        return list(campaigns), total
    
    async def get_campaign_by_id(self, user_id: UUID, campaign_id: UUID) -> Optional[Campaign]:
        """Get a campaign by ID for a specific user."""
        stmt = select(Campaign).where(
            and_(Campaign.id == campaign_id, Campaign.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_campaign_status(
        self,
        campaign_id: UUID,
        user_id: UUID,
        status: CampaignStatus
    ) -> Campaign:
        """Update campaign status."""
        campaign = await self.get_campaign_by_id(user_id, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        campaign.status = status
        await self.db.commit()
        await self.db.refresh(campaign)
        
        return campaign

