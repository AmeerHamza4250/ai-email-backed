"""
Campaign Pydantic schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from src.models.campaign import CampaignStatus


class CampaignBase(BaseModel):
    """Base campaign schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    email_template: Optional[str] = None


class CampaignCreate(CampaignBase):
    """Schema for campaign creation."""
    lead_ids: Optional[List[UUID]] = None  # Leads to include in campaign


class CampaignResponse(CampaignBase):
    """Schema for campaign response."""
    id: UUID
    user_id: UUID
    status: CampaignStatus
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    """Schema for campaign list response."""
    campaigns: List[CampaignResponse]
    total: int
    page: int
    page_size: int


class GenerateEmailsRequest(BaseModel):
    """Schema for email generation request."""
    lead_ids: Optional[List[UUID]] = None  # If None, generate for all leads in campaign


class GenerateEmailsResponse(BaseModel):
    """Schema for email generation response."""
    generated: int
    failed: int

