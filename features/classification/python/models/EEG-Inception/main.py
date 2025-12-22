import os
import sys
import json
import numpy as np
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
from tensorflow.keras import backend as K

# -----------------------------------------------------------------------------
# Path Setup
# -----------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
python_root = os.path.abspath(os.path.join(current_dir, "../../"))

if python_root not in sys.path:
    sys.path.append(python_root)

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
try:
    from core.preprocess_bridge import PreprocessBridge
except ImportError as e:
    print(f"Error importing PreprocessBridge: {e}")
    sys.exit(1)

try:
    from .model import EEGInception
except ImportError:
    from model import EEGInception

# Set image data format to channels_last
K.set_image_data_format('channels_last')

def load_config(config_path):
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def main():
    # -------------------------------------------------------------------------
    # 1. Configuration
    # -------------------------------------------------------------------------
    data_folder = os.path.join(python_root, "data")
    
    # Determine which config to use. 
    # You can change this variable or pass it as an argument.
    # Options: 'erp', 'tf', 'it'
    analysis_mode = 'erp' 
    if len(sys.argv) > 1:
        analysis_mode = sys.argv[1]

    config_file = f"{analysis_mode}_config.json"
    config_path = os.path.join(current_dir, "configs", config_file)
    
    if not os.path.exists(config_path):
        print(f"Error: Config file {config_path} not found.")
        return

    print(f"Using configuration: {config_file}")
    config = load_config(config_path)
    
    # Defaults
    batch_size = config.get('batch_size', 16)
    epochs = config.get('epochs', 100)
    lr = config.get('learning_rate', 0.001)
    dropout_rate = config.get('dropout_rate', 0.25)
    filters_per_branch = config.get('filters_per_branch', 8)
    scales_time = config.get('scales_time', [500, 250, 125])
    activation = config.get('activation', 'elu')
    fs = config.get('fs', 128)
    
    # Analysis type mapping
    # 'erp' -> 'erp'
    # 'tf' -> 'time_frequency'
    # 'it' -> 'intertrial_coherence'
    analysis_type_map = {
        'erp': 'erp',
        'tf': 'time_frequency',
        'it': 'intertrial_coherence'
    }
    analysis_type = analysis_type_map.get(analysis_mode, 'erp')

    # -------------------------------------------------------------------------
    # 2. Load Data using Bridge
    # -------------------------------------------------------------------------
    print("Initializing PreprocessBridge...")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print(f"Loading {analysis_type} data for EEG-Inception...")
    try:
        # Bridge returns:
        # ERP: (Batch, 1, Channels, Time)
        # TF/ITC: (Batch, Channels, Freq, Time)
        X, y = bridge.load_and_transform(analysis_type, "eeg_inception")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
        return

    print(f"Data Loaded. Original Shape: {X.shape}")
    
    # -------------------------------------------------------------------------
    # 3. Data Reshaping Logic
    # -------------------------------------------------------------------------
    # EEG-Inception expects: (Batch, Time, Channels, 1)
    
    if analysis_type == 'erp':
        # Input: (Batch, 1, Channels, Time)
        # Transpose to (Batch, Time, Channels, 1)
        # Axis mapping: 0->0, 3->1, 2->2, 1->3
        X = np.transpose(X, (0, 3, 2, 1))
        
    elif analysis_type in ['time_frequency', 'intertrial_coherence']:
        # Input: (Batch, Channels, Freq, Time)
        # We need to map this to (Batch, Time, NewChannels, 1)
        # Strategy: Flatten Channels and Freq into one dimension -> NewChannels
        
        b, c, f, t = X.shape
        # Reshape to (Batch, C*F, Time)
        X = X.reshape(b, c * f, t)
        
        # Now we have (Batch, NewChannels, Time)
        # Transpose to (Batch, Time, NewChannels)
        X = np.transpose(X, (0, 2, 1))
        
        # Add the last dimension -> (Batch, Time, NewChannels, 1)
        X = X[..., np.newaxis]
        
        print(f"Reshaped TF/ITC data. Merged {c} channels * {f} freqs -> {c*f} input features.")

    print(f"Final Shape for Keras: {X.shape}")

    # Extract dimensions
    _, samples, chans, _ = X.shape
    
    # Calculate input_time based on samples and fs
    # samples = input_time * fs / 1000  => input_time = samples * 1000 / fs
    # Note: For TF data, 'fs' in the config should probably be set such that this calculation matches 'samples'
    # Or we can just reverse calculate input_time to satisfy the model's internal math.
    input_time = int(samples * 1000 / fs)
    print(f"Derived input_time: {input_time} ms (Samples: {samples}, Fs: {fs})")

    conditions = y['condition']
    subject_ids = y['subject_id']
    
    # Determine number of classes
    unique_conditions = np.unique(conditions)
    nb_classes = len(unique_conditions)
    print(f"Number of classes: {nb_classes}")

    # -------------------------------------------------------------------------
    # 3. Subject-Wise Split
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    train_subs, val_subs = train_test_split(unique_subjects, test_size=0.2, random_state=42)
    
    train_mask = np.isin(subject_ids, train_subs)
    val_mask = np.isin(subject_ids, val_subs)
    
    X_train = X[train_mask]
    y_train = conditions[train_mask]
    
    X_val = X[val_mask]
    y_val = conditions[val_mask]
    
    y_train_cat = to_categorical(y_train, num_classes=nb_classes)
    y_val_cat = to_categorical(y_val, num_classes=nb_classes)

    print("-" * 30)
    print(f"Training Set:   {X_train.shape} samples")
    print(f"Validation Set: {X_val.shape} samples")
    print("-" * 30)
    
    # -------------------------------------------------------------------------
    # 4. Model Initialization & Training
    # -------------------------------------------------------------------------
    print("Initializing EEG-Inception Model...")
    model = EEGInception(input_time=input_time, 
                         fs=fs, 
                         ncha=chans, 
                         filters_per_branch=filters_per_branch,
                         scales_time=scales_time,
                         dropout_rate=dropout_rate,
                         activation=activation,
                         n_classes=nb_classes,
                         learning_rate=lr)

    model.summary()

    checkpoint_path = os.path.join(current_dir, "weights", "best_model.h5")
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    
    callbacks = [
        ModelCheckpoint(filepath=checkpoint_path, 
                        verbose=1, 
                        save_best_only=True,
                        monitor='val_accuracy'),
        EarlyStopping(monitor='val_loss', 
                      min_delta=0.0001,
                      patience=10, 
                      verbose=1,
                      restore_best_weights=True)
    ]

    print("Starting Training...")
    history = model.fit(X_train, y_train_cat, 
                        batch_size=batch_size, 
                        epochs=epochs, 
                        verbose=2, 
                        validation_data=(X_val, y_val_cat),
                        callbacks=callbacks)
    
    print(f"Training complete. Best model saved to {checkpoint_path}")

if __name__ == "__main__":
    main()
