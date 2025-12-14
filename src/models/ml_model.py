"""
MLModel model for storing trained machine learning models.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from src.database.base import Base
import uuid


class MLModel(Base):
    """MLModel for storing trained lead scoring models."""
    __tablename__ = "ml_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    model_type = Column(String(100), nullable=False)  # e.g., "lead_scoring", "engagement_prediction"
    model_path = Column(String(500), nullable=True)  # Path to serialized model
    metrics = Column(JSONB, nullable=True)  # Training metrics
    accuracy = Column(Float, nullable=True)
    is_active = Column(String(50), default="inactive", nullable=False)  # "active", "inactive", "training"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MLModel {self.name}>"
"""
AI Leads.
"""