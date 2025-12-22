"""
Riemannian Geometry Model Builder for EEG Classification

This module provides the pipeline construction for Riemannian geometry-based
classification using pyRiemann library with Tangent Space Mapping (TSM).
"""

from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from pyriemann.estimation import Covariances
from pyriemann.tangentmap import TangentSpace
from pyriemann.classification import MDM


def create_riemannian_pipeline(estimator='scm', metric='riemann', 
                                kernel='linear', C=1.0, 
                                use_mdm=False):
    """
    Create a Riemannian geometry classification pipeline.
    
    This implements the Tangent Space Mapping (TSM) architecture from pyRiemann.
    The pipeline: Covariance Estimation -> Tangent Space -> Classifier
    
    Parameters
    ----------
    estimator : str, default='scm'
        Covariance estimator. Options: 'scm', 'lwf', 'oas', 'mcd'
    metric : str, default='riemann'
        Riemannian metric. Options: 'riemann', 'euclid', 'logeuclid'
    kernel : str, default='linear'
        SVM kernel type. Options: 'linear', 'rbf', 'poly'
    C : float, default=1.0
        SVM regularization parameter
    use_mdm : bool, default=False
        If True, use Minimum Distance to Mean (MDM) classifier instead of SVM
        
    Returns
    -------
    pipeline : sklearn.pipeline.Pipeline
        Fitted pipeline ready for training
        
    References
    ----------
    - pyRiemann documentation: https://pyriemann.readthedocs.io/
    - Barachant et al. (2012): "Multiclass Brain-Computer Interface Classification 
      by Riemannian Geometry"
    """
    
    if use_mdm:
        # Alternative: Use Minimum Distance to Mean classifier
        pipeline = Pipeline([
            ('cov', Covariances(estimator=estimator)),
            ('mdm', MDM(metric=metric))
        ])
    else:
        # Standard TSM approach with SVM
        pipeline = Pipeline([
            ('cov', Covariances(estimator=estimator)),        # Sample Covariance Matrix
            ('ts', TangentSpace(metric=metric)),               # Tangent Space Mapping
            ('scaler', StandardScaler()),                      # Normalization for SVM
            ('svm', SVC(kernel=kernel, C=C, probability=True)) # SVM Classifier
        ])
    
    return pipeline


def get_default_config():
    """
    Get default configuration for Riemannian classifier.
    
    Returns
    -------
    config : dict
        Default hyperparameters
    """
    return {
        'estimator': 'scm',
        'metric': 'riemann',
        'kernel': 'linear',
        'C': 1.0,
        'use_mdm': False,
        'test_size': 0.3,
        'random_state': 42
    }
