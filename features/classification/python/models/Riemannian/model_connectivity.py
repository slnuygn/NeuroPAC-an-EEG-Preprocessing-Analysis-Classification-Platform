"""
Riemannian Geometry Model Builder for Connectivity-Based EEG Classification

This module provides a "softer" Riemannian pipeline specifically designed for
connectivity matrices (e.g., coherence, PLV) which may not be strictly positive
definite. Key features:

1. Regularization: Adds small regularization to ensure matrices are SPD
2. Shrinkage estimators: Uses robust covariance estimators
3. Fallback metrics: Uses 'logeuclid' metric which is more stable than 'riemann'
4. Matrix conditioning: Clips eigenvalues to ensure numerical stability
"""

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.base import BaseEstimator, TransformerMixin, ClassifierMixin
from pyriemann.estimation import Covariances
from pyriemann.tangentspace import TangentSpace
from pyriemann.classification import MDM

# Optional TensorFlow backend
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    HAVE_TF = True
except ImportError:
    HAVE_TF = False


class ConnectivityRegularizer(BaseEstimator, TransformerMixin):
    """
    Regularizes connectivity matrices to ensure they are symmetric positive definite.
    
    This transformer:
    1. Ensures symmetry by averaging with transpose
    2. Regularizes the matrix by adding epsilon * I (identity matrix)
    3. Clips eigenvalues to ensure all are positive
    4. Optionally shrinks toward identity matrix for numerical stability
    
    Parameters
    ----------
    reg : float, default=1e-6
        Regularization parameter. Added to diagonal as reg * I.
    shrinkage : float, default=0.01
        Shrinkage toward identity: (1-shrinkage)*M + shrinkage*I
    min_eigenvalue : float, default=1e-7
        Minimum eigenvalue threshold. Eigenvalues below this are clipped.
    ensure_spd : bool, default=True
        If True, reconstructs matrix from eigendecomposition with clipped eigenvalues.
    preserve_scale : bool, default=True
        If True, preserves the original trace/scale of matrices after regularization.
    """
    
    def __init__(self, reg=1e-6, shrinkage=0.01, min_eigenvalue=1e-7, ensure_spd=True, preserve_scale=True):
        self.reg = reg
        self.shrinkage = shrinkage
        self.min_eigenvalue = min_eigenvalue
        self.ensure_spd = ensure_spd
        self.preserve_scale = preserve_scale
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        """
        Transform connectivity matrices to ensure they are SPD.
        
        Parameters
        ----------
        X : ndarray, shape (n_trials, n_channels, n_channels)
            Input connectivity matrices.
        
        Returns
        -------
        X_reg : ndarray, shape (n_trials, n_channels, n_channels)
            Regularized SPD matrices.
        """
        X = np.array(X, dtype=np.float64)
        n_trials, n_channels, n_features = X.shape
        
        # If not square matrices, cannot regularize as SPD
        if n_channels != n_features:
            # Just clean NaN/Inf values
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
            return X
        
        X_reg = np.zeros_like(X)
        identity = np.eye(n_channels, dtype=np.float64)
        
        for i in range(n_trials):
            M = X[i].copy()
            
            # Handle NaN/Inf
            M = np.nan_to_num(M, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Save original trace for scale preservation
            original_trace = np.trace(M) if self.preserve_scale else None
            
            # Ensure symmetry
            M = (M + M.T) / 2.0
            
            # Apply minimal shrinkage toward identity (only if needed)
            if self.shrinkage > 0:
                M = (1 - self.shrinkage) * M + self.shrinkage * identity
            
            # Add small regularization to diagonal
            M = M + self.reg * identity
            
            # Ensure SPD via eigendecomposition
            if self.ensure_spd:
                try:
                    eigenvalues, eigenvectors = np.linalg.eigh(M)
                    # Clip eigenvalues to be at least min_eigenvalue
                    eigenvalues = np.maximum(eigenvalues, self.min_eigenvalue)
                    # Reconstruct matrix
                    M = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
                    # Ensure symmetry after reconstruction
                    M = (M + M.T) / 2.0
                except np.linalg.LinAlgError:
                    # If eigendecomposition fails, fall back to stronger regularization
                    M = X[i].copy()
                    M = np.nan_to_num(M, nan=0.0, posinf=0.0, neginf=0.0)
                    M = (M + M.T) / 2.0
                    # Moderate shrinkage toward identity
                    M = 0.9 * M + 0.1 * identity
            
            # Preserve original scale if requested
            if self.preserve_scale and original_trace is not None and original_trace > 0:
                current_trace = np.trace(M)
                if current_trace > 0:
                    M = M * (original_trace / current_trace)
            
            X_reg[i] = M
        
        return X_reg


class SoftTangentSpace(TangentSpace):
    """
    A softer version of TangentSpace that handles non-SPD matrices more gracefully.
    
    This class wraps TangentSpace and adds:
    1. Pre-regularization of input matrices
    2. Fallback to Euclidean metric if Riemannian fails
    3. Better error handling
    
    Parameters
    ----------
    metric : str, default='logeuclid'
        Metric for mean computation. 'logeuclid' is more stable than 'riemann'.
    tsupdate : bool, default=False
        Whether to update tangent space reference during transform.
    reg : float, default=1e-5
        Regularization added to matrices before tangent space projection.
    """
    
    def __init__(self, metric='logeuclid', tsupdate=False, reg=1e-5):
        super().__init__(metric=metric, tsupdate=tsupdate)
        self.reg = reg
        self._fallback_to_euclid = False
    
    def _regularize(self, X):
        """Add regularization to ensure SPD."""
        X = np.array(X, dtype=np.float64)
        n_trials = X.shape[0]
        n_channels = X.shape[1]
        identity = np.eye(n_channels, dtype=np.float64)
        
        X_reg = np.zeros_like(X)
        for i in range(n_trials):
            M = X[i].copy()
            M = np.nan_to_num(M, nan=0.0, posinf=0.0, neginf=0.0)
            M = (M + M.T) / 2.0
            M = M + self.reg * identity
            X_reg[i] = M
        
        return X_reg
    
    def fit(self, X, y=None, sample_weight=None):
        X_reg = self._regularize(X)
        try:
            super().fit(X_reg, y, sample_weight)
        except ValueError as e:
            if "positive definite" in str(e).lower():
                print(f"Warning: Riemannian metric failed, falling back to 'euclid' metric")
                self._fallback_to_euclid = True
                self.metric = 'euclid'
                super().fit(X_reg, y, sample_weight)
            else:
                raise
        return self
    
    def transform(self, X):
        X_reg = self._regularize(X)
        return super().transform(X_reg)
    
    def fit_transform(self, X, y=None, sample_weight=None):
        self.fit(X, y, sample_weight)
        return self.transform(X)


class ConnectivityVectorizer(BaseEstimator, TransformerMixin):
    """
    Vectorizes connectivity matrices by extracting the upper triangle.
    
    This is a simpler alternative to Riemannian tangent space that directly
    uses connectivity values as features. Since connectivity matrices are
    symmetric, we only need the upper triangle.
    
    Parameters
    ----------
    include_diagonal : bool, default=True
        Whether to include diagonal elements (self-connectivity).
    log_transform : bool, default=False
        Whether to apply log transform to connectivity values.
    epsilon : float, default=1e-8
        Small value added before log transform to avoid log(0).
    """
    
    def __init__(self, include_diagonal=True, log_transform=False, epsilon=1e-8):
        self.include_diagonal = include_diagonal
        self.log_transform = log_transform
        self.epsilon = epsilon
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        """
        Extract upper triangle from connectivity matrices.
        
        Parameters
        ----------
        X : ndarray, shape (n_trials, n_channels, n_channels)
            Input connectivity matrices.
        
        Returns
        -------
        X_vec : ndarray, shape (n_trials, n_features)
            Vectorized upper triangle of each matrix.
        """
        X = np.array(X, dtype=np.float64)
        n_trials, n_channels, _ = X.shape
        
        # Get indices for upper triangle
        k = 0 if self.include_diagonal else 1
        triu_idx = np.triu_indices(n_channels, k=k)
        
        # Extract upper triangle for each sample
        X_vec = np.zeros((n_trials, len(triu_idx[0])), dtype=np.float64)
        for i in range(n_trials):
            vec = X[i][triu_idx]
            # Handle NaN/Inf
            vec = np.nan_to_num(vec, nan=0.0, posinf=1.0, neginf=0.0)
            if self.log_transform:
                vec = np.log(np.abs(vec) + self.epsilon)
            X_vec[i] = vec
        
        return X_vec


class RegularizedCovariances(Covariances):
    """
    Covariance estimator with built-in regularization for connectivity data.
    
    Wraps pyriemann's Covariances and adds post-regularization to ensure
    the resulting matrices are strictly positive definite.
    
    Parameters
    ----------
    estimator : str, default='lwf'
        Covariance estimator. 'lwf' (Ledoit-Wolf) and 'oas' are recommended
        for connectivity data as they include shrinkage.
    reg : float, default=1e-6
        Regularization parameter added to diagonal.
    """
    
    def __init__(self, estimator='lwf', reg=1e-6):
        super().__init__(estimator=estimator)
        self.reg = reg
    
    def transform(self, X):
        covs = super().transform(X)
        n_trials = covs.shape[0]
        n_channels = covs.shape[1]
        identity = np.eye(n_channels, dtype=np.float64)
        
        for i in range(n_trials):
            covs[i] = covs[i] + self.reg * identity
            covs[i] = (covs[i] + covs[i].T) / 2.0
        
        return covs


class ConnectivityTFMLPClassifier(BaseEstimator, ClassifierMixin):
    """
    Keras MLP classifier optimized for connectivity-based features.
    
    Similar to TFMLPClassifier but with additional regularization options
    suitable for the typically smaller feature space of connectivity data.
    """
    
    def __init__(
        self,
        hidden_dims=(64, 32),
        dropout=0.4,
        input_dropout=0.1,
        lr=1e-3,
        max_epochs=100,
        batch_size=32,
        weight_decay=1e-3,
        patience=10,
        n_classes=2,
        train_split=0.1,
        label_smoothing=0.1,
    ):
        self.hidden_dims = hidden_dims
        self.dropout = dropout
        self.input_dropout = input_dropout
        self.lr = lr
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.weight_decay = weight_decay
        self.patience = patience
        self.n_classes = n_classes
        self.train_split = train_split
        self.label_smoothing = label_smoothing
        self.model_ = None
        self.classes_ = None
    
    def _build(self, input_dim):
        reg = keras.regularizers.l2(self.weight_decay) if self.weight_decay else None
        inputs = layers.Input(shape=(input_dim,))
        x = inputs
        
        if self.input_dropout and self.input_dropout > 0:
            x = layers.Dropout(self.input_dropout)(x)
        
        for width in self.hidden_dims:
            x = layers.Dense(width, activation='relu', kernel_regularizer=reg)(x)
            x = layers.BatchNormalization()(x)
            if self.dropout and self.dropout > 0:
                x = layers.Dropout(self.dropout)(x)
        
        outputs = layers.Dense(self.n_classes, activation='softmax')(x)
        model = keras.Model(inputs, outputs)
        
        opt = keras.optimizers.Adam(learning_rate=self.lr)
        callbacks = []
        # Monitor validation loss when a split is provided; otherwise fall back to training loss
        monitor_metric = 'val_loss' if self.train_split and 0 < self.train_split < 1 else 'loss'
        if self.patience and self.patience > 0:
            callbacks.append(keras.callbacks.EarlyStopping(
                patience=self.patience,
                restore_best_weights=True,
                monitor=monitor_metric
            ))
        
        loss_fn = keras.losses.SparseCategoricalCrossentropy()
        model.compile(optimizer=opt, loss=loss_fn, metrics=['accuracy'])
        self._callbacks = callbacks
        return model
    
    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        
        # Store classes for sklearn compatibility
        self.classes_ = np.unique(y)
        
        if self.model_ is None:
            self.model_ = self._build(X.shape[1])
        
        val_split = self.train_split if isinstance(self.train_split, (int, float)) and 0 < self.train_split < 1 else 0.0
        
        self.model_.fit(
            X, y,
            epochs=self.max_epochs,
            batch_size=self.batch_size,
            verbose=0,
            shuffle=True,
            callbacks=self._callbacks if hasattr(self, '_callbacks') else None,
            validation_split=val_split,
        )
        return self
    
    def predict(self, X):
        proba = self.predict_proba(X)
        return self.classes_[proba.argmax(axis=1)]
    
    def predict_proba(self, X):
        X = np.asarray(X, dtype=np.float32)
        preds = self.model_.predict(X, verbose=0)
        return preds


def create_connectivity_pipeline(
    estimator='lwf',
    metric='logeuclid',
    kernel='rbf',
    C=1.0,
    use_mdm=False,
    class_weight='balanced',
    use_deep=True,
    hidden_dims=(64, 32),
    dropout=0.4,
    input_dropout=0.1,
    lr=1e-3,
    max_epochs=100,
    batch_size=32,
    weight_decay=1e-3,
    patience=10,
    n_classes=2,
    train_split=0.1,
    label_smoothing=0.1,
    reg=1e-7,
    shrinkage=0.001,
    min_eigenvalue=1e-8,
    use_vectorized=False,
):
    """
    Create a classification pipeline optimized for connectivity matrices.
    
    This pipeline is specifically designed to handle connectivity matrices (coherence,
    PLV, etc.) which may not be strictly positive definite. It offers two modes:
    
    1. Riemannian mode (default): Uses tangent space projection with minimal regularization
    2. Vectorized mode: Directly uses upper triangle of connectivity matrix as features
    
    Parameters
    ----------
    estimator : str, default='lwf'
        Covariance estimator. 'lwf' (Ledoit-Wolf) recommended for connectivity.
    metric : str, default='logeuclid'
        Riemannian metric. 'logeuclid' is more stable than 'riemann' for
        matrices that may have numerical issues.
    kernel : str, default='rbf'
        SVM kernel when use_deep is False.
    C : float, default=1.0
        SVM regularization parameter.
    use_mdm : bool, default=False
        If True, use Minimum Distance to Mean classifier.
    class_weight : str or dict, default='balanced'
        Class weighting for classifier.
    use_deep : bool, default=True
        If True, use deep learning classifier.
    hidden_dims : tuple, default=(64, 32)
        MLP hidden layer sizes.
    dropout : float, default=0.4
        Dropout rate.
    input_dropout : float, default=0.1
        Input dropout rate.
    lr : float, default=1e-3
        Learning rate.
    max_epochs : int, default=100
        Maximum training epochs.
    batch_size : int, default=32
        Batch size.
    weight_decay : float, default=1e-3
        L2 weight decay.
    patience : int, default=10
        Early stopping patience.
    n_classes : int, default=2
        Number of classes.
    train_split : float, default=0.1
        Validation split ratio.
    label_smoothing : float, default=0.1
        Label smoothing (not used in current implementation).
    reg : float, default=1e-7
        Regularization parameter for SPD enforcement. Keep very small to preserve information.
    shrinkage : float, default=0.001
        Shrinkage toward identity matrix. Keep very small to preserve information.
    min_eigenvalue : float, default=1e-8
        Minimum eigenvalue threshold.
    use_vectorized : bool, default=False
        If True, skip Riemannian processing and use vectorized connectivity features.
    
    Returns
    -------
    sklearn.pipeline.Pipeline
        Configured pipeline ready for fit/predict.
    """
    
    # VECTORIZED MODE: Skip Riemannian, use connectivity values directly
    if use_vectorized:
        vectorizer = ConnectivityVectorizer(include_diagonal=True, log_transform=False)
        
        if use_deep and HAVE_TF:
            tf_head = ConnectivityTFMLPClassifier(
                hidden_dims=hidden_dims,
                dropout=dropout,
                input_dropout=input_dropout,
                lr=lr,
                max_epochs=max_epochs,
                batch_size=batch_size,
                weight_decay=weight_decay,
                patience=patience,
                n_classes=n_classes,
                train_split=train_split,
                label_smoothing=label_smoothing,
            )
            
            pipeline = Pipeline([
                ('vectorizer', vectorizer),
                ('scaler', StandardScaler()),
                ('mlp', tf_head)
            ])
            return pipeline
        
        # Fallback to SVM
        pipeline = Pipeline([
            ('vectorizer', vectorizer),
            ('scaler', StandardScaler()),
            ('svm', SVC(kernel=kernel, C=C, probability=True, class_weight=class_weight))
        ])
        return pipeline
    
    # RIEMANNIAN MODE: Use minimal regularization to preserve information
    # Regularizer to ensure SPD matrices with minimal distortion
    regularizer = ConnectivityRegularizer(
        reg=reg,
        shrinkage=shrinkage,
        min_eigenvalue=min_eigenvalue,
        ensure_spd=True,
        preserve_scale=True
    )
    
    if use_mdm:
        # MDM with regularization
        pipeline = Pipeline([
            ('regularizer', regularizer),
            ('mdm', MDM(metric=metric))
        ])
        return pipeline
    
    # Use soft tangent space for safer projection
    soft_ts = SoftTangentSpace(metric=metric, reg=reg)
    
    if use_deep and HAVE_TF:
        tf_head = ConnectivityTFMLPClassifier(
            hidden_dims=hidden_dims,
            dropout=dropout,
            input_dropout=input_dropout,
            lr=lr,
            max_epochs=max_epochs,
            batch_size=batch_size,
            weight_decay=weight_decay,
            patience=patience,
            n_classes=n_classes,
            train_split=train_split,
            label_smoothing=label_smoothing,
        )
        
        pipeline = Pipeline([
            ('regularizer', regularizer),
            ('ts', soft_ts),
            ('scaler', StandardScaler()),
            ('mlp', tf_head)
        ])
        return pipeline
    
    if use_deep and not HAVE_TF:
        print("Warning: TensorFlow not available; using SVM fallback.")
    
    # Fallback to SVM
    pipeline = Pipeline([
        ('regularizer', regularizer),
        ('ts', soft_ts),
        ('scaler', StandardScaler()),
        ('svm', SVC(kernel=kernel, C=C, probability=True, class_weight=class_weight))
    ])
    return pipeline


def get_connectivity_default_config():
    """
    Default hyperparameters optimized for connectivity-based classification.
    
    These defaults are tuned for connectivity matrices which typically:
    - Are smaller (12x12 channels)
    - Need minimal regularization to preserve discriminative information
    """
    return {
        'estimator': 'lwf',          # Ledoit-Wolf with smart shrinkage
        'metric': 'logeuclid',       # Better for SPD matrices than Euclidean
        'kernel': 'linear',          # Linear SVM is less prone to overfitting
        'C': 0.01,                   # Balanced regularization - allows learning
        'use_mdm': False,
        'use_deep': False,           # Default to SVM to avoid overfitting on small datasets
        'class_weight': 'balanced',
        'enable_grid_search': False,
        'test_size': 0.3,
        'val_split': 0.25,
        'random_state': 42,
        # Deep learning params (only used if use_deep=True)
        'hidden_dims': [24],         # Small network
        'dropout': 0.75,             # High dropout
        'input_dropout': 0.4,        # Drop input features
        'lr': 1e-3,
        'max_epochs': 40,
        'batch_size': 8,
        'weight_decay': 0.05,        # Strong L2 regularization
        'patience': 6,
        'train_split': 0.3,
        'label_smoothing': 0.15,
        # Connectivity-specific regularization - balanced
        'reg': 1e-4,                 # Moderate diagonal regularization
        'shrinkage': 0.08,           # Moderate shrinkage toward identity (8%)
        'min_eigenvalue': 1e-5,      # Stability threshold
        'use_vectorized': True,      # Try vectorized approach
    }


# Convenience function to create pipeline from config dict
def create_pipeline_from_config(config=None):
    """
    Create a connectivity pipeline from a configuration dictionary.
    
    Parameters
    ----------
    config : dict, optional
        Configuration dictionary. If None, uses defaults.
    
    Returns
    -------
    sklearn.pipeline.Pipeline
        Configured pipeline.
    """
    if config is None:
        config = get_connectivity_default_config()
    
    # Merge with defaults
    full_config = get_connectivity_default_config()
    full_config.update(config)
    
    return create_connectivity_pipeline(
        estimator=full_config['estimator'],
        metric=full_config['metric'],
        kernel=full_config['kernel'],
        C=full_config['C'],
        use_mdm=full_config['use_mdm'],
        class_weight=full_config['class_weight'],
        use_deep=full_config['use_deep'],
        hidden_dims=tuple(full_config['hidden_dims']),
        dropout=full_config['dropout'],
        input_dropout=full_config['input_dropout'],
        lr=full_config['lr'],
        max_epochs=full_config['max_epochs'],
        batch_size=full_config['batch_size'],
        weight_decay=full_config['weight_decay'],
        patience=full_config['patience'],
        n_classes=full_config.get('n_classes', 2),
        train_split=full_config['train_split'],
        label_smoothing=full_config['label_smoothing'],
        reg=full_config['reg'],
        shrinkage=full_config['shrinkage'],
        min_eigenvalue=full_config['min_eigenvalue'],
        use_vectorized=full_config.get('use_vectorized', True),
    )
