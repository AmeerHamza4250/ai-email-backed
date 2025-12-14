"""
CampaignLead model for linking leads to campaigns.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.base import Base
import uuid


class CampaignLead(Base):
    """CampaignLead model linking leads to campaigns with generated email content."""
    __tablename__ = "campaign_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Generated email content
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    
    # Email status
    sent = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tracking flags
    opened = Column(Boolean, default=False, nullable=False)
    clicked = Column(Boolean, default=False, nullable=False)
    replied = Column(Boolean, default=False, nullable=False)
    bounced = Column(Boolean, default=False, nullable=False)
    
    # Resend message ID for tracking
    resend_message_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_leads")
    lead = relationship("Lead", back_populates="campaign_leads")
    email_events = relationship("EmailEvent", back_populates="campaign_lead", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CampaignLead {self.campaign_id}:{self.lead_id}>"
"""
AI Leads.
"""