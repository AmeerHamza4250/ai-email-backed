"""
Feature engineering for reply prediction model.
"""
import re
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
import pickle
import json


class FeatureEngineer:
    """Feature engineering pipeline for email reply prediction."""
    
    def __init__(self, max_features: int = 5000, ngram_range: Tuple[int, int] = (1, 2)):
        """
        Initialize feature engineer.
        
        Args:
            max_features: Maximum number of TF-IDF features
            ngram_range: N-gram range for TF-IDF
        """
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.tfidf_vectorizer = None
        self.scaler = None
        self.is_fitted = False
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text or pd.isna(text):
            return ""
        
        text = str(text).lower()
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_text_features(self, text: str) -> Dict[str, float]:
        """Extract text-based features."""
        if not text or pd.isna(text):
            text = ""
        
        text = str(text)
        words = text.split()
        
        return {
            'text_length': len(text),
            'word_count': len(words),
            'char_count': len(text),
            'avg_word_length': np.mean([len(w) for w in words]) if words else 0,
            'has_question': 1 if '?' in text else 0,
            'has_exclamation': 1 if '!' in text else 0,
            'has_urgent_words': 1 if any(word in text.lower() for word in ['urgent', 'asap', 'immediately', 'important']) else 0,
            'has_greeting': 1 if any(word in text.lower() for word in ['hi', 'hello', 'hey', 'dear']) else 0,
            'has_thanks': 1 if any(word in text.lower() for word in ['thanks', 'thank you', 'appreciate']) else 0,
        }
    
    def _extract_email_domain_features(self, email: str) -> Dict[str, Any]:
        """Extract features from email domain."""
        if not email or pd.isna(email):
            return {
                'domain': 'unknown',
                'is_common_domain': 0,
                'domain_length': 0
            }
        
        email = str(email).lower()
        try:
            domain = email.split('@')[1] if '@' in email else 'unknown'
        except:
            domain = 'unknown'
        
        common_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com']
        
        return {
            'domain': domain,
            'is_common_domain': 1 if domain in common_domains else 0,
            'domain_length': len(domain)
        }
    
    def _extract_metadata_features(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata features from lead and campaign data."""
        features = {}
        
        # Email type (from additional_data)
        additional_data = row.get('additional_data', {})
        if isinstance(additional_data, str):
            try:
                additional_data = json.loads(additional_data)
            except:
                additional_data = {}
        
        email_type = additional_data.get('email_type', '') if additional_data else ''
        email_type_encoded = {
            'Support Query': 1,
            'Internal Memo': 2,
            'Project Update': 3,
            'Marketing Campaign': 4,
            'Sales Pitch': 5
        }.get(email_type, 0)
        
        features['email_type_encoded'] = email_type_encoded
        features['has_email_type'] = 1 if email_type else 0
        
        # NOTE: time_to_reply_hours is NOT used as a feature because it's only
        # available for emails that received replies (data leakage)
        # This would make the model "cheat" by knowing the answer beforehand
        
        # Lead metadata
        company = row.get('company', '')
        features['has_company'] = 1 if company and str(company).strip() else 0
        features['company_length'] = len(str(company)) if company else 0
        
        # Name features
        name = row.get('name', '')
        features['name_length'] = len(str(name)) if name else 0
        features['name_word_count'] = len(str(name).split()) if name else 0
        
        return features
    
    def _extract_interaction_features(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract interaction-based features."""
        features = {
            'opened': 1 if row.get('opened', False) else 0,
            'clicked': 1 if row.get('clicked', False) else 0,
            'bounced': 1 if row.get('bounced', False) else 0,
            'is_sent': 1 if row.get('sent', False) else 0,
        }
        
        # Time-based features (if sent_at available)
        sent_at = row.get('sent_at')
        if sent_at:
            try:
                if isinstance(sent_at, str):
                    from datetime import datetime
                    sent_at = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                
                # Days since sent (if datetime available)
                from datetime import datetime, timezone
                if isinstance(sent_at, datetime):
                    days_since = (datetime.now(timezone.utc) - sent_at).days
                    features['days_since_sent'] = days_since
                else:
                    features['days_since_sent'] = 0
            except:
                features['days_since_sent'] = 0
        else:
            features['days_since_sent'] = 0
        
        return features
    
    def fit(self, data: List[Dict[str, Any]]):
        """
        Fit the feature engineering pipeline on training data.
        
        Args:
            data: List of dictionaries with email/lead data
        """
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(data)
        
        # Prepare text for TF-IDF
        subjects = []
        bodies = []
        
        for row in data:
            subject = self._clean_text(row.get('subject', ''))
            body = self._clean_text(row.get('body', ''))
            subjects.append(subject)
            bodies.append(body)
        
        # Combine subject and body for TF-IDF
        combined_text = [f"{s} {b}" for s, b in zip(subjects, bodies)]
        
        # Fit TF-IDF vectorizer
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            stop_words='english',
            min_df=2,
            max_df=0.95
        )
        
        self.tfidf_vectorizer.fit(combined_text)
        
        # Fit scaler on numeric features (we'll fit it during transform)
        self.scaler = StandardScaler()
        
        # Extract numeric features for scaling
        numeric_features_list = []
        for row in data:
            text_feat = self._extract_text_features(row.get('subject', ''))
            metadata_feat = self._extract_metadata_features(row)
            interaction_feat = self._extract_interaction_features(row)
            
            # Email domain features (must match transform!)
            email = row.get('email', '')
            domain_feat = self._extract_email_domain_features(email)
            domain_feat['domain_hash'] = hash(domain_feat['domain']) % 1000
            
            # Combine all numeric features
            numeric_feat = {
                **text_feat,
                **metadata_feat,
                **interaction_feat,
                'is_common_domain': domain_feat['is_common_domain'],
                'domain_length': domain_feat['domain_length'],
                'domain_hash': domain_feat['domain_hash']
            }
            numeric_features_list.append(list(numeric_feat.values()))
        
        if numeric_features_list:
            numeric_array = np.array(numeric_features_list)
            self.scaler.fit(numeric_array)
        
        self.is_fitted = True
    
    def transform(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """
        Transform data into feature matrix.
        
        Args:
            data: List of dictionaries with email/lead data
            
        Returns:
            Feature matrix (n_samples, n_features)
        """
        if not self.is_fitted:
            raise ValueError("Feature engineer must be fitted before transform. Call fit() first.")
        
        # Prepare text for TF-IDF
        subjects = []
        bodies = []
        
        for row in data:
            subject = self._clean_text(row.get('subject', ''))
            body = self._clean_text(row.get('body', ''))
            subjects.append(subject)
            bodies.append(body)
        
        # Combine subject and body
        combined_text = [f"{s} {b}" for s, b in zip(subjects, bodies)]
        
        # Transform with TF-IDF
        tfidf_features = self.tfidf_vectorizer.transform(combined_text).toarray()
        
        # Extract other features
        numeric_features_list = []
        for row in data:
            # Text features
            text_feat = self._extract_text_features(row.get('subject', ''))
            
            # Metadata features
            metadata_feat = self._extract_metadata_features(row)
            
            # Interaction features
            interaction_feat = self._extract_interaction_features(row)
            
            # Email domain features
            email = row.get('email', '')
            domain_feat = self._extract_email_domain_features(email)
            # Convert domain to numeric (simple hash)
            domain_feat['domain_hash'] = hash(domain_feat['domain']) % 1000
            
            # Combine all numeric features
            numeric_feat = {
                **text_feat,
                **metadata_feat,
                **interaction_feat,
                'is_common_domain': domain_feat['is_common_domain'],
                'domain_length': domain_feat['domain_length'],
                'domain_hash': domain_feat['domain_hash']
            }
            numeric_features_list.append(list(numeric_feat.values()))
        
        # Scale numeric features
        if numeric_features_list:
            numeric_array = np.array(numeric_features_list)
            numeric_scaled = self.scaler.transform(numeric_array)
        else:
            numeric_scaled = np.array([]).reshape(len(data), 0)
        
        # Combine TF-IDF and numeric features
        if numeric_scaled.shape[1] > 0:
            features = np.hstack([tfidf_features, numeric_scaled])
        else:
            features = tfidf_features
        
        return features
    
    def fit_transform(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """Fit and transform in one step."""
        self.fit(data)
        return self.transform(data)
    
    def save(self, filepath: str):
        """Save fitted feature engineer to disk."""
        if not self.is_fitted:
            raise ValueError("Cannot save unfitted feature engineer.")
        
        with open(filepath, 'wb') as f:
            pickle.dump({
                'max_features': self.max_features,
                'ngram_range': self.ngram_range,
                'tfidf_vectorizer': self.tfidf_vectorizer,
                'scaler': self.scaler,
                'is_fitted': self.is_fitted
            }, f)
    
    @classmethod
    def load(cls, filepath: str) -> 'FeatureEngineer':
        """Load fitted feature engineer from disk."""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        instance = cls(
            max_features=data['max_features'],
            ngram_range=data['ngram_range']
        )
        instance.tfidf_vectorizer = data['tfidf_vectorizer']
        instance.scaler = data['scaler']
        instance.is_fitted = data['is_fitted']
        
        return instance




