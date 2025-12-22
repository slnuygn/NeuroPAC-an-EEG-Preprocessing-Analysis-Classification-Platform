import numpy as np
from tensorflow.keras import backend as K
from .model import EEGInception

# Set image data format to channels_last
K.set_image_data_format('channels_last')

class EEGInceptionInference:
    def __init__(self, weights_path, input_time=1000, fs=128, ncha=8, 
                 filters_per_branch=8, scales_time=(500, 250, 125), 
                 dropout_rate=0.25, activation='elu', n_classes=2, 
                 learning_rate=0.001):
        """
        Initialize the EEG-Inception model for inference.
        """
        self.model = EEGInception(input_time=input_time, fs=fs, ncha=ncha,
                                  filters_per_branch=filters_per_branch,
                                  scales_time=scales_time,
                                  dropout_rate=dropout_rate,
                                  activation=activation,
                                  n_classes=n_classes,
                                  learning_rate=learning_rate)
        
        try:
            self.model.load_weights(weights_path)
            print(f"Successfully loaded weights from {weights_path}")
        except Exception as e:
            print(f"Error loading weights from {weights_path}: {e}")
            raise

    def preprocess(self, X, scale_factor=1.0):
        """
        Preprocess data to match model input requirements (Batch, Time, Channels, 1).
        
        Args:
            X (numpy.ndarray): Input data. 
                               Expected shape: (Batch, Channels, Time) or (Channels, Time)
            scale_factor (float): Scaling factor.
            
        Returns:
            numpy.ndarray: Processed data (Batch, Time, Channels, 1)
        """
        X = X * scale_factor

        # Handle single trial (Channels, Time) -> (1, Channels, Time)
        if X.ndim == 2:
            X = X[np.newaxis, ...] 
            
        # Transpose to (Batch, Time, Channels)
        # Input is typically (Batch, Channels, Time) from standard EEG formats
        if X.ndim == 3:
            X = np.transpose(X, (0, 2, 1))
            
        # Add channel dimension -> (Batch, Time, Channels, 1)
        if X.ndim == 3:
            X = X[..., np.newaxis]
        
        return X

    def predict(self, X, scale_factor=1.0):
        """
        Perform inference.
        """
        X_processed = self.preprocess(X, scale_factor)
        probs = self.model.predict(X_processed)
        preds = probs.argmax(axis=-1)
        return preds, probs
