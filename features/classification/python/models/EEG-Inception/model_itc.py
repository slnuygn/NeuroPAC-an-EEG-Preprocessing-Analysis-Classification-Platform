"""
EEG-Inception adapted for Intertrial Coherence (ITC) data.
Keeps the multi-scale Inception architecture but tuned for ITC spectrograms.
"""

from tensorflow.keras.layers import (
    Input, Conv2D, BatchNormalization, Activation, 
    Dropout, GlobalAveragePooling2D, Dense, Flatten,
    MaxPooling2D, Reshape, AveragePooling2D, DepthwiseConv2D,
    SpatialDropout2D, Add, Concatenate, SeparableConv2D
)
from tensorflow.keras.regularizers import l2
from tensorflow.keras.constraints import max_norm
from tensorflow import keras
import tensorflow as tf
import numpy as np


def calculate_class_weights(y, strategy='balanced', extra_weight_classes=None):
    """
    Calculate class weights to handle imbalance and give extra attention to specific classes.
    
    Parameters
    ----------
    y : np.ndarray
        Class labels (one-hot or integer encoded)
    strategy : str
        'balanced': inverse frequency weighting
        'aggressive': more aggressive weighting for minority classes
    extra_weight_classes : dict, optional
        Dict mapping class indices to extra weight multipliers
        e.g., {3: 2.0} doubles weight for class 3 (PD-target)
    
    Returns
    -------
    dict : mapping class index to weight
    """
    # Convert one-hot to class indices if needed
    if len(y.shape) > 1 and y.shape[1] > 1:
        classes = np.argmax(y, axis=1)
    else:
        classes = y.astype(int).flatten()
    
    n_classes = len(np.unique(classes))
    class_counts = np.bincount(classes, minlength=n_classes)
    
    if strategy == 'balanced':
        # Inverse frequency: weight = total_samples / (n_classes * class_count)
        total = len(classes)
        weights = total / (n_classes * class_counts + 1e-7)
    
    elif strategy == 'aggressive':
        # More aggressive: weight = (total_samples / class_count) ^ 1.5
        total = len(classes)
        weights = (total / (class_counts + 1e-7)) ** 1.5
    
    else:
        # Default to balanced
        total = len(classes)
        weights = total / (n_classes * class_counts + 1e-7)
    
    # Apply extra weights to specific classes
    if extra_weight_classes:
        for class_idx, multiplier in extra_weight_classes.items():
            if class_idx < len(weights):
                weights[class_idx] *= multiplier
    
    # Normalize so mean weight is 1.0
    weights = weights / np.mean(weights)
    
    return {i: float(w) for i, w in enumerate(weights)}


def focal_loss(gamma=4.0, alpha=0.5, class_weights=None):
    """
    Weighted Focal Loss for addressing class imbalance and hard examples.
    Gives extra training attention to specified classes.
    
    Parameters
    ----------
    gamma : float
        Focusing parameter (higher = more focus on hard examples)
        gamma=4.0 is very aggressive, strongly focuses on hard examples
    alpha : float
        Balance parameter for class weighting
    class_weights : dict, optional
        Class-specific weights {class_idx: weight}
    """
    def focal_loss_fixed(y_true, y_pred):
        epsilon = 1e-7
        y_pred = tf.clip_by_value(y_pred, epsilon, 1. - epsilon)
        
        # Calculate focal loss
        ce_loss = -y_true * tf.math.log(y_pred)
        focal_weight = tf.pow(1. - y_pred, gamma)  # gamma=4 = very strong focusing
        focal_loss_val = alpha * focal_weight * ce_loss
        
        # Apply class weights if provided
        if class_weights is not None:
            class_weights_tensor = tf.constant(
                [class_weights.get(i, 1.0) for i in range(len(class_weights))],
                dtype=tf.float32
            )
            # Apply weights: multiply by class weight for true class
            class_weight_per_sample = tf.reduce_sum(y_true * class_weights_tensor, axis=1, keepdims=True)
            focal_loss_val = focal_loss_val * class_weight_per_sample
        
        return tf.reduce_mean(tf.reduce_sum(focal_loss_val, axis=1))
    
    return focal_loss_fixed


def EEGInceptionITC(n_freqs=91, n_times=29, n_channels=12, 
                    n_classes=6, filters_per_branch=8,
                    scales_freq=(3, 5, 9), scales_time=(3, 5, 7),
                    dropout_rate=0.3, activation='elu', 
                    learning_rate=0.001, class_weights=None):
    """
    EEG-Inception architecture adapted for Intertrial Coherence (ITC) data.
    Balanced for good learning and generalization on ITC spectrograms.
    
    Parameters
    ----------
    class_weights : dict, optional
        Class-specific weights {class_idx: weight} for handling imbalance.
        Higher weights give more training attention to specific classes.
        Use calculate_class_weights() to generate automatically.
    """
    
    # Moderate L2 regularization for good generalization
    reg = l2(0.0005)  # Sweet spot between learning and regularization
    
    # Input: (Batch, Freq, Time, Channels)
    input_layer = Input((n_freqs, n_times, n_channels))
    
    # Moderate input dropout
    x = SpatialDropout2D(0.15)(input_layer)  # Increased from 0.1 to 0.15
    
    # Initial channel expansion with 1x1 conv
    x = Conv2D(filters=20, kernel_size=(1, 1), padding='same',
               kernel_initializer='he_normal', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Activation(activation)(x)
    
    # ========================== BLOCK 1: INCEPTION ========================== #
    b1_units = []
    for kf, kt in zip(scales_freq, scales_time):
        unit = SeparableConv2D(filters=12,  # Reduced from 16 to 12
                               kernel_size=(kf, kt),
                               padding='same',
                               depthwise_regularizer=reg,
                               pointwise_regularizer=reg)(x)
        unit = BatchNormalization()(unit)
        unit = Activation(activation)(unit)
        b1_units.append(unit)
    
    b1_out = Concatenate()(b1_units)
    b1_out = SpatialDropout2D(0.2)(b1_out)  # Increased from 0.1 to 0.2
    b1_out = AveragePooling2D((2, 2))(b1_out)
    
    # ========================== BLOCK 2: SIMPLE CONV ======================== #
    x = SeparableConv2D(filters=20,
                        kernel_size=(3, 3),
                        padding='same',
                        depthwise_regularizer=reg,
                        pointwise_regularizer=reg)(b1_out)
    x = BatchNormalization()(x)
    x = Activation(activation)(x)
    x = SpatialDropout2D(0.2)(x)  # Increased from 0.1 to 0.2
    x = AveragePooling2D((2, 2))(x)
    
    # Global pooling
    x = GlobalAveragePooling2D()(x)
    
    # Dense layers - balanced capacity
    x = Dense(128, activation=activation, kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Dropout(0.4)(x)  # Increased from 0.2 to 0.4
    
    x = Dense(64, activation=activation, kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Dropout(0.3)(x)  # Added dropout here too
    
    # Output
    output = Dense(n_classes, activation='softmax')(x)
    
    model = keras.Model(inputs=input_layer, outputs=output)
    
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    # Use AGGRESSIVE Focal Loss with optional class weights
    model.compile(optimizer=optimizer,
                  loss=focal_loss(gamma=4.0, alpha=0.5, class_weights=class_weights),
                  metrics=['accuracy'],
                  run_eagerly=False)
    
    return model


def EEGInceptionITC_V2(n_freqs=91, n_times=29, n_channels=12, 
                       n_classes=6, dropout_rate=0.25, learning_rate=0.001,
                       class_weights=None):
    """
    Simplified but deeper architecture with residual connections.
    Better suited for small datasets with ITC data.
    
    Parameters
    ----------
    class_weights : dict, optional
        Class-specific weights {class_idx: weight} for handling imbalance.
    """
    reg = l2(0.0005)
    
    input_layer = Input((n_freqs, n_times, n_channels))
    
    # Stem
    x = Conv2D(32, (3, 3), padding='same', kernel_regularizer=reg)(input_layer)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = Conv2D(32, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = MaxPooling2D((2, 2))(x)
    x = SpatialDropout2D(dropout_rate)(x)
    
    # Block 1
    shortcut = Conv2D(64, (1, 1), padding='same')(x)
    x = Conv2D(64, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = Conv2D(64, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Add()([x, shortcut])
    x = Activation('elu')(x)
    x = MaxPooling2D((2, 2))(x)
    x = SpatialDropout2D(dropout_rate)(x)
    
    # Block 2
    shortcut = Conv2D(128, (1, 1), padding='same')(x)
    x = Conv2D(128, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = Conv2D(128, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Add()([x, shortcut])
    x = Activation('elu')(x)
    x = SpatialDropout2D(dropout_rate)(x)
    
    # Head
    x = GlobalAveragePooling2D()(x)
    x = Dense(64, activation='elu', kernel_regularizer=reg)(x)
    x = Dropout(dropout_rate)(x)
    output = Dense(n_classes, activation='softmax')(x)
    
    model = keras.Model(inputs=input_layer, outputs=output)
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer, 
                  loss=focal_loss(gamma=4.0, alpha=0.5, class_weights=class_weights),
                  metrics=['accuracy'], 
                  run_eagerly=False)
    
    return model


def LightweightITCNet(n_freqs=91, n_times=29, n_channels=12, 
                      n_classes=6, dropout_rate=0.5, learning_rate=0.001,
                      class_weights=None):
    """
    Lightweight CNN for Intertrial Coherence (ITC) classification.
    
    Parameters
    ----------
    n_freqs : int
        Number of frequency bins (91 in your data)
    n_times : int
        Number of time points (29 in your data)
    n_channels : int  
        Number of EEG channels (12 in your data)
    n_classes : int
        Number of output classes (default: 6 = 2 labels × 3 conditions)
    dropout_rate : float
        Dropout rate for regularization
    learning_rate : float
        Learning rate for Adam optimizer
    class_weights : dict, optional
        Class-specific weights {class_idx: weight} for handling imbalance.
    
    Returns
    -------
    model : keras.models.Model
        Compiled Keras model ready for training
    """
    reg = l2(0.0005)
    
    input_layer = Input((n_freqs, n_times, n_channels))
    
    # Block 1: Initial conv layers
    x = Conv2D(32, (3, 3), padding='same', kernel_regularizer=reg)(input_layer)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = Conv2D(32, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = MaxPooling2D((2, 2))(x)
    x = SpatialDropout2D(dropout_rate * 0.6)(x)
    
    # Block 2: Deeper conv
    x = Conv2D(64, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = Conv2D(64, (3, 3), padding='same', kernel_regularizer=reg)(x)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = MaxPooling2D((2, 2))(x)
    x = SpatialDropout2D(dropout_rate * 0.6)(x)
    
    # Global pooling and dense layers
    x = GlobalAveragePooling2D()(x)
    x = Dense(128, activation='elu', kernel_regularizer=reg)(x)
    x = Dropout(dropout_rate)(x)
    x = Dense(64, activation='elu', kernel_regularizer=reg)(x)
    x = Dropout(dropout_rate * 0.8)(x)
    
    output = Dense(n_classes, activation='softmax')(x)
    
    model = keras.Model(inputs=input_layer, outputs=output)
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer, 
                  loss=focal_loss(gamma=4.0, alpha=0.5, class_weights=class_weights),
                  metrics=['accuracy'], 
                  run_eagerly=False)
    
    return model


def SimpleITCNet(n_freqs=91, n_times=29, n_channels=12, 
                 n_classes=6, dropout_rate=0.5, learning_rate=0.001,
                 class_weights=None):
    """
    Very simple CNN for ITC classification. Baseline model.
    
    Parameters
    ----------
    n_freqs : int
        Number of frequency bins (91 in your data)
    n_times : int
        Number of time points (29 in your data)
    n_channels : int  
        Number of EEG channels (12 in your data)
    n_classes : int
        Number of output classes (default: 6 = 2 labels × 3 conditions)
    dropout_rate : float
        Dropout rate for regularization
    learning_rate : float
        Learning rate for Adam optimizer
    class_weights : dict, optional
        Class-specific weights {class_idx: weight} for handling imbalance.
    
    Returns
    -------
    model : keras.models.Model
        Compiled Keras model ready for training
    """
    reg = l2(0.0005)
    
    input_layer = Input((n_freqs, n_times, n_channels))
    
    # Single simple conv block
    x = Conv2D(32, (3, 3), padding='same', kernel_regularizer=reg)(input_layer)
    x = BatchNormalization()(x)
    x = Activation('elu')(x)
    x = MaxPooling2D((2, 2))(x)
    x = Dropout(dropout_rate)(x)
    
    # Flatten and classify
    x = Flatten()(x)
    x = Dense(64, activation='elu', kernel_regularizer=reg)(x)
    x = Dropout(dropout_rate)(x)
    
    output = Dense(n_classes, activation='softmax')(x)
    
    model = keras.Model(inputs=input_layer, outputs=output)
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer, 
                  loss=focal_loss(gamma=4.0, alpha=0.5, class_weights=class_weights),
                  metrics=['accuracy'], 
                  run_eagerly=False)
    
    return model
