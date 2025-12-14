"""
Database models for AI Leads.
"""
from src.models.user import User
from src.models.lead import Lead
from src.models.campaign import Campaign, CampaignStatus
from src.models.campaign_lead import CampaignLead
from src.models.email_event import EmailEvent, EmailEventType
from src.models.ml_model import MLModel
from src.models.ml_prediction import MLPrediction

__all__ = [
    "User",
    "Lead",
    "Campaign",
    "CampaignStatus",
    "CampaignLead",
    "EmailEvent",
    "EmailEventType",
    "MLModel",
    "MLPrediction",
]
"""
AI Leads.
"""