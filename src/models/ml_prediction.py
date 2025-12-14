"""
MLPrediction model for storing lead predictions.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from src.database.base import Base
import uuid


class MLPrediction(Base):
    """MLPrediction for storing lead scoring predictions."""
    __tablename__ = "ml_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False)  # Prediction score (0-1)
    confidence = Column(Float, nullable=True)  # Confidence level
    features = Column(JSONB, nullable=True)  # Input features used
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<MLPrediction {self.lead_id}: {self.score}>"
"""
AI Leads.
"""