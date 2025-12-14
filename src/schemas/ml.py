"""
ML schemas for API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class ModelMetadata(BaseModel):
    """Model metadata schema."""
    id: UUID
    name: str
    description: Optional[str] = None
    model_type: str
    accuracy: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    is_active: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ModelListResponse(BaseModel):
    """Response for listing models."""
    models: List[ModelMetadata]
    total: int


class PredictionRequest(BaseModel):
    """Request for single prediction."""
    subject: str = Field(..., description="Email subject")
    body: Optional[str] = Field(None, description="Email body")
    lead_email: str = Field(..., description="Lead email address")
    lead_name: Optional[str] = Field(None, description="Lead name")
    lead_company: Optional[str] = Field(None, description="Lead company")
    additional_data: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class PredictionResponse(BaseModel):
    """Response for prediction."""
    score: float = Field(..., description="Reply probability (0-1)", ge=0, le=1)
    confidence: Optional[float] = Field(None, description="Confidence level")
    prediction: bool = Field(..., description="Binary prediction (True if score >= 0.5)")
    model_version: Optional[str] = Field(None, description="Model version used")


class BatchPredictionRequest(BaseModel):
    """Request for batch prediction."""
    predictions: List[PredictionRequest] = Field(..., description="List of prediction requests")
    model_version: Optional[str] = Field(None, description="Specific model version to use")


class BatchPredictionResponse(BaseModel):
    """Response for batch prediction."""
    predictions: List[PredictionResponse]
    model_version: str
    total: int


class LeadRankingItem(BaseModel):
    """Item in lead ranking response."""
    lead_id: UUID
    lead_email: str
    lead_name: Optional[str]
    score: float = Field(..., ge=0, le=1)
    confidence: Optional[float] = None
    campaign_lead_id: Optional[UUID] = None


class LeadRankingResponse(BaseModel):
    """Response for lead ranking."""
    leads: List[LeadRankingItem]
    total: int
    model_version: str


class TrainingRequest(BaseModel):
    """Request to trigger model training."""
    model_name: Optional[str] = Field("Reply Predictor", description="Name for the model")
    use_bert: bool = Field(True, description="Whether to use BERT model")
    test_size: float = Field(0.15, description="Test set proportion", ge=0, le=0.5)
    val_size: float = Field(0.15, description="Validation set proportion", ge=0, le=0.5)


class TrainingResponse(BaseModel):
    """Response for training request."""
    status: str = Field(..., description="Training status")
    message: str = Field(..., description="Status message")
    model_version: Optional[str] = Field(None, description="Model version if training completed")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Training metrics")


class ModelInfoResponse(BaseModel):
    """Response for model information."""
    version: str
    model_name: str
    trained_at: Optional[datetime] = None
    training_samples: Optional[int] = None
    test_accuracy: Optional[float] = None
    test_f1: Optional[float] = None
    test_roc_auc: Optional[float] = None
    validation_metrics: Optional[Dict[str, Any]] = None
    test_metrics: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = Field(None, alias="model_config", description="Model configuration parameters")
    
    class Config:
        populate_by_name = True


class SentEmailPrediction(BaseModel):
    """Prediction result for a sent email."""
    campaign_lead_id: UUID
    lead_id: UUID
    lead_name: Optional[str] = None
    lead_email: str
    lead_company: Optional[str] = None
    campaign_id: UUID
    campaign_name: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    opened: bool = False
    clicked: bool = False
    replied: bool = False
    bounced: bool = False
    # Prediction fields
    reply_probability: float = Field(..., description="Reply probability (0-1)", ge=0, le=1)
    confidence: float = Field(..., description="Confidence level (0-1)", ge=0, le=1)
    prediction: bool = Field(..., description="Binary prediction (True = likely to reply)")
    model_version: Optional[str] = None
    
    class Config:
        from_attributes = True


class SentEmailPredictionsResponse(BaseModel):
    """Response for sent email predictions."""
    predictions: List[SentEmailPrediction]
    total: int
    model_version: str


