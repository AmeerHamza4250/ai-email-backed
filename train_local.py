"""
Local Model Training Script
Trains Logistic Regression + Random Forest ensemble for reply prediction.
No BERT - runs on CPU.

Usage: python train_local.py
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import UUID, uuid4
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix, classification_report
)
import json
import pickle

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_, text
from sqlalchemy.orm import selectinload

from src.database.session import DATABASE_URL, async_engine
from src.models.user import User
from src.models.lead import Lead
from src.models.campaign import Campaign, CampaignStatus
from src.models.campaign_lead import CampaignLead
from src.models.ml_model import MLModel
from src.ml.features.feature_engineering import FeatureEngineer
from src.ml.models.reply_predictor import TFIDFLogisticRegression, RandomForestPredictor

# ============================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================
CSV_PATH = r"c:\Users\hamza\Downloads\Final Email Dataset.csv"
MODEL_NAME = "Reply Predictor (LR + RF)"
OUTPUT_DIR = "models"
# ============================================================


class LocalReplyPredictor:
    """
    Simple ensemble predictor with Logistic Regression + Random Forest.
    No BERT - CPU friendly.
    """
    
    def __init__(self, lr_weight: float = 0.4, rf_weight: float = 0.6):
        self.feature_engineer = FeatureEngineer()
        self.tfidf_lr = TFIDFLogisticRegression()
        self.random_forest = RandomForestPredictor(n_estimators=100, max_depth=20)
        self.lr_weight = lr_weight
        self.rf_weight = rf_weight
        self.is_fitted = False
    
    def fit(self, data: List[Dict[str, Any]], y: np.ndarray):
        """Train both models."""
        print("\n" + "="*60)
        print("TRAINING MODELS")
        print("="*60)
        
        # Fit feature engineer
        print("\n[1/3] Fitting feature engineer (TF-IDF + metadata features)...")
        X_features = self.feature_engineer.fit_transform(data)
        print(f"      Feature matrix shape: {X_features.shape}")
        
        # Train Logistic Regression
        print("\n[2/3] Training TF-IDF + Logistic Regression...")
        self.tfidf_lr.fit(X_features, y)
        print("      [OK] Logistic Regression trained successfully")
        
        # Train Random Forest
        print("\n[3/3] Training Random Forest (100 trees, max_depth=20)...")
        self.random_forest.fit(X_features, y)
        print("      [OK] Random Forest trained successfully")
        
        self.is_fitted = True
        print("\n" + "="*60)
        print("TRAINING COMPLETE!")
        print("="*60)
    
    def predict_proba(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """Predict probabilities using ensemble."""
        if not self.is_fitted:
            raise ValueError("Model not trained. Call fit() first.")
        
        X_features = self.feature_engineer.transform(data)
        
        # Get predictions from both models
        lr_proba = self.tfidf_lr.predict_proba(X_features)
        rf_proba = self.random_forest.predict_proba(X_features)
        
        # Weighted average
        ensemble_proba = (lr_proba * self.lr_weight) + (rf_proba * self.rf_weight)
        
        return ensemble_proba
    
    def predict(self, data: List[Dict[str, Any]], threshold: float = 0.5) -> np.ndarray:
        """Predict binary labels."""
        proba = self.predict_proba(data)
        return (proba[:, 1] >= threshold).astype(int)
    
    def predict_single(self, subject: str, recipient_name: str = "", recipient_email: str = "") -> Dict[str, Any]:
        """
        Predict for a single email.
        Returns probability and prediction.
        """
        data = [{
            'subject': subject,
            'body': '',
            'email': recipient_email,
            'name': recipient_name,
            'company': '',
            'opened': False,
            'clicked': False,
            'replied': False,
            'bounced': False,
            'sent': True,
            'sent_at': None,
            'additional_data': None
        }]
        
        proba = self.predict_proba(data)
        score = float(proba[0][1])
        
        return {
            'subject': subject,
            'reply_probability': round(score * 100, 2),
            'will_reply': score >= 0.5,
            'confidence': round(abs(score - 0.5) * 200, 2)
        }
    
    def save(self, model_dir: str):
        """Save model to disk."""
        os.makedirs(model_dir, exist_ok=True)
        
        # Save feature engineer
        self.feature_engineer.save(os.path.join(model_dir, 'feature_engineer.pkl'))
        
        # Save models
        self.tfidf_lr.save(model_dir)
        self.random_forest.save(model_dir)
        
        # Save metadata
        metadata = {
            'model_type': 'LocalReplyPredictor',
            'lr_weight': self.lr_weight,
            'rf_weight': self.rf_weight,
            'is_fitted': self.is_fitted,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        with open(os.path.join(model_dir, 'model_metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"[SAVED] Model saved to: {model_dir}")
    
    @classmethod
    def load(cls, model_dir: str) -> 'LocalReplyPredictor':
        """Load model from disk."""
        # Load metadata
        with open(os.path.join(model_dir, 'model_metadata.json'), 'r') as f:
            metadata = json.load(f)
        
        instance = cls(
            lr_weight=metadata.get('lr_weight', 0.4),
            rf_weight=metadata.get('rf_weight', 0.6)
        )
        
        # Load feature engineer
        instance.feature_engineer = FeatureEngineer.load(
            os.path.join(model_dir, 'feature_engineer.pkl')
        )
        
        # Load models
        instance.tfidf_lr.load(model_dir)
        instance.random_forest.load(model_dir)
        instance.is_fitted = True
        
        return instance


def load_csv_data(csv_path: str) -> List[Dict[str, Any]]:
    """Load and prepare CSV data for training."""
    print(f"\nLoading CSV from: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} rows")
    print(f"Columns: {list(df.columns)}")
    
    # Prepare data
    data = []
    labels = []
    
    for idx, row in df.iterrows():
        # Skip if sent status is not SENT
        sent_status = str(row.get('Sent_Status', '')).strip().upper()
        if sent_status != 'SENT':
            continue
        
        data_row = {
            'subject': str(row.get('Email_Subject', '')),
            'body': '',  # No body in CSV
            'email': str(row.get('Recipient_Email', '')),
            'name': str(row.get('Recipient_Name', '')),
            'company': '',
            'opened': False,
            'clicked': False,
            'replied': bool(row.get('Reply_Status', False)),
            'bounced': False,
            'sent': True,
            'sent_at': None,
            'additional_data': {
                'email_type': str(row.get('Email_Type', '')),
                'time_to_reply_hours': float(row['Time_to_Reply_Hours']) if pd.notna(row.get('Time_to_Reply_Hours')) else None
            }
        }
        
        data.append(data_row)
        labels.append(1 if row.get('Reply_Status', False) else 0)
    
    labels = np.array(labels)
    
    print(f"\nData Statistics:")
    print(f"  Total samples: {len(data)}")
    print(f"  Replied (positive): {np.sum(labels)} ({np.sum(labels)/len(labels)*100:.1f}%)")
    print(f"  Not replied (negative): {len(labels) - np.sum(labels)} ({(1-np.sum(labels)/len(labels))*100:.1f}%)")
    
    return data, labels


def evaluate_model(model: LocalReplyPredictor, X_test: List[Dict[str, Any]], y_test: np.ndarray) -> Dict[str, Any]:
    """Evaluate model and return metrics."""
    y_pred_proba = model.predict_proba(X_test)
    y_pred = model.predict(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    
    try:
        roc_auc = roc_auc_score(y_test, y_pred_proba[:, 1])
    except:
        roc_auc = 0.0
    
    cm = confusion_matrix(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=['No Reply', 'Reply'])
    
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'roc_auc': roc_auc,
        'confusion_matrix': cm,
        'classification_report': report
    }


def print_metrics(metrics: Dict[str, Any], title: str):
    """Print metrics in a formatted way."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"  Accuracy:  {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)")
    print(f"  Precision: {metrics['precision']:.4f} ({metrics['precision']*100:.2f}%)")
    print(f"  Recall:    {metrics['recall']:.4f} ({metrics['recall']*100:.2f}%)")
    print(f"  F1-Score:  {metrics['f1_score']:.4f} ({metrics['f1_score']*100:.2f}%)")
    print(f"  ROC-AUC:   {metrics['roc_auc']:.4f} ({metrics['roc_auc']*100:.2f}%)")
    print(f"\nConfusion Matrix:")
    print(f"                  Predicted")
    print(f"                No Reply  Reply")
    print(f"  Actual No Reply  {metrics['confusion_matrix'][0][0]:5d}   {metrics['confusion_matrix'][0][1]:5d}")
    print(f"  Actual Reply     {metrics['confusion_matrix'][1][0]:5d}   {metrics['confusion_matrix'][1][1]:5d}")
    print(f"\nClassification Report:")
    print(metrics['classification_report'])


def demo_predictions(model: LocalReplyPredictor):
    """Demo predictions on sample emails."""
    print("\n" + "="*60)
    print("DEMO: PREDICTING NEW EMAILS")
    print("="*60)
    
    test_emails = [
        ("Meeting request for next week", "John Smith", "john@example.com"),
        ("Exclusive offer just for you", "Jane Doe", "jane@marketing.com"),
        ("Quick question regarding Project Alpha", "Bob Wilson", "bob@techcorp.com"),
        ("Follow-up on our recent discussion", "Alice Brown", "alice@company.org"),
        ("Important update: System Change", "Charlie Davis", "charlie@internal.net"),
        ("Can we schedule a call?", "Diana Miller", "diana@business.io"),
        ("Your feedback is needed", "Eve Taylor", "eve@startup.com"),
        ("Re: Previous Email Subject", "Frank Moore", "frank@enterprise.com"),
    ]
    
    print(f"\n{'Subject':<45} {'Probability':<12} {'Will Reply?':<12} {'Confidence'}")
    print("-" * 90)
    
    for subject, name, email in test_emails:
        result = model.predict_single(subject, name, email)
        reply_str = "YES" if result['will_reply'] else "NO"
        print(f"{subject:<45} {result['reply_probability']:>8.1f}%    {reply_str:<12} {result['confidence']:.1f}%")


def main():
    """Main training function."""
    print("\n" + "="*60)
    print("  LOCAL MODEL TRAINING")
    print("  Logistic Regression + Random Forest Ensemble")
    print("="*60)
    print(f"\nCSV Path: {CSV_PATH}")
    print(f"Model Name: {MODEL_NAME}")
    print(f"Output Directory: {OUTPUT_DIR}")
    
    # Check if CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"\n[ERROR] CSV file not found: {CSV_PATH}")
        print("Please update CSV_PATH in this script.")
        sys.exit(1)
    
    # Load data
    print("\n" + "="*60)
    print("STEP 1: LOADING DATA")
    print("="*60)
    data, labels = load_csv_data(CSV_PATH)
    
    # Split data
    print("\n" + "="*60)
    print("STEP 2: SPLITTING DATA")
    print("="*60)
    X_train, X_test, y_train, y_test = train_test_split(
        data, labels, 
        test_size=0.2, 
        random_state=42, 
        stratify=labels
    )
    
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, 
        test_size=0.15, 
        random_state=42, 
        stratify=y_train
    )
    
    print(f"\n  Training set:   {len(X_train)} samples ({len(X_train)/len(data)*100:.1f}%)")
    print(f"  Validation set: {len(X_val)} samples ({len(X_val)/len(data)*100:.1f}%)")
    print(f"  Test set:       {len(X_test)} samples ({len(X_test)/len(data)*100:.1f}%)")
    
    # Initialize and train model
    print("\n" + "="*60)
    print("STEP 3: TRAINING MODEL")
    print("="*60)
    model = LocalReplyPredictor(lr_weight=0.4, rf_weight=0.6)
    model.fit(X_train, y_train)
    
    # Evaluate on validation set
    print("\n" + "="*60)
    print("STEP 4: EVALUATION")
    print("="*60)
    
    val_metrics = evaluate_model(model, X_val, y_val)
    print_metrics(val_metrics, "VALIDATION SET RESULTS")
    
    test_metrics = evaluate_model(model, X_test, y_test)
    print_metrics(test_metrics, "TEST SET RESULTS")
    
    # Save model
    print("\n" + "="*60)
    print("STEP 5: SAVING MODEL")
    print("="*60)
    
    model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = os.path.join(OUTPUT_DIR, model_version)
    os.makedirs(model_dir, exist_ok=True)
    
    model.save(model_dir)
    
    # Save training metadata
    training_metadata = {
        'model_name': MODEL_NAME,
        'model_version': model_version,
        'trained_at': datetime.now(timezone.utc).isoformat(),
        'csv_path': CSV_PATH,
        'total_samples': len(data),
        'training_samples': len(X_train),
        'validation_samples': len(X_val),
        'test_samples': len(X_test),
        'validation_metrics': {k: v.tolist() if isinstance(v, np.ndarray) else v 
                               for k, v in val_metrics.items() if k != 'classification_report'},
        'test_metrics': {k: v.tolist() if isinstance(v, np.ndarray) else v 
                        for k, v in test_metrics.items() if k != 'classification_report'},
        'model_weights': {
            'logistic_regression': model.lr_weight,
            'random_forest': model.rf_weight
        }
    }
    
    with open(os.path.join(model_dir, 'training_metadata.json'), 'w') as f:
        json.dump(training_metadata, f, indent=2)
    
    print(f"\n  Model saved to: {model_dir}")
    print(f"  Files created:")
    for file in os.listdir(model_dir):
        print(f"    - {file}")
    
    # Demo predictions
    demo_predictions(model)
    
    # Summary
    print("\n" + "="*60)
    print("TRAINING SUMMARY")
    print("="*60)
    print(f"\n  Model: {MODEL_NAME}")
    print(f"  Version: {model_version}")
    print(f"  Location: {model_dir}")
    print(f"\n  Final Test Metrics:")
    print(f"    Accuracy:  {test_metrics['accuracy']*100:.2f}%")
    print(f"    Precision: {test_metrics['precision']*100:.2f}%")
    print(f"    Recall:    {test_metrics['recall']*100:.2f}%")
    print(f"    F1-Score:  {test_metrics['f1_score']*100:.2f}%")
    print(f"    ROC-AUC:   {test_metrics['roc_auc']*100:.2f}%")
    
    print("\n" + "="*60)
    print("HOW TO USE THE TRAINED MODEL")
    print("="*60)
    print(f"""
    # Load the model
    from train_local import LocalReplyPredictor
    model = LocalReplyPredictor.load('{model_dir}')
    
    # Predict for a new email
    result = model.predict_single(
        subject="Meeting request for next week",
        recipient_name="John Smith",
        recipient_email="john@example.com"
    )
    
    print(f"Reply Probability: {{result['reply_probability']}}%")
    print(f"Will Reply: {{result['will_reply']}}")
    """)
    
    print("\n[SUCCESS] Training complete!")
    
    return model, model_dir


if __name__ == "__main__":
    model, model_dir = main()




