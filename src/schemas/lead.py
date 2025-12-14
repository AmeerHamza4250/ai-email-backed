"""
Lead Pydantic schemas.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class LeadBase(BaseModel):
    """Base lead schema."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: Optional[str] = Field(None, max_length=255)


class LeadCreate(LeadBase):
    """Schema for lead creation."""
    email_id: Optional[str] = Field(None, max_length=255)
    email_subject: Optional[str] = Field(None, max_length=500)
    email_type: Optional[str] = Field(None, max_length=255)
    sent_status: Optional[str] = Field(None, max_length=50)
    reply_status: Optional[str] = Field(None, max_length=50)
    time_to_reply_hours: Optional[str] = Field(None, max_length=50)
    additional_data: Optional[Dict[str, Any]] = None


class LeadResponse(LeadBase):
    """Schema for lead response."""
    id: UUID
    user_id: UUID
    email_id: Optional[str] = None
    email_subject: Optional[str] = None
    email_type: Optional[str] = None
    sent_status: Optional[str] = None
    reply_status: Optional[str] = None
    time_to_reply_hours: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    """Schema for lead list response."""
    leads: list[LeadResponse]
    total: int
    page: int
    page_size: int


class UploadLeadsResponse(BaseModel):
    """Schema for CSV upload response."""
    imported: int
    failed: int
    errors: list[str] = []

