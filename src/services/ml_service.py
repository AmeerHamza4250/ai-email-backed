"""
ML service for predictions and lead ranking.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any, Optional
from uuid import UUID
import numpy as np

from src.models.lead import Lead
from src.models.campaign_lead import CampaignLead
from src.models.ml_prediction import MLPrediction
from src.models.ml_model import MLModel
from src.ml.utils.model_loader import get_model_loader
from src.ml.models.reply_predictor import ReplyPredictor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MLService:
    """Service for ML predictions and lead ranking."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.model_loader = get_model_loader()
        self._cached_model: Optional[ReplyPredictor] = None
        self._cached_version: Optional[str] = None
    
    def _get_model(self, version: Optional[str] = None) -> ReplyPredictor:
        """Get loaded model, using cache if available."""
        # Get latest version if not specified
        if version is None:
            latest = self.model_loader.get_latest_model()
            if not latest:
                raise ValueError("No trained model available. Please train a model first.")
            version = latest['version']
        
        # Use cached model if same version
        if self._cached_model and self._cached_version == version:
            return self._cached_model
        
        # Load model
        model = self.model_loader.load_model(version)
        self._cached_model = model
        self._cached_version = version
        
        return model
    
    async def predict(
        self,
        subject: str,
        body: Optional[str],
        lead_email: str,
        lead_name: Optional[str] = None,
        lead_company: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict reply probability for a single lead.
        
        Args:
            subject: Email subject
            body: Email body (optional)
            lead_email: Lead email address
            lead_name: Lead name (optional)
            lead_company: Lead company (optional)
            additional_data: Additional metadata
            model_version: Specific model version to use
            
        Returns:
            Dictionary with prediction results
        """
        try:
            # Get model
            model = self._get_model(model_version)
            
            # Prepare data
            data = [{
                'subject': subject or '',
                'body': body or '',
                'email': lead_email,
                'name': lead_name or '',
                'company': lead_company or '',
                'opened': False,
                'clicked': False,
                'replied': False,
                'bounced': False,
                'sent': True,
                'sent_at': None,
                'additional_data': additional_data
            }]
            
            # Predict
            proba = model.predict_proba(data)
            score = float(proba[0][1])  # Probability of reply
            
            # Get model version
            if model_version is None:
                latest = self.model_loader.get_latest_model()
                model_version = latest['version'] if latest else None
            
            return {
                'score': score,
                'confidence': abs(score - 0.5) * 2,  # Confidence: distance from 0.5
                'prediction': score >= 0.5,
                'model_version': model_version
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise
    
    async def predict_batch(
        self,
        predictions_data: List[Dict[str, Any]],
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict reply probabilities for multiple leads.
        
        Args:
            predictions_data: List of prediction data dictionaries
            model_version: Specific model version to use
            
        Returns:
            Dictionary with batch prediction results
        """
        try:
            # Get model
            model = self._get_model(model_version)
            
            # Prepare data
            data = []
            for pred_data in predictions_data:
                data.append({
                    'subject': pred_data.get('subject', ''),
                    'body': pred_data.get('body', ''),
                    'email': pred_data.get('lead_email', ''),
                    'name': pred_data.get('lead_name', ''),
                    'company': pred_data.get('lead_company', ''),
                    'opened': False,
                    'clicked': False,
                    'replied': False,
                    'bounced': False,
                    'sent': True,
                    'sent_at': None,
                    'additional_data': pred_data.get('additional_data')
                })
            
            # Predict
            proba = model.predict_proba(data)
            scores = proba[:, 1]  # Probabilities of reply
            
            # Get model version
            if model_version is None:
                latest = self.model_loader.get_latest_model()
                model_version = latest['version'] if latest else None
            
            # Format results
            results = []
            for i, score in enumerate(scores):
                results.append({
                    'score': float(score),
                    'confidence': abs(score - 0.5) * 2,
                    'prediction': score >= 0.5,
                    'model_version': model_version
                })
            
            return {
                'predictions': results,
                'model_version': model_version or 'unknown',
                'total': len(results)
            }
        except Exception as e:
            logger.error(f"Batch prediction error: {e}")
            raise
    
    async def rank_campaign_leads(
        self,
        campaign_id: UUID,
        user_id: UUID,
        limit: Optional[int] = None,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rank leads in a campaign by reply probability.
        
        Args:
            campaign_id: Campaign ID
            user_id: User ID for authorization
            limit: Maximum number of leads to return
            model_version: Specific model version to use
            
        Returns:
            Dictionary with ranked leads
        """
        try:
            # Get model
            model = self._get_model(model_version)
            
            # Get campaign leads
            stmt = (
                select(CampaignLead)
                .join(Lead)
                .where(
                    and_(
                        CampaignLead.campaign_id == campaign_id,
                        Lead.user_id == user_id
                    )
                )
                .options(selectinload(CampaignLead.lead))
            )
            
            result = await self.db.execute(stmt)
            campaign_leads = result.scalars().all()
            
            if not campaign_leads:
                return {
                    'leads': [],
                    'total': 0,
                    'model_version': model_version or 'unknown'
                }
            
            # Prepare data for prediction
            data = []
            lead_mapping = []
            
            for cl in campaign_leads:
                data.append({
                    'subject': cl.subject or '',
                    'body': cl.body or '',
                    'email': cl.lead.email,
                    'name': cl.lead.name,
                    'company': cl.lead.company,
                    'opened': cl.opened,
                    'clicked': cl.clicked,
                    'replied': cl.replied,
                    'bounced': cl.bounced,
                    'sent': cl.sent,
                    'sent_at': cl.sent_at.isoformat() if cl.sent_at else None,
                    'additional_data': cl.additional_data if hasattr(cl, 'additional_data') else None
                })
                lead_mapping.append({
                    'lead_id': cl.lead_id,
                    'campaign_lead_id': cl.id,
                    'lead_email': cl.lead.email,
                    'lead_name': cl.lead.name
                })
            
            # Predict
            proba = model.predict_proba(data)
            scores = proba[:, 1]
            
            # Combine with lead info and sort by score
            ranked_items = []
            for i, (score, mapping) in enumerate(zip(scores, lead_mapping)):
                ranked_items.append({
                    **mapping,
                    'score': float(score),
                    'confidence': abs(score - 0.5) * 2
                })
            
            # Sort by score (descending)
            ranked_items.sort(key=lambda x: x['score'], reverse=True)
            
            # Apply limit
            if limit:
                ranked_items = ranked_items[:limit]
            
            # Get model version
            if model_version is None:
                latest = self.model_loader.get_latest_model()
                model_version = latest['version'] if latest else None
            
            return {
                'leads': ranked_items,
                'total': len(ranked_items),
                'model_version': model_version or 'unknown'
            }
        except Exception as e:
            logger.error(f"Lead ranking error: {e}")
            raise
    
    async def save_prediction(
        self,
        model_id: UUID,
        lead_id: UUID,
        score: float,
        confidence: Optional[float] = None,
        features: Optional[Dict[str, Any]] = None
    ) -> MLPrediction:
        """
        Save a prediction to the database.
        
        Args:
            model_id: ML model ID
            lead_id: Lead ID
            score: Prediction score
            confidence: Confidence level
            features: Input features used
            
        Returns:
            Created MLPrediction instance
        """
        prediction = MLPrediction(
            model_id=model_id,
            lead_id=lead_id,
            score=score,
            confidence=confidence,
            features=features
        )
        
        self.db.add(prediction)
        await self.db.commit()
        await self.db.refresh(prediction)
        
        return prediction
    
    async def get_active_model(self, user_id: UUID) -> Optional[MLModel]:
        """Get the active ML model for a user."""
        stmt = (
            select(MLModel)
            .where(
                and_(
                    MLModel.user_id == user_id,
                    MLModel.is_active == "active"
                )
            )
            .order_by(desc(MLModel.created_at))
            .limit(1)
        )
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def predict_sent_emails(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        campaign_id: Optional[UUID] = None,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all sent emails with predictions for reply probability.
        
        Args:
            user_id: User ID to filter campaigns/leads
            limit: Maximum number of emails to return
            offset: Offset for pagination
            campaign_id: Optional campaign ID to filter by
            model_version: Specific model version to use
            
        Returns:
            Dictionary with predictions for sent emails
        """
        from src.models.campaign import Campaign
        
        try:
            # Get model
            model = self._get_model(model_version)
            
            # Build query for sent campaign leads
            stmt = (
                select(CampaignLead)
                .join(Lead)
                .join(Campaign)
                .where(
                    and_(
                        Lead.user_id == user_id,
                        CampaignLead.sent == True
                    )
                )
                .options(
                    selectinload(CampaignLead.lead),
                    selectinload(CampaignLead.campaign)
                )
                .order_by(desc(CampaignLead.sent_at))
            )
            
            # Filter by campaign if specified
            if campaign_id:
                stmt = stmt.where(CampaignLead.campaign_id == campaign_id)
            
            # Apply pagination
            stmt = stmt.offset(offset).limit(limit)
            
            result = await self.db.execute(stmt)
            campaign_leads = result.scalars().all()
            
            if not campaign_leads:
                # Get model version for empty response
                if model_version is None:
                    latest = self.model_loader.get_latest_model()
                    model_version = latest['version'] if latest else 'unknown'
                
                return {
                    'predictions': [],
                    'total': 0,
                    'model_version': model_version or 'unknown'
                }
            
            # Prepare data for prediction
            data = []
            for cl in campaign_leads:
                data.append({
                    'subject': cl.subject or '',
                    'body': cl.body or '',
                    'email': cl.lead.email,
                    'name': cl.lead.name,
                    'company': cl.lead.company,
                    'opened': cl.opened,
                    'clicked': cl.clicked,
                    'replied': cl.replied,
                    'bounced': cl.bounced,
                    'sent': cl.sent,
                    'sent_at': cl.sent_at.isoformat() if cl.sent_at else None,
                    'additional_data': cl.lead.additional_data if cl.lead.additional_data else None
                })
            
            # Predict
            proba = model.predict_proba(data)
            scores = proba[:, 1]  # Probability of reply
            
            # Get model version
            if model_version is None:
                latest = self.model_loader.get_latest_model()
                model_version = latest['version'] if latest else 'unknown'
            
            # Build response
            predictions = []
            for i, (cl, score) in enumerate(zip(campaign_leads, scores)):
                predictions.append({
                    'campaign_lead_id': cl.id,
                    'lead_id': cl.lead_id,
                    'lead_name': cl.lead.name,
                    'lead_email': cl.lead.email,
                    'lead_company': cl.lead.company,
                    'campaign_id': cl.campaign_id,
                    'campaign_name': cl.campaign.name,
                    'subject': cl.subject,
                    'body': cl.body,
                    'sent_at': cl.sent_at,
                    'opened': cl.opened,
                    'clicked': cl.clicked,
                    'replied': cl.replied,
                    'bounced': cl.bounced,
                    'reply_probability': float(score),
                    'confidence': abs(float(score) - 0.5) * 2,
                    'prediction': float(score) >= 0.5,
                    'model_version': model_version
                })
            
            return {
                'predictions': predictions,
                'total': len(predictions),
                'model_version': model_version or 'unknown'
            }
        except Exception as e:
            logger.error(f"Sent email prediction error: {e}")
            raise


