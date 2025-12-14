"""
Model training script for Google Colab.

This script can be run in Colab cells to train the reply prediction model.

Usage in Colab:
    # Install dependencies
    !pip install pandas numpy scikit-learn transformers torch sqlalchemy asyncpg psycopg-binary
    
    # Set environment variables
    import os
    os.environ['DATABASE_URL'] = 'your-database-url'
    
    # Run training
    !python -m src.ml.training.train_model --user-id <uuid>
"""
import asyncio
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import UUID
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix, classification_report
)
import json
import zipfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from src.database.session import DATABASE_URL, async_engine
from src.models.campaign_lead import CampaignLead
from src.models.lead import Lead
from src.models.email_event import EmailEvent
from src.models.ml_model import MLModel
from src.ml.models.reply_predictor import ReplyPredictor
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def extract_training_data(
    session: AsyncSession,
    user_id: UUID,
    min_samples: int = 50
) -> tuple[List[Dict[str, Any]], np.ndarray]:
    """
    Extract training data from database.
    
    Args:
        session: Database session
        user_id: User ID to filter data
        min_samples: Minimum number of samples required
        
    Returns:
        Tuple of (data_list, labels_array)
    """
    # Query CampaignLeads with sent emails
    stmt = (
        select(CampaignLead)
        .join(Lead)
        .where(
            and_(
                Lead.user_id == user_id,
                CampaignLead.sent == True,
                CampaignLead.sent_at.isnot(None)
            )
        )
        .options(selectinload(CampaignLead.lead))
    )
    
    result = await session.execute(stmt)
    campaign_leads = result.scalars().all()
    
    if len(campaign_leads) < min_samples:
        raise ValueError(
            f"Insufficient training data: {len(campaign_leads)} samples. "
            f"Minimum required: {min_samples}. Please import more data."
        )
    
    data = []
    labels = []
    
    for cl in campaign_leads:
        # Extract features
        row = {
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
        }
        
        data.append(row)
        labels.append(1 if cl.replied else 0)
    
    labels = np.array(labels)
    
    logger.info(f"Extracted {len(data)} training samples")
    logger.info(f"  Replied: {np.sum(labels)} ({np.sum(labels)/len(labels)*100:.1f}%)")
    logger.info(f"  Not replied: {len(labels) - np.sum(labels)} ({(1-np.sum(labels)/len(labels))*100:.1f}%)")
    
    return data, labels


def evaluate_model(
    model: ReplyPredictor,
    X_test: List[Dict[str, Any]],
    y_test: np.ndarray
) -> Dict[str, Any]:
    """Evaluate model performance."""
    # Predictions
    y_pred_proba = model.predict_proba(X_test)
    y_pred = model.predict(X_test)
    
    # Metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    
    # ROC-AUC
    try:
        roc_auc = roc_auc_score(y_test, y_pred_proba[:, 1])
    except:
        roc_auc = 0.0
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    
    # Classification report
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    
    metrics = {
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'roc_auc': float(roc_auc),
        'confusion_matrix': cm.tolist(),
        'classification_report': report
    }
    
    return metrics


async def train_model(
    user_id: UUID,
    model_name: str = "Reply Predictor",
    use_bert: bool = True,
    test_size: float = 0.15,
    val_size: float = 0.15,
    output_dir: str = "models"
) -> Dict[str, Any]:
    """
    Train the reply prediction model.
    
    Args:
        user_id: User ID for data filtering
        model_name: Name for the model
        use_bert: Whether to use BERT (can disable for faster training)
        test_size: Proportion of data for testing
        val_size: Proportion of data for validation
        output_dir: Directory to save models
        
    Returns:
        Dictionary with training results and metrics
    """
    # Create async session
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Extract training data
        print("Extracting training data from database...")
        data, labels = await extract_training_data(session, user_id)
        
        # Split data
        print(f"Splitting data (train: {1-test_size-val_size:.0%}, val: {val_size:.0%}, test: {test_size:.0%})...")
        X_temp, X_test, y_temp, y_test = train_test_split(
            data, labels, test_size=test_size, random_state=42, stratify=labels
        )
        
        val_size_adjusted = val_size / (1 - test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=val_size_adjusted, random_state=42, stratify=y_temp
        )
        
        print(f"Training set: {len(X_train)} samples")
        print(f"Validation set: {len(X_val)} samples")
        print(f"Test set: {len(X_test)} samples")
        
        # Initialize model
        print("\nInitializing model...")
        model = ReplyPredictor(use_bert=use_bert)
        
        # Train model
        print("\nTraining model...")
        model.fit(X_train, y_train, use_bert=use_bert)
        
        # Evaluate on validation set
        print("\nEvaluating on validation set...")
        val_metrics = evaluate_model(model, X_val, y_val)
        print(f"Validation Accuracy: {val_metrics['accuracy']:.4f}")
        print(f"Validation F1: {val_metrics['f1_score']:.4f}")
        print(f"Validation ROC-AUC: {val_metrics['roc_auc']:.4f}")
        
        # Evaluate on test set
        print("\nEvaluating on test set...")
        test_metrics = evaluate_model(model, X_test, y_test)
        print(f"Test Accuracy: {test_metrics['accuracy']:.4f}")
        print(f"Test F1: {test_metrics['f1_score']:.4f}")
        print(f"Test ROC-AUC: {test_metrics['roc_auc']:.4f}")
        
        # Create model version
        model_version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_dir = os.path.join(output_dir, model_version)
        os.makedirs(model_dir, exist_ok=True)
        
        # Save model
        print(f"\nSaving model to {model_dir}...")
        model.save(model_dir)
        
        # Save training metadata
        metadata = {
            'model_name': model_name,
            'version': model_version,
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'user_id': str(user_id),
            'training_samples': len(X_train),
            'validation_samples': len(X_val),
            'test_samples': len(X_test),
            'validation_metrics': val_metrics,
            'test_metrics': test_metrics,
            'model_config': {
                'use_bert': use_bert,
                'weights': model.weights
            }
        }
        
        metadata_path = os.path.join(model_dir, 'model_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Create zip file for download
        zip_path = f"{output_dir}/model_{model_version}.zip"
        print(f"\nCreating zip file: {zip_path}...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(model_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, model_dir)
                    zipf.write(file_path, arcname)
        
        print(f"\nModel saved successfully!")
        print(f"  Model directory: {model_dir}")
        print(f"  Zip file: {zip_path}")
        print(f"\nTest Metrics:")
        print(f"  Accuracy: {test_metrics['accuracy']:.4f}")
        print(f"  Precision: {test_metrics['precision']:.4f}")
        print(f"  Recall: {test_metrics['recall']:.4f}")
        print(f"  F1-Score: {test_metrics['f1_score']:.4f}")
        print(f"  ROC-AUC: {test_metrics['roc_auc']:.4f}")
        
        # Save model record to database
        try:
            ml_model = MLModel(
                user_id=user_id,
                name=model_name,
                description=f"Reply prediction model trained on {len(X_train)} samples",
                model_type="reply_prediction",
                model_path=model_dir,
                metrics=test_metrics,
                accuracy=test_metrics['accuracy'],
                is_active="active"
            )
            session.add(ml_model)
            await session.commit()
            await session.refresh(ml_model)
            print(f"\nModel record saved to database: {ml_model.id}")
        except Exception as e:
            print(f"\nWarning: Could not save model record to database: {e}")
        
        return {
            'model_version': model_version,
            'model_dir': model_dir,
            'zip_path': zip_path,
            'validation_metrics': val_metrics,
            'test_metrics': test_metrics,
            'metadata': metadata
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Train reply prediction model')
    parser.add_argument('--user-id', required=True, type=UUID, help='User ID (UUID)')
    parser.add_argument('--model-name', default='Reply Predictor', help='Model name')
    parser.add_argument('--use-bert', action='store_true', default=True, help='Use BERT model')
    parser.add_argument('--no-bert', dest='use_bert', action='store_false', help='Disable BERT (faster training)')
    parser.add_argument('--output-dir', default='models', help='Output directory for models')
    parser.add_argument('--test-size', type=float, default=0.15, help='Test set size (0-1)')
    parser.add_argument('--val-size', type=float, default=0.15, help='Validation set size (0-1)')
    
    args = parser.parse_args()
    
    try:
        results = await train_model(
            user_id=args.user_id,
            model_name=args.model_name,
            use_bert=args.use_bert,
            test_size=args.test_size,
            val_size=args.val_size,
            output_dir=args.output_dir
        )
        
        print("\n" + "="*50)
        print("TRAINING COMPLETE")
        print("="*50)
        print(f"Model version: {results['model_version']}")
        print(f"Zip file ready for download: {results['zip_path']}")
        
    except Exception as e:
        print(f"\nError: {e}")
        logger.exception("Training failed", exc_info=e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())




