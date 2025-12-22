"""
Riemannian Geometry Model Inference

This module provides inference capabilities for trained Riemannian models.
"""

import numpy as np
import joblib
import os


class RiemannianInference:
    """
    Inference class for Riemannian geometry-based EEG classifier.
    
    This class loads a pre-trained pyRiemann pipeline and provides
    prediction capabilities for new EEG data.
    """
    
    def __init__(self, weights_path):
        """
        Initialize the Riemannian inference model.
        
        Parameters
        ----------
        weights_path : str
            Path to the saved pipeline (.pkl file)
        """
        self.pipeline = None
        self.weights_path = weights_path
        
        if not os.path.exists(weights_path):
            raise FileNotFoundError(f"Model weights not found at: {weights_path}")
        
        try:
            self.pipeline = joblib.load(weights_path)
            print(f"Successfully loaded model from {weights_path}")
        except Exception as e:
            print(f"Error loading model from {weights_path}: {e}")
            raise
    
    def preprocess(self, X):
        """
        Preprocess input data for Riemannian inference.
        
        The pyRiemann pipeline expects (n_trials, n_channels, n_features) format.
        For spectral data: (n_trials, 12, 15)
        For connectivity data: (n_trials, 12, 12)
        
        Parameters
        ----------
        X : numpy.ndarray
            Input data. Expected shape: (n_trials, n_channels, n_features)
            
        Returns
        -------
        X : numpy.ndarray
            Preprocessed data ready for the pipeline
        """
        # Ensure 3D array
        if X.ndim == 2:
            X = X[np.newaxis, ...]
            
        return X
    
    def predict(self, X):
        """
        Predict class labels for input data.
        
        Parameters
        ----------
        X : numpy.ndarray
            Input data (n_trials, n_channels, n_features)
            
        Returns
        -------
        predictions : numpy.ndarray
            Predicted class labels
        proba : numpy.ndarray
            Class probabilities (if available)
        """
        if self.pipeline is None:
            raise RuntimeError("Model not loaded. Initialize with valid weights_path.")
        
        X_processed = self.preprocess(X)
        
        # Predict
        predictions = self.pipeline.predict(X_processed)
        
        # Get probabilities if available
        try:
            proba = self.pipeline.predict_proba(X_processed)
        except AttributeError:
            # MDM classifier doesn't have predict_proba
            proba = None
            
        return predictions, proba
    
    def predict_proba(self, X):
        """
        Predict class probabilities for input data.
        
        Parameters
        ----------
        X : numpy.ndarray
            Input data (n_trials, n_channels, n_features)
            
        Returns
        -------
        proba : numpy.ndarray
            Class probabilities
        """
        if self.pipeline is None:
            raise RuntimeError("Model not loaded. Initialize with valid weights_path.")
        
        X_processed = self.preprocess(X)
        
        try:
            proba = self.pipeline.predict_proba(X_processed)
            return proba
        except AttributeError:
            raise NotImplementedError(
                "This pipeline does not support probability predictions. "
                "Use predict() instead."
            )
    
    def get_pipeline_steps(self):
        """
        Get information about pipeline steps.
        
        Returns
        -------
        steps : list
            List of (name, transformer) tuples
        """
        if self.pipeline is None:
            raise RuntimeError("Model not loaded.")
        
        return self.pipeline.steps
    
    def get_feature_importance(self):
        """
        Get feature importance from SVM classifier (if available).
        
        Returns
        -------
        coef : numpy.ndarray
            SVM coefficients (for linear kernel)
        """
        if self.pipeline is None:
            raise RuntimeError("Model not loaded.")
        
        # Check if SVM is in the pipeline
        if hasattr(self.pipeline.named_steps, 'svm'):
            svm = self.pipeline.named_steps['svm']
            if hasattr(svm, 'coef_'):
                return svm.coef_
        
        return None
