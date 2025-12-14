"""
ML API routes for predictions and model management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from src.database.session import get_db
from src.api.middleware.auth import get_current_user
from src.models.user import User
from src.schemas.ml import (
    PredictionRequest, PredictionResponse,
    BatchPredictionRequest, BatchPredictionResponse,
    LeadRankingResponse, TrainingRequest, TrainingResponse,
    ModelListResponse, ModelInfoResponse, ModelMetadata,
    SentEmailPrediction, SentEmailPredictionsResponse
)
from src.schemas.common import ApiResponse
from src.services.ml_service import MLService
from src.models.ml_model import MLModel
from src.ml.utils.model_loader import get_model_loader
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/predict", response_model=ApiResponse)
async def predict_reply(
    request: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Predict reply probability for a single lead."""
    try:
        ml_service = MLService(db)
        
        result = await ml_service.predict(
            subject=request.subject,
            body=request.body,
            lead_email=request.lead_email,
            lead_name=request.lead_name,
            lead_company=request.lead_company,
            additional_data=request.additional_data
        )
        
        return ApiResponse(
            status="success",
            message="Prediction completed",
            data=PredictionResponse(**result)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Prediction error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.post("/predict/batch", response_model=ApiResponse)
async def predict_batch(
    request: BatchPredictionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Predict reply probabilities for multiple leads."""
    try:
        ml_service = MLService(db)
        
        # Convert to list of dicts
        predictions_data = [pred.dict() for pred in request.predictions]
        
        result = await ml_service.predict_batch(
            predictions_data=predictions_data,
            model_version=request.model_version
        )
        
        return ApiResponse(
            status="success",
            message=f"Batch prediction completed for {result['total']} leads",
            data=BatchPredictionResponse(**result)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Batch prediction error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {str(e)}"
        )


@router.get("/predict/sent-emails", response_model=ApiResponse)
async def predict_sent_emails(
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    campaign_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all sent emails with ML predictions for reply probability.
    
    This endpoint fetches already sent emails from the database and 
    predicts whether each email will receive a reply.
    """
    try:
        ml_service = MLService(db)
        
        result = await ml_service.predict_sent_emails(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            campaign_id=campaign_id
        )
        
        return ApiResponse(
            status="success",
            message=f"Predictions generated for {result['total']} sent emails",
            data=SentEmailPredictionsResponse(**result)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Sent email prediction error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to predict sent emails: {str(e)}"
        )


@router.get("/campaigns/{campaign_id}/rank", response_model=ApiResponse)
async def rank_campaign_leads(
    campaign_id: UUID,
    limit: Optional[int] = 50,
    model_version: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rank leads in a campaign by reply probability."""
    try:
        ml_service = MLService(db)
        
        result = await ml_service.rank_campaign_leads(
            campaign_id=campaign_id,
            user_id=current_user.id,
            limit=limit,
            model_version=model_version
        )
        
        return ApiResponse(
            status="success",
            message=f"Ranked {result['total']} leads",
            data=LeadRankingResponse(**result)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Lead ranking error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lead ranking failed: {str(e)}"
        )


@router.post("/train", response_model=ApiResponse)
async def trigger_training(
    request: TrainingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger model training (runs in background).
    
    Note: This is a simplified endpoint. In production, you might want to:
    - Use a task queue (Celery, RQ, etc.)
    - Run training in a separate service
    - Provide training status updates via websockets
    """
    try:
        # For now, return a message that training should be done via script
        # In production, you could trigger background training here
        
        return ApiResponse(
            status="success",
            message="Training should be initiated via the training script. See documentation.",
            data=TrainingResponse(
                status="pending",
                message="Use the training script: python -m src.ml.training.train_model --user-id <uuid>"
            )
        )
    except Exception as e:
        logger.exception("Training trigger error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger training: {str(e)}"
        )


@router.get("/models", response_model=ApiResponse)
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all trained models for the current user."""
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        # Get models from database
        stmt = (
            select(MLModel)
            .where(MLModel.user_id == current_user.id)
            .order_by(MLModel.created_at.desc())
        )
        
        result = await db.execute(stmt)
        models = result.scalars().all()
        
        # Also get local models
        model_loader = get_model_loader()
        local_models = model_loader.list_models()
        
        # Combine and format
        model_list = []
        for model in models:
            model_list.append(ModelMetadata(
                id=model.id,
                name=model.name,
                description=model.description,
                model_type=model.model_type,
                accuracy=model.accuracy,
                metrics=model.metrics,
                is_active=model.is_active,
                created_at=model.created_at,
                updated_at=model.updated_at
            ))
        
        return ApiResponse(
            status="success",
            message=f"Found {len(model_list)} models",
            data=ModelListResponse(models=model_list, total=len(model_list))
        )
    except Exception as e:
        logger.exception("List models error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )


@router.get("/models/{model_id}", response_model=ApiResponse)
async def get_model_info(
    model_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific model."""
    try:
        from sqlalchemy import select, and_
        
        stmt = (
            select(MLModel)
            .where(
                and_(
                    MLModel.id == model_id,
                    MLModel.user_id == current_user.id
                )
            )
        )
        
        result = await db.execute(stmt)
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )
        
        # Get local model info if available
        model_loader = get_model_loader()
        local_info = None
        if model.model_path:
            try:
                import os
                version = os.path.basename(model.model_path)
                local_info = model_loader.get_model_info(version)
            except:
                pass
        
        # Combine database and local info
        info = {
            'version': local_info.get('version') if local_info else None,
            'model_name': model.name,
            'trained_at': model.created_at,
            'training_samples': local_info.get('training_samples') if local_info else None,
            'test_accuracy': model.accuracy or (local_info.get('test_metrics', {}).get('accuracy') if local_info else None),
            'test_f1': local_info.get('test_metrics', {}).get('f1_score') if local_info else None,
            'test_roc_auc': local_info.get('test_metrics', {}).get('roc_auc') if local_info else None,
            'validation_metrics': local_info.get('validation_metrics') if local_info else None,
            'test_metrics': local_info.get('test_metrics') if local_info else None,
            'configuration': local_info.get('model_config') if local_info else None
        }
        
        return ApiResponse(
            status="success",
            message="Model information retrieved",
            data=ModelInfoResponse(**{k: v for k, v in info.items() if v is not None})
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Get model info error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model info: {str(e)}"
        )


@router.get("/models/local/info", response_model=ApiResponse)
async def get_local_model_info(
    version: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get information about locally stored models."""
    try:
        model_loader = get_model_loader()
        
        if version:
            info = model_loader.get_model_info(version)
            if not info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Model version not found: {version}"
                )
            return ApiResponse(
                status="success",
                message="Model information retrieved",
                data=ModelInfoResponse(**info)
            )
        else:
            # List all models
            models = model_loader.list_models()
            return ApiResponse(
                status="success",
                message=f"Found {len(models)} local models",
                data={"models": models, "total": len(models)}
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Get local model info error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get local model info: {str(e)}"
        )


