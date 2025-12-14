"""
Campaign model for email campaigns.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.base import Base
import uuid
import enum


class CampaignStatus(str, enum.Enum):
    """Campaign status enum."""
    DRAFT = "draft"
    GENERATING = "generating"
    ACTIVE = "active"
    SENDING = "sending"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Campaign(Base):
    """Campaign model for email marketing campaigns."""
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    email_template = Column(Text, nullable=True)
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    campaign_leads = relationship("CampaignLead", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Campaign {self.name}>"
"""
AI Leads.
"""