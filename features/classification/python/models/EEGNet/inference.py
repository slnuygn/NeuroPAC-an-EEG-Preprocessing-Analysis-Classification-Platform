import numpy as np
from tensorflow.keras import backend as K
from .model import EEGNet

# Set image data format to channels_last as required by the model
K.set_image_data_format('channels_last')

class EEGNetInference:
    def __init__(self, weights_path, nb_classes=4, Chans=64, Samples=128, 
                 dropoutRate=0.5, kernLength=64, F1=8, D=2, F2=16, 
                 norm_rate=0.25, dropoutType='Dropout'):
        """
        Initialize the EEGNet model for inference.
        
        Args:
            weights_path (str): Path to the saved model weights (.h5 file)
            nb_classes (int): Number of classes to classify
            Chans (int): Number of channels in the EEG data
            Samples (int): Number of time points in the EEG data
            dropoutRate (float): Dropout fraction
            kernLength (int): Length of temporal convolution in first layer
            F1 (int): Number of temporal filters
            D (int): Number of spatial filters to learn within each temporal convolution
            F2 (int): Number of pointwise filters
            norm_rate (float): Max norm constraint on weights
            dropoutType (str): 'Dropout' or 'SpatialDropout2D'
        """
        self.model = EEGNet(nb_classes=nb_classes, Chans=Chans, Samples=Samples, 
                            dropoutRate=dropoutRate, kernLength=kernLength, 
                            F1=F1, D=D, F2=F2, norm_rate=norm_rate, 
                            dropoutType=dropoutType)
        
        try:
            self.model.load_weights(weights_path)
            print(f"Successfully loaded weights from {weights_path}")
        except Exception as e:
            print(f"Error loading weights from {weights_path}: {e}")
            raise

    def preprocess(self, X, scale_factor=1.0):
        """
        Preprocess data to match model input requirements.
        
        Args:
            X (numpy.ndarray): Input data of shape (trials, channels, samples) or (channels, samples)
            scale_factor (float): Factor to scale the input data (e.g. 1000 to convert V to uV if needed)
            
        Returns:
            numpy.ndarray: Processed data ready for inference (trials, channels, samples, 1)
        """
        # Scale data
        X = X * scale_factor

        # Handle single trial case (channels, samples) -> (1, channels, samples)
        if X.ndim == 2:
            X = X[np.newaxis, ...]
            
        # Reshape to (trials, channels, samples, kernels)
        # Assuming kernels = 1 as in the standard EEGNet implementation
        if X.ndim == 3:
            trials, channels, samples = X.shape
            X = X.reshape(trials, channels, samples, 1)
        
        return X

    def predict(self, X, scale_factor=1.0):
        """
        Perform inference on input data.
        
        Args:
            X (numpy.ndarray): Input EEG data
            scale_factor (float): Scaling factor to apply to data before prediction
            
        Returns:
            tuple: (predictions, probabilities)
                predictions: Class indices
                probabilities: Class probabilities
        """
        X_processed = self.preprocess(X, scale_factor)
        probs = self.model.predict(X_processed)
        preds = probs.argmax(axis=-1)
        return preds, probs
