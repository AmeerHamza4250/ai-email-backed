"""
EmailEvent model for tracking email interactions.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.base import Base
import uuid
import enum


class EmailEventType(str, enum.Enum):
    """Email event types from Resend webhooks."""
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    UNSUBSCRIBED = "unsubscribed"


class EmailEvent(Base):
    """EmailEvent model for storing email interaction events."""
    __tablename__ = "email_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_lead_id = Column(UUID(as_uuid=True), ForeignKey("campaign_leads.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Enum(EmailEventType), nullable=False)
    event_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    campaign_lead = relationship("CampaignLead", back_populates="email_events")

    def __repr__(self):
        return f"<EmailEvent {self.event_type} for {self.campaign_lead_id}>"
"""
AI Leads.
"""