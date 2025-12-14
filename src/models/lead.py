"""
Lead model for storing lead information.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.base import Base
import uuid


class Lead(Base):
    """Lead model for storing potential customer information."""
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=True)
    
    # CSV import fields
    email_id = Column(String(255), nullable=True, index=True)  # Email_ID from CSV
    email_subject = Column(String(500), nullable=True)  # Email_Subject from CSV
    email_type = Column(String(255), nullable=True)  # Email_Type from CSV
    sent_status = Column(String(50), nullable=True)  # Sent_Status from CSV
    reply_status = Column(String(50), nullable=True)  # Reply_Status from CSV (can be True/False or string)
    time_to_reply_hours = Column(String(50), nullable=True)  # Time_to_Reply_Hours from CSV
    
    additional_data = Column(JSONB, nullable=True)  # For any other fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    campaign_leads = relationship("CampaignLead", back_populates="lead", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lead {self.email}>"
"""
AI Leads.
"""