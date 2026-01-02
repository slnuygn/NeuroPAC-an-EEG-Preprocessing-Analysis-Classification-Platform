"""
EEG-Inception adapted for Time-Frequency data.
Keeps the multi-scale Inception architecture but tuned for TF spectrograms.
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


def focal_loss(gamma=4.0, alpha=0.5):
    """
    Focal Loss for addressing class imbalance and hard examples.
    Focuses training on hard negatives and misclassified examples.
    
    Parameters
    ----------
    gamma : float
        Focusing parameter (higher = more focus on hard examples)
        gamma=4.0 is very aggressive, strongly focuses on hard examples
    alpha : float
        Balance parameter for class weighting
    """
    def focal_loss_fixed(y_true, y_pred):
        epsilon = 1e-7
        y_pred = tf.clip_by_value(y_pred, epsilon, 1. - epsilon)
        
        # Calculate focal loss - much more aggressive
        ce_loss = -y_true * tf.math.log(y_pred)
        focal_weight = tf.pow(1. - y_pred, gamma)  # gamma=4 = very strong focusing
        focal_loss = alpha * focal_weight * ce_loss
        
        return tf.reduce_mean(tf.reduce_sum(focal_loss, axis=1))
    
    return focal_loss_fixed


def EEGInceptionTF(n_freqs=91, n_times=29, n_channels=12, 
                   n_classes=6, filters_per_branch=8,
                   scales_freq=(3, 5, 9), scales_time=(3, 5, 7),
                   dropout_rate=0.3, activation='elu', 
                   learning_rate=0.001):
    """
    EEG-Inception architecture adapted for Time-Frequency EEG data.
    Balanced for good learning and generalization.
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
    # Use AGGRESSIVE Focal Loss: gamma=4.0, alpha=0.5 - very strong focus on hard examples
    model.compile(optimizer=optimizer,
                  loss=focal_loss(gamma=4.0, alpha=0.5),
                  metrics=['accuracy'],
                  run_eagerly=False)
    
    return model


def EEGInceptionTF_V2(n_freqs=91, n_times=29, n_channels=12, 
                      n_classes=6, dropout_rate=0.25, learning_rate=0.001):
    """
    Simplified but deeper architecture with residual connections.
    Better suited for small datasets.
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
    model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'], run_eagerly=False)
    
    return model


def LightweightTFNet(n_freqs=91, n_times=29, n_channels=12, 
                     n_classes=6, dropout_rate=0.5, learning_rate=0.001):
    """
    Lightweight CNN for Time-Frequency EEG classification.
    
    Parameters
    ----------
    n_times : int
        Number of time points (29 in your data)
    n_channels : int  
        Number of EEG channels (12 in your data)
    n_freqs : int
        Number of frequency bins (91 in your data)
    n_classes : int
        Number of output classes (default: 6 = 2 labels × 3 conditions)
    dropout_rate : float
        Dropout rate for regularization
    learning_rate : float
        Learning rate for Adam optimizer
    
    Returns
    -------
    model : keras.Model
        Compiled Keras model
    """
    
    # Input: (Batch, Freq, Time, Channels) - treat as 2D image
    # Freq = height, Time = width, Channels = depth
    input_layer = Input((n_freqs, n_times, n_channels))
    
    # Block 1: Simple conv to extract features
    x = Conv2D(8, (3, 3), padding='same', kernel_regularizer=l2(0.01))(input_layer)
    x = BatchNormalization()(x)
    x = Activation('relu')(x)
    x = MaxPooling2D((2, 2))(x)  # (45, 14, 8)
    x = Dropout(dropout_rate)(x)
    
    # Block 2
    x = Conv2D(16, (3, 3), padding='same', kernel_regularizer=l2(0.01))(x)
    x = BatchNormalization()(x)
    x = Activation('relu')(x)
    x = MaxPooling2D((2, 2))(x)  # (22, 7, 16)
    x = Dropout(dropout_rate)(x)
    
    # Block 3
    x = Conv2D(32, (3, 3), padding='same', kernel_regularizer=l2(0.01))(x)
    x = BatchNormalization()(x)
    x = Activation('relu')(x)
    x = GlobalAveragePooling2D()(x)  # (32,)
    x = Dropout(dropout_rate)(x)
    
    # Output
    output = Dense(n_classes, activation='softmax')(x)
    
    model = keras.Model(inputs=input_layer, outputs=output)
    
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer,
                  loss='categorical_crossentropy',
                  metrics=['accuracy'],
                  run_eagerly=False)
    
    return model


def SimpleTFNet(input_shape, n_classes=6, dropout_rate=0.5, learning_rate=0.001):
    """
    Even simpler model - just a few dense layers after flattening.
    Good for very small datasets.
    
    Parameters
    ----------
    input_shape : tuple
        Shape of input data (without batch dimension)
    n_classes : int
        Number of output classes (default: 6 = 2 labels × 3 conditions)
    """
    
    input_layer = Input(input_shape)
    
    # Global pooling to reduce dimensions immediately
    if len(input_shape) == 3:
        x = GlobalAveragePooling2D()(input_layer)
    else:
        x = Flatten()(input_layer)
    
    # Small dense layers with AGGRESSIVE regularization
    x = Dense(64, activation='relu', kernel_regularizer=l2(0.005))(x)
    x = Dropout(0.7)(x)  # Increased from 0.5 to 0.7
    x = Dense(32, activation='relu', kernel_regularizer=l2(0.005))(x)
    x = Dropout(0.7)(x)  # Increased from 0.5 to 0.7
    
    output = Dense(n_classes, activation='softmax')(x)
    
    model = keras.Model(inputs=input_layer, outputs=output)
    
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer,
                  loss='categorical_crossentropy', 
                  metrics=['accuracy'],
                  run_eagerly=False)
    
    return model
