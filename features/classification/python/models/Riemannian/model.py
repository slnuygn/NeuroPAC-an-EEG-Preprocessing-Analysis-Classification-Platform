"""
Riemannian Geometry Model Builder for EEG Classification (Deep Learning)

This module creates pipelines that map EEG trials to the Riemannian tangent
space and feeds them to either a classical classifier (SVM/MDM) or a
TensorFlow-based multilayer perceptron for deep learning (no scikeras needed).
"""

from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from pyriemann.estimation import Covariances
from pyriemann.tangentspace import TangentSpace
from pyriemann.classification import MDM
from sklearn.base import BaseEstimator, ClassifierMixin
import numpy as np

# Optional TensorFlow backend (no scikeras dependency)
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers

    HAVE_TF = True
except ImportError:
    HAVE_TF = False


class TFMLPClassifier(BaseEstimator, ClassifierMixin):
    """Keras MLP head compatible with sklearn API (defined at module scope for pickling)."""

    def __init__(
        self,
        hidden_dims,
        dropout,
        input_dropout,
        lr,
        max_epochs,
        batch_size,
        weight_decay,
        patience,
        n_classes,
        train_split,
        label_smoothing,
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
        monitor_metric = 'val_loss' if self.train_split and 0 < self.train_split < 1 else 'loss'
        if self.patience and self.patience > 0:
            callbacks.append(keras.callbacks.EarlyStopping(
                patience=self.patience,
                restore_best_weights=True,
                monitor=monitor_metric
            ))
        # Use sparse loss without label_smoothing to avoid TF version issues
        loss_fn = keras.losses.SparseCategoricalCrossentropy()
        model.compile(optimizer=opt, loss=loss_fn, metrics=['accuracy'])
        self._callbacks = callbacks
        return model

    def fit(self, X, y):
        X = np.asarray(X)
        y = np.asarray(y)
        if self.model_ is None:
            self.model_ = self._build(X.shape[1])
        val_split = self.train_split if isinstance(self.train_split, (int, float)) and 0 < self.train_split < 1 else 0.0
        self.model_.fit(
            X,
            y,
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
        return proba.argmax(axis=1)

    def predict_proba(self, X):
        X = np.asarray(X)
        preds = self.model_.predict(X, verbose=0)
        return preds


def create_riemannian_pipeline(
    estimator='scm',
    metric='riemann',
    kernel='linear',
    C=1.0,
    use_mdm=False,
    class_weight=None,
    use_deep=True,
    hidden_dims=(128, 64),
    dropout=0.3,
    lr=1e-3,
    max_epochs=50,
    batch_size=64,
    weight_decay=1e-4,
    patience=0,
    n_classes=6,
    train_split=None,
    input_dropout=0.0,
    label_smoothing=0.0,
):
    """
    Create a Riemannian classification pipeline.

    Steps: Covariance Estimation -> Tangent Space -> (Scaler) -> Classifier

    Parameters
    ----------
    estimator : str
        Covariance estimator: 'scm', 'lwf', 'oas', 'mcd'.
    metric : str
        Riemannian metric: 'riemann', 'euclid', 'logeuclid'.
    kernel : str
        SVM kernel when use_deep is False and use_mdm is False.
    C : float
        SVM regularization strength.
    use_mdm : bool
        If True, use Minimum Distance to Mean classifier.
    class_weight : dict or str or None
        Passed to SVM when applicable.
    use_deep : bool
        If True (default), use a torch MLP on tangent features via skorch.
    hidden_dims : tuple[int]
        MLP hidden layer sizes.
    dropout : float
        Dropout rate between hidden layers.
    lr : float
        Learning rate for Adam optimizer.
    max_epochs : int
        Training epochs for the deep model.
    batch_size : int
        Batch size for the deep model.
    weight_decay : float
        L2 weight decay for the deep model.
    patience : int
        Early-stopping patience (0 disables early stopping).
    device : str
        'cpu' or 'cuda' for torch backend.
    n_classes : int
        Number of target classes (needed for the MLP head).
    train_split : float or None
        Optional internal validation split for skorch (e.g., 0.1). None trains on all data.

    Returns
    -------
    sklearn.pipeline.Pipeline
        Configured pipeline ready for fit/predict.
    """

    if use_mdm:
        pipeline = Pipeline([
            ('cov', Covariances(estimator=estimator)),
            ('mdm', MDM(metric=metric))
        ])
        return pipeline

    if use_deep and HAVE_TF:
        tf_head = TFMLPClassifier(
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
            ('cov', Covariances(estimator=estimator)),
            ('ts', TangentSpace(metric=metric)),
            ('scaler', StandardScaler()),
            ('mlp', tf_head)
        ])
        return pipeline

    if use_deep and not HAVE_TF:
        print("Warning: TensorFlow not available; using SVM fallback.")

    # Fallback to classical SVM when deep backend is disabled or unavailable
    pipeline = Pipeline([
        ('cov', Covariances(estimator=estimator)),
        ('ts', TangentSpace(metric=metric)),
        ('scaler', StandardScaler()),
        ('svm', SVC(kernel=kernel, C=C, probability=True, class_weight=class_weight))
    ])
    return pipeline


def get_default_config():
    """Default hyperparameters for the Riemannian classifier."""
    return {
        'estimator': 'oas',
        'metric': 'riemann',
        'kernel': 'linear',
        'C': 0.05,
        'use_mdm': False,
        'use_deep': True,
        'class_weight': 'balanced',
        'enable_grid_search': False,
        'test_size': 0.8,
        'val_split': 0.6,
        'random_state': 42,
        'hidden_dims': [64, 32],
        'dropout': 0.65,
        'input_dropout': 0.2,
        'lr': 3e-4,
        'max_epochs': 50,
        'batch_size': 128,
        'weight_decay': 0.001,
        'patience': 7,
        'train_split': 0.25,
        'label_smoothing': 0.1
    }
