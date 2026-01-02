from tensorflow.keras.layers import Activation, Input, Flatten
from tensorflow.keras.layers import Dropout, BatchNormalization
from tensorflow.keras.layers import Conv2D, AveragePooling2D, DepthwiseConv2D
from tensorflow.keras.layers import Dense
from tensorflow.keras.constraints import max_norm
from tensorflow import keras


def EEGInception(input_time=1000, fs=128, ncha=8, filters_per_branch=8,
                 scales_time=(500, 250, 125), dropout_rate=0.25,
                 activation='elu', n_classes=2, learning_rate=0.001,
                 input_samples=None):
    """Keras implementation of EEG-Inception. All hyperparameters and
    architectural choices are explained in the original article:

    https://doi.org/10.1109/TNSRE.2020.3048106

    Parameters
    ----------
    input_time : int
        EEG epoch time in milliseconds
    fs : int
        Sample rate of the EEG
    ncha :
        Number of input channels
    filters_per_branch : int
        Number of filters in each Inception branch
    scales_time : list
        Temporal scale (ms) of the convolutions on each Inception module.
        This parameter determines the kernel sizes of the filters
    dropout_rate : float
        Dropout rate
    activation : str
        Activation
    n_classes : int
        Number of output classes
    learning_rate : float
        Learning rate
    input_samples : int or None
        If provided, use this as the number of input samples directly,
        bypassing the input_time * fs / 1000 calculation. Useful for
        time-frequency data where the "time" dimension is actually frequency bins.

    Returns
    -------
    model : keras.models.Model
        Keras model already compiled and ready to work

    """

    # ============================= CALCULATIONS ============================= #
    if input_samples is None:
        if input_time is not None and fs is not None:
            input_samples = int(input_time * fs / 1000)
        else:
            raise ValueError("Either input_samples or both input_time and fs must be provided")
    # If input_samples is passed directly, use it as-is
    
    scales_samples = [int(s * fs / 1000) for s in scales_time]

    # ================================ INPUT ================================= #
    input_layer = Input((input_samples, ncha, 1))

    # ========================== BLOCK 1: INCEPTION ========================== #
    b1_units = list()
    for i in range(len(scales_samples)):
        unit = Conv2D(filters=filters_per_branch,
                      kernel_size=(scales_samples[i], 1),
                      kernel_initializer='he_normal',
                      padding='same')(input_layer)
        unit = BatchNormalization()(unit)
        unit = Activation(activation)(unit)
        unit = Dropout(dropout_rate)(unit)

        unit = DepthwiseConv2D((1, ncha),
                               use_bias=False,
                               depth_multiplier=2,
                               depthwise_constraint=max_norm(1.))(unit)
        unit = BatchNormalization()(unit)
        unit = Activation(activation)(unit)
        unit = Dropout(dropout_rate)(unit)

        b1_units.append(unit)

    # Concatenation
    b1_out = keras.layers.concatenate(b1_units, axis=3)
    
    # Adaptive pooling - use smaller pool size for short sequences
    pool1_size = min(4, max(1, input_samples // 8))
    b1_out = AveragePooling2D((pool1_size, 1))(b1_out)

    # ========================== BLOCK 2: INCEPTION ========================== #
    b2_units = list()
    for i in range(len(scales_samples)):
        # Ensure kernel size is at least 1
        kernel_size = max(1, int(scales_samples[i]/4))
        unit = Conv2D(filters=filters_per_branch,
                      kernel_size=(kernel_size, 1),
                      kernel_initializer='he_normal',
                      use_bias=False,
                      padding='same')(b1_out)
        unit = BatchNormalization()(unit)
        unit = Activation(activation)(unit)
        unit = Dropout(dropout_rate)(unit)

        b2_units.append(unit)

    # Concatenate + Average pooling
    b2_out = keras.layers.concatenate(b2_units, axis=3)
    pool2_size = min(2, max(1, input_samples // (pool1_size * 4)))
    b2_out = AveragePooling2D((pool2_size, 1))(b2_out)

    # ============================ BLOCK 3: OUTPUT =========================== #
    # Reduce kernel sizes for short sequences
    kernel3_1 = min(8, max(1, input_samples // (pool1_size * pool2_size * 2)))
    b3_u1 = Conv2D(filters=int(filters_per_branch*len(scales_samples)/2),
                   kernel_size=(kernel3_1, 1),
                   kernel_initializer='he_normal',
                   use_bias=False,
                   padding='same')(b2_out)
    b3_u1 = BatchNormalization()(b3_u1)
    b3_u1 = Activation(activation)(b3_u1)
    # Skip pooling if sequence is too short
    current_size = input_samples // (pool1_size * pool2_size)
    if current_size > 2:
        b3_u1 = AveragePooling2D((2, 1))(b3_u1)
        current_size = current_size // 2
    b3_u1 = Dropout(dropout_rate)(b3_u1)

    kernel3_2 = min(4, max(1, current_size))
    b3_u2 = Conv2D(filters=int(filters_per_branch*len(scales_samples)/4),
                   kernel_size=(kernel3_2, 1),
                   kernel_initializer='he_normal',
                   use_bias=False,
                   padding='same')(b3_u1)
    b3_u2 = BatchNormalization()(b3_u2)
    b3_u2 = Activation(activation)(b3_u2)
    # Skip pooling if sequence is too short
    if current_size > 2:
        b3_u2 = AveragePooling2D((2, 1))(b3_u2)
    b3_out = Dropout(dropout_rate)(b3_u2)

    # Output layer
    output_layer = Flatten()(b3_out)
    output_layer = Dense(n_classes, activation='softmax')(output_layer)

    # ================================ MODEL ================================= #
    model = keras.models.Model(inputs=input_layer, outputs=output_layer)
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate, beta_1=0.9,
                                      beta_2=0.999, amsgrad=False)
    model.compile(loss='binary_crossentropy', optimizer=optimizer,
                  metrics=['accuracy'])
    return model