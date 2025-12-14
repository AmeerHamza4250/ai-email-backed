"""
Ensemble model for reply prediction.
"""
import numpy as np
import pickle
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import os

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

from src.ml.features.feature_engineering import FeatureEngineer


class TFIDFLogisticRegression:
    """TF-IDF + Logistic Regression model wrapper."""
    
    def __init__(self):
        self.model = None
        self.feature_engineer = None
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """Train the model."""
        self.model = LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight='balanced'  # Handle imbalanced data
        )
        self.model.fit(X, y)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities."""
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")
        return self.model.predict_proba(X)
    
    def save(self, model_dir: str):
        """Save model to disk."""
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, 'tfidf_lr_model.pkl'), 'wb') as f:
            pickle.dump(self.model, f)
    
    def load(self, model_dir: str):
        """Load model from disk."""
        model_path = os.path.join(model_dir, 'tfidf_lr_model.pkl')
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)


class RandomForestPredictor:
    """Random Forest model wrapper."""
    
    def __init__(self, n_estimators: int = 100, max_depth: Optional[int] = None):
        self.model = None
        self.n_estimators = n_estimators
        self.max_depth = max_depth
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """Train the model."""
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1
        )
        self.model.fit(X, y)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities."""
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")
        return self.model.predict_proba(X)
    
    def save(self, model_dir: str):
        """Save model to disk."""
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, 'random_forest_model.pkl'), 'wb') as f:
            pickle.dump(self.model, f)
    
    def load(self, model_dir: str):
        """Load model from disk."""
        model_path = os.path.join(model_dir, 'random_forest_model.pkl')
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)


class BERTPredictor:
    """BERT-based model wrapper for semantic understanding."""
    
    def __init__(self, model_name: str = "distilbert-base-uncased"):
        """
        Initialize BERT predictor.
        
        Args:
            model_name: HuggingFace model name (use distilbert for faster inference)
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.is_fitted = False
    
    def _prepare_text(self, data: List[Dict[str, Any]]) -> List[str]:
        """Prepare text from data for BERT."""
        texts = []
        for row in data:
            subject = str(row.get('subject', ''))
            body = str(row.get('body', ''))
            text = f"{subject} {body}".strip()
            texts.append(text if text else "[EMPTY]")
        return texts
    
    def fit(self, data: List[Dict[str, Any]], y: np.ndarray):
        """
        Train BERT model (fine-tuning).
        
        Note: Full BERT fine-tuning is computationally expensive.
        For production, consider using a pre-trained model or feature extraction.
        """
        # For now, we'll use a simpler approach: feature extraction + classifier
        # Full fine-tuning would require more complex training loop
        
        texts = self._prepare_text(data)
        
        # Initialize tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        
        # Use a simpler approach: extract features and train a classifier on top
        # This is more efficient than full fine-tuning
        from transformers import AutoModel
        base_model = AutoModel.from_pretrained(self.model_name)
        base_model.to(self.device)
        base_model.eval()
        
        # Extract BERT features
        features = []
        batch_size = 16
        
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                inputs = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors='pt'
                ).to(self.device)
                
                outputs = base_model(**inputs)
                # Use [CLS] token embedding
                batch_features = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                features.append(batch_features)
        
        features = np.vstack(features)
        
        # Train a simple classifier on BERT features
        from sklearn.linear_model import LogisticRegression
        self.classifier = LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight='balanced'
        )
        self.classifier.fit(features, y)
        
        # Save base model reference
        self.base_model = base_model
        self.is_fitted = True
    
    def predict_proba(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """Predict probabilities using BERT."""
        if not self.is_fitted:
            raise ValueError("Model not trained. Call fit() first.")
        
        texts = self._prepare_text(data)
        
        features = []
        batch_size = 16
        
        self.base_model.eval()
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                inputs = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors='pt'
                ).to(self.device)
                
                outputs = self.base_model(**inputs)
                batch_features = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                features.append(batch_features)
        
        features = np.vstack(features)
        return self.classifier.predict_proba(features)
    
    def save(self, model_dir: str):
        """Save model to disk."""
        os.makedirs(model_dir, exist_ok=True)
        bert_dir = os.path.join(model_dir, 'bert_model')
        os.makedirs(bert_dir, exist_ok=True)
        
        # Save tokenizer
        if self.tokenizer:
            self.tokenizer.save_pretrained(bert_dir)
        
        # Save base model
        if hasattr(self, 'base_model') and self.base_model:
            self.base_model.save_pretrained(bert_dir)
        
        # Save classifier
        if hasattr(self, 'classifier'):
            with open(os.path.join(model_dir, 'bert_classifier.pkl'), 'wb') as f:
                pickle.dump(self.classifier, f)
        
        # Save metadata
        metadata = {
            'model_name': self.model_name,
            'is_fitted': self.is_fitted
        }
        with open(os.path.join(model_dir, 'bert_metadata.json'), 'w') as f:
            json.dump(metadata, f)
    
    def load(self, model_dir: str):
        """Load model from disk."""
        bert_dir = os.path.join(model_dir, 'bert_model')
        
        if not os.path.exists(bert_dir):
            raise FileNotFoundError(f"BERT model directory not found: {bert_dir}")
        
        # Load metadata
        metadata_path = os.path.join(model_dir, 'bert_metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            self.model_name = metadata.get('model_name', 'distilbert-base-uncased')
            self.is_fitted = metadata.get('is_fitted', False)
        
        # Load tokenizer and model
        from transformers import AutoModel
        self.tokenizer = AutoTokenizer.from_pretrained(bert_dir)
        self.base_model = AutoModel.from_pretrained(bert_dir)
        self.base_model.to(self.device)
        self.base_model.eval()
        
        # Load classifier
        classifier_path = os.path.join(model_dir, 'bert_classifier.pkl')
        if os.path.exists(classifier_path):
            with open(classifier_path, 'rb') as f:
                self.classifier = pickle.load(f)


class ReplyPredictor:
    """Ensemble predictor combining TF-IDF+LR, Random Forest, and BERT."""
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        use_bert: bool = True
    ):
        """
        Initialize ensemble predictor.
        
        Args:
            weights: Dictionary with model weights (default: equal weights)
            use_bert: Whether to use BERT (can disable for faster inference)
        """
        self.feature_engineer = FeatureEngineer()
        self.tfidf_lr = TFIDFLogisticRegression()
        self.random_forest = RandomForestPredictor()
        self.bert = BERTPredictor() if use_bert else None
        
        # Default weights (can be adjusted based on validation performance)
        self.weights = weights or {
            'tfidf_lr': 0.3,
            'random_forest': 0.4,
            'bert': 0.3 if use_bert else 0.0
        }
        
        # Normalize weights
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        
        self.is_fitted = False
    
    def fit(
        self,
        data: List[Dict[str, Any]],
        y: np.ndarray,
        use_bert: Optional[bool] = None
    ):
        """
        Train all models in the ensemble.
        
        Args:
            data: List of dictionaries with email/lead data
            y: Target labels (0 or 1)
            use_bert: Override BERT usage (None to use instance default)
        """
        if use_bert is not None:
            self.bert = BERTPredictor() if use_bert else None
        
        # Fit feature engineer
        print("Fitting feature engineer...")
        X_features = self.feature_engineer.fit_transform(data)
        
        # Train TF-IDF + Logistic Regression
        print("Training TF-IDF + Logistic Regression...")
        self.tfidf_lr.fit(X_features, y)
        
        # Train Random Forest
        print("Training Random Forest...")
        self.random_forest.fit(X_features, y)
        
        # Train BERT (if enabled)
        if self.bert:
            print("Training BERT model (this may take a while)...")
            try:
                self.bert.fit(data, y)
            except Exception as e:
                print(f"Warning: BERT training failed: {e}. Continuing without BERT.")
                self.bert = None
                # Adjust weights
                total = self.weights['tfidf_lr'] + self.weights['random_forest']
                if total > 0:
                    self.weights['tfidf_lr'] = self.weights['tfidf_lr'] / total
                    self.weights['random_forest'] = self.weights['random_forest'] / total
                self.weights['bert'] = 0.0
        
        self.is_fitted = True
    
    def predict_proba(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """
        Predict reply probabilities using ensemble.
        
        Args:
            data: List of dictionaries with email/lead data
            
        Returns:
            Array of probabilities (n_samples, 2) - [prob_not_reply, prob_reply]
        """
        if not self.is_fitted:
            raise ValueError("Model not trained. Call fit() first.")
        
        # Transform features
        X_features = self.feature_engineer.transform(data)
        
        # Get predictions from each model
        predictions = []
        weights = []
        
        # TF-IDF + LR
        if self.weights.get('tfidf_lr', 0) > 0:
            proba = self.tfidf_lr.predict_proba(X_features)
            predictions.append(proba)
            weights.append(self.weights['tfidf_lr'])
        
        # Random Forest
        if self.weights.get('random_forest', 0) > 0:
            proba = self.random_forest.predict_proba(X_features)
            predictions.append(proba)
            weights.append(self.weights['random_forest'])
        
        # BERT
        if self.bert and self.weights.get('bert', 0) > 0:
            try:
                proba = self.bert.predict_proba(data)
                predictions.append(proba)
                weights.append(self.weights['bert'])
            except Exception as e:
                print(f"Warning: BERT prediction failed: {e}. Using other models only.")
        
        # Ensemble: weighted average
        if not predictions:
            raise ValueError("No models available for prediction.")
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            weights = [1.0 / len(predictions)] * len(predictions)
        else:
            weights = [w / total_weight for w in weights]
        
        # Weighted average
        ensemble_proba = np.zeros_like(predictions[0])
        for pred, weight in zip(predictions, weights):
            ensemble_proba += pred * weight
        
        return ensemble_proba
    
    def predict(self, data: List[Dict[str, Any]], threshold: float = 0.5) -> np.ndarray:
        """
        Predict binary labels.
        
        Args:
            data: List of dictionaries with email/lead data
            threshold: Probability threshold for positive class
            
        Returns:
            Array of binary predictions (0 or 1)
        """
        proba = self.predict_proba(data)
        return (proba[:, 1] >= threshold).astype(int)
    
    def save(self, model_dir: str):
        """Save entire ensemble to disk."""
        os.makedirs(model_dir, exist_ok=True)
        
        # Save feature engineer
        self.feature_engineer.save(os.path.join(model_dir, 'feature_engineer.pkl'))
        
        # Save individual models
        self.tfidf_lr.save(model_dir)
        self.random_forest.save(model_dir)
        if self.bert:
            self.bert.save(model_dir)
        
        # Save ensemble metadata
        metadata = {
            'weights': self.weights,
            'use_bert': self.bert is not None,
            'is_fitted': self.is_fitted
        }
        with open(os.path.join(model_dir, 'model_metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
    
    @classmethod
    def load(cls, model_dir: str) -> 'ReplyPredictor':
        """Load ensemble from disk."""
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model directory not found: {model_dir}")
        
        # Load metadata
        metadata_path = os.path.join(model_dir, 'model_metadata.json')
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Model metadata not found: {metadata_path}")
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Handle LocalReplyPredictor format (from train_local.py)
        model_type = metadata.get('model_type', '')
        if model_type == 'LocalReplyPredictor' or 'lr_weight' in metadata:
            # Convert LocalReplyPredictor format to ReplyPredictor format
            lr_weight = metadata.get('lr_weight', 0.4)
            rf_weight = metadata.get('rf_weight', 0.6)
            weights = {
                'tfidf_lr': lr_weight,
                'random_forest': rf_weight,
                'bert': 0.0
            }
            use_bert = False
        else:
            # Standard ReplyPredictor format
            weights = metadata.get('weights')
            use_bert = metadata.get('use_bert', True)
        
        # Create instance
        instance = cls(
            weights=weights,
            use_bert=use_bert
        )
        
        # Load feature engineer
        feature_engineer_path = os.path.join(model_dir, 'feature_engineer.pkl')
        if os.path.exists(feature_engineer_path):
            instance.feature_engineer = FeatureEngineer.load(feature_engineer_path)
        
        # Load models
        instance.tfidf_lr.load(model_dir)
        instance.random_forest.load(model_dir)
        
        # Don't load BERT if it wasn't used (LocalReplyPredictor or use_bert=False)
        if use_bert and metadata.get('use_bert', False):
            try:
                instance.bert.load(model_dir)
            except Exception as e:
                print(f"Warning: Could not load BERT model: {e}")
                instance.bert = None
                # Adjust weights
                total = instance.weights['tfidf_lr'] + instance.weights['random_forest']
                if total > 0:
                    instance.weights['tfidf_lr'] = instance.weights['tfidf_lr'] / total
                    instance.weights['random_forest'] = instance.weights['random_forest'] / total
                instance.weights['bert'] = 0.0
        else:
            # No BERT model
            instance.bert = None
        
        instance.is_fitted = metadata.get('is_fitted', False)
        
        return instance




