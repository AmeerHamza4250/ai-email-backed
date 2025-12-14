"""
Model loader utility for loading trained models from local storage.
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.ml.models.reply_predictor import ReplyPredictor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ModelLoader:
    """Utility for loading and managing ML models."""
    
    def __init__(self, models_dir: str):
        """
        Initialize model loader.
        
        Args:
            models_dir: Base directory containing model versions (absolute or relative path)
        """
        self.models_dir = Path(models_dir).resolve()  # Resolve to absolute path
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_models: Dict[str, ReplyPredictor] = {}
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available model versions.
        
        Returns:
            List of model metadata dictionaries
        """
        models = []
        
        if not self.models_dir.exists():
            return models
        
        for model_dir in self.models_dir.iterdir():
            if not model_dir.is_dir():
                continue
            
            metadata_path = model_dir / "model_metadata.json"
            if not metadata_path.exists():
                continue
            
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                models.append({
                    'version': model_dir.name,
                    'model_dir': str(model_dir),
                    'trained_at': metadata.get('trained_at'),
                    'model_name': metadata.get('model_name'),
                    'test_accuracy': metadata.get('test_metrics', {}).get('accuracy'),
                    'test_f1': metadata.get('test_metrics', {}).get('f1_score'),
                    'training_samples': metadata.get('training_samples')
                })
            except Exception as e:
                logger.warning(f"Error reading model {model_dir.name}: {e}")
                continue
        
        # Sort by trained_at (newest first), fallback to version name (timestamp format)
        models.sort(key=lambda x: x.get('trained_at') or x.get('version', ''), reverse=True)
        return models
    
    def get_latest_model(self) -> Optional[Dict[str, Any]]:
        """Get the latest model version."""
        models = self.list_models()
        return models[0] if models else None
    
    def load_model(self, version: Optional[str] = None, use_cache: bool = True) -> ReplyPredictor:
        """
        Load a model version.
        
        Args:
            version: Model version (directory name). If None, loads latest.
            use_cache: Whether to use cached model if already loaded
            
        Returns:
            Loaded ReplyPredictor instance
        """
        # Determine version
        if version is None:
            latest = self.get_latest_model()
            if not latest:
                raise ValueError("No models found. Please train a model first.")
            version = latest['version']
        
        # Check cache
        if use_cache and version in self._loaded_models:
            logger.info(f"Using cached model: {version}")
            return self._loaded_models[version]
        
        # Load model
        model_dir = self.models_dir / version
        if not model_dir.exists():
            raise FileNotFoundError(f"Model version not found: {version}")
        
        logger.info(f"Loading model from: {model_dir}")
        
        try:
            model = ReplyPredictor.load(str(model_dir))
            self._loaded_models[version] = model
            logger.info(f"Model loaded successfully: {version}")
            return model
        except Exception as e:
            logger.error(f"Error loading model {version}: {e}")
            raise
    
    def get_model_info(self, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get model metadata without loading the model.
        
        Args:
            version: Model version. If None, returns latest.
            
        Returns:
            Model metadata dictionary
        """
        if version is None:
            latest = self.get_latest_model()
            if not latest:
                return None
            version = latest['version']
        
        model_dir = self.models_dir / version
        metadata_path = model_dir / "model_metadata.json"
        
        if not metadata_path.exists():
            return None
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            return {
                'version': version,
                'model_dir': str(model_dir),
                **metadata
            }
        except Exception as e:
            logger.error(f"Error reading model info {version}: {e}")
            return None
    
    def clear_cache(self, version: Optional[str] = None):
        """
        Clear cached models.
        
        Args:
            version: Specific version to clear. If None, clears all.
        """
        if version:
            self._loaded_models.pop(version, None)
            logger.info(f"Cleared cache for model: {version}")
        else:
            self._loaded_models.clear()
            logger.info("Cleared all model caches")
    
    def validate_model(self, version: Optional[str] = None) -> bool:
        """
        Validate that a model version is complete and loadable.
        
        Args:
            version: Model version. If None, validates latest.
            
        Returns:
            True if model is valid, False otherwise
        """
        try:
            if version is None:
                latest = self.get_latest_model()
                if not latest:
                    return False
                version = latest['version']
            
            model_dir = self.models_dir / version
            
            # Check required files
            required_files = [
                'feature_engineer.pkl',
                'tfidf_lr_model.pkl',
                'random_forest_model.pkl',
                'model_metadata.json'
            ]
            
            for file in required_files:
                if not (model_dir / file).exists():
                    logger.warning(f"Missing required file: {file}")
                    return False
            
            # Try loading
            model = self.load_model(version, use_cache=False)
            if model is None or not model.is_fitted:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Model validation failed: {e}")
            return False


# Global model loader instance
_model_loader: Optional[ModelLoader] = None


def _get_default_models_dir() -> str:
    """
    Get the default models directory path.
    
    Models are stored in: backend/models/ (relative to backend directory)
    This is separate from backend/src/models/ which contains database ORM models.
    
    Path structure:
    - backend/src/ml/utils/model_loader.py (this file)
    - backend/models/ (ML trained models - pickle files)
    - backend/src/models/ (database ORM models - Python classes)
    """
    # Get the backend directory
    # Path: backend/src/ml/utils/model_loader.py
    # We need to go up 4 levels: utils -> ml -> src -> backend
    current_file = Path(__file__).resolve()
    backend_dir = current_file.parent.parent.parent.parent  # utils -> ml -> src -> backend
    
    # Models directory is at: backend/models/
    models_path = backend_dir / "models"
    
    # Resolve to absolute path and log
    models_path_abs = models_path.resolve()
    logger.info(f"Models directory: {models_path_abs}")
    
    if not models_path_abs.exists():
        logger.warning(f"Models directory does not exist, will create: {models_path_abs}")
    
    return str(models_path_abs)


def get_model_loader(models_dir: Optional[str] = None) -> ModelLoader:
    """
    Get or create global model loader instance.
    
    Args:
        models_dir: Optional path to models directory. If None, uses default location
                    at backend/models/ (relative to backend directory)
    
    Returns:
        ModelLoader instance
    """
    global _model_loader
    if _model_loader is None:
        if models_dir is None:
            models_dir = _get_default_models_dir()
        logger.info(f"Initializing ModelLoader with directory: {models_dir}")
        _model_loader = ModelLoader(models_dir)
        # Log available models
        models = _model_loader.list_models()
        if models:
            logger.info(f"Found {len(models)} trained model(s): {[m['version'] for m in models]}")
            logger.info(f"Latest model: {models[0]['version']}")
        else:
            logger.warning("No trained models found in models directory")
    return _model_loader


def reset_model_loader():
    """Reset the global model loader (useful for testing or reloading)."""
    global _model_loader
    _model_loader = None
    logger.info("Model loader cache reset")


