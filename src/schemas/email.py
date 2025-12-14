"""
Email Pydantic schemas.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from src.models.email_event import EmailEventType


class EmailEventResponse(BaseModel):
    """Schema for email event response."""
    id: UUID
    campaign_lead_id: UUID
    event_type: EmailEventType
    event_data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SendEmailsRequest(BaseModel):
    """Schema for sending emails request."""
    campaign_lead_ids: Optional[List[UUID]] = None  # If None, send to all in campaign


class SendEmailsResponse(BaseModel):
    """Schema for email sending response."""
    sent: int
    failed: int
    errors: List[str] = []


class EmailStatusResponse(BaseModel):
    """Schema for email status response."""
    campaign_lead_id: UUID
    sent: bool
    sent_at: Optional[datetime] = None
    opened: bool
    clicked: bool
    replied: bool
    bounced: bool
    events: List[EmailEventResponse] = []

