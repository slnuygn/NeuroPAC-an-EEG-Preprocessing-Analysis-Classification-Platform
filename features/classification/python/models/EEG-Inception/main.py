import os
import sys
import json
import warnings

# Suppress TensorFlow and NumPy warnings BEFORE importing TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logging (3 = ERROR only)
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom operations
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

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
capstone_root = os.path.abspath(os.path.join(current_dir, "../../../../.."))

if python_root not in sys.path:
    sys.path.insert(0, python_root)
if capstone_root not in sys.path:
    sys.path.insert(0, capstone_root)

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
try:
    from features.classification.python.core.preprocess_bridge import PreprocessBridge
except ImportError as e:
    try:
        from core.preprocess_bridge import PreprocessBridge
    except ImportError as e2:
        print(f"Error importing PreprocessBridge: {e2}")
        sys.exit(1)

try:
    from .model import EEGInception
except ImportError:
    from model import EEGInception

# Set image data format to channels_last
K.set_image_data_format('channels_last')

def load_config(config_path):
    """Load configuration from JSON file."""
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    return {}

def main():
    # -------------------------------------------------------------------------
    # 1. Configuration
    # -------------------------------------------------------------------------
    # Default data folder
    data_folder = os.path.join(python_root, "data")
    
    # Determine which config to use. 
    # You can change this variable or pass it as an argument.
    # Options: 'erp', 'tf', 'it'
    analysis_mode = 'erp' 
    if len(sys.argv) > 1:
        analysis_mode = sys.argv[1]
    
    # Override data folder if provided as command line argument
    if len(sys.argv) > 2:
        data_folder = sys.argv[2]
        print(f"Using data folder from argument: {data_folder}")

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
        # Handle different input shapes from bridge
        if X.ndim == 4:
            # Input: (Batch, 1, Channels, Time) -> (Batch, Time, Channels, 1)
            X = np.transpose(X, (0, 3, 2, 1))
        elif X.ndim == 3:
            # Input: (Batch, Channels, Time) -> (Batch, Time, Channels, 1)
            X = np.transpose(X, (0, 2, 1))  # (Batch, Time, Channels)
            X = X[..., np.newaxis]  # Add final dimension
        
        # Ensure 4th dimension exists
        if X.ndim == 3:
            X = X[..., np.newaxis]
        
        print(f"ERP reshaped to: {X.shape}")
        
    elif analysis_type in ['time_frequency', 'intertrial_coherence']:
        # Input: (Batch, Channels, Freq, Time)
        # We need to map this to (Batch, Time, NewChannels, 1)
        # Strategy: Flatten Channels and Freq into one dimension -> NewChannels
        
        print(f"TF/ITC input shape: {X.shape}, ndim: {X.ndim}")
        
        if X.ndim == 4:
            b, c, f, t = X.shape
            # Reshape to (Batch, C*F, Time)
            X = X.reshape(b, c * f, t)
            
            # Now we have (Batch, NewChannels, Time)
            # Transpose to (Batch, Time, NewChannels)
            X = np.transpose(X, (0, 2, 1))
            
            print(f"Reshaped TF/ITC data. Merged {c} channels * {f} freqs -> {c*f} input features.")
        elif X.ndim == 3:
            # If data is (Batch, Channels, Time), transpose to (Batch, Time, Channels)
            X = np.transpose(X, (0, 2, 1))
            print(f"Transposed 3D TF/ITC data to: {X.shape}")
        
        # Always ensure 4th dimension exists for TF/ITC
        if X.ndim == 3:
            X = X[..., np.newaxis]
            print(f"Added channel dimension: {X.shape}")

    # Final safety check - ensure 4D tensor
    if X.ndim == 3:
        X = X[..., np.newaxis]
        print(f"Final safety: Added 4th dimension: {X.shape}")

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
    # 3. Subject-Wise Split (Train/Validation/Test)
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    print(f"Total unique subjects found: {len(unique_subjects)}")
    
    # First split: 60% train, 40% temp (which will be split into val and test)
    train_subs, temp_subs = train_test_split(unique_subjects, test_size=0.4, random_state=42)
    # Second split: 20% validation, 20% test (50/50 split of the 40%)
    val_subs, test_subs = train_test_split(temp_subs, test_size=0.5, random_state=42)
    
    print(f"Training Subjects:   {len(train_subs)} ({len(train_subs)/len(unique_subjects)*100:.1f}%)")
    print(f"Validation Subjects: {len(val_subs)} ({len(val_subs)/len(unique_subjects)*100:.1f}%)")
    print(f"Test Subjects:       {len(test_subs)} ({len(test_subs)/len(unique_subjects)*100:.1f}%)")
    
    train_mask = np.isin(subject_ids, train_subs)
    val_mask = np.isin(subject_ids, val_subs)
    test_mask = np.isin(subject_ids, test_subs)
    
    X_train = X[train_mask]
    y_train = conditions[train_mask]
    
    X_val = X[val_mask]
    y_val = conditions[val_mask]
    
    X_test = X[test_mask]
    y_test = conditions[test_mask]
    
    # Debug: Check shapes after split
    print(f"X_train shape after split: {X_train.shape}, ndim: {X_train.ndim}")
    print(f"X_val shape after split: {X_val.shape}, ndim: {X_val.ndim}")
    print(f"X_test shape after split: {X_test.shape}, ndim: {X_test.ndim}")
    
    # Ensure 4D after split (safety check)
    if X_train.ndim == 3:
        X_train = X_train[..., np.newaxis]
        print(f"Added dimension to X_train: {X_train.shape}")
    if X_val.ndim == 3:
        X_val = X_val[..., np.newaxis]
        print(f"Added dimension to X_val: {X_val.shape}")
    if X_test.ndim == 3:
        X_test = X_test[..., np.newaxis]
        print(f"Added dimension to X_test: {X_test.shape}")
    
    y_train_cat = to_categorical(y_train, num_classes=nb_classes)
    y_val_cat = to_categorical(y_val, num_classes=nb_classes)
    y_test_cat = to_categorical(y_test, num_classes=nb_classes)

    print("-" * 30)
    print(f"Training Set:   {X_train.shape} samples")
    print(f"Validation Set: {X_val.shape} samples")
    print(f"Test Set:       {X_test.shape} samples")
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

    # Checkpoint to save best model in data folder with naming: EEG-Inception_{analysis}_weights_best.keras
    weights_filename = f"EEG-Inception_{analysis_mode}_weights_best.keras"
    checkpoint_path = os.path.join(data_folder, weights_filename)
    os.makedirs(data_folder, exist_ok=True)
    
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
    
    # Final shape check right before training
    print(f"PRE-TRAINING CHECK - X_train.shape: {X_train.shape}, X_val.shape: {X_val.shape}")
    
    # Force reshape to 4D if needed
    if X_train.ndim == 3:
        X_train = np.expand_dims(X_train, axis=-1)
        print(f"FORCED X_train to 4D: {X_train.shape}")
    if X_val.ndim == 3:
        X_val = np.expand_dims(X_val, axis=-1)
        print(f"FORCED X_val to 4D: {X_val.shape}")
    
    print(f"FINAL - X_train.shape: {X_train.shape}, X_val.shape: {X_val.shape}")
    
    history = model.fit(X_train, y_train_cat, 
                        batch_size=batch_size, 
                        epochs=epochs, 
                        verbose=2, 
                        validation_data=(X_val, y_val_cat),
                        callbacks=callbacks)
    
    print(f"Training complete. Best model saved to {checkpoint_path}")
    
    # -------------------------------------------------------------------------
    # 5. Final Evaluation on Test Set
    # -------------------------------------------------------------------------
    print("\n" + "="*50)
    print("FINAL EVALUATION ON HELD-OUT TEST SET")
    print("="*50)
    
    # Model already has best weights restored by EarlyStopping callback
    train_loss, train_accuracy = model.evaluate(X_train, y_train_cat, verbose=0)
    val_loss, val_accuracy = model.evaluate(X_val, y_val_cat, verbose=0)
    test_loss, test_accuracy = model.evaluate(X_test, y_test_cat, verbose=0)
    
    print(f"Training Accuracy:   {train_accuracy * 100:.2f}%")
    print(f"Validation Accuracy: {val_accuracy * 100:.2f}%")
    print(f"Test Accuracy:       {test_accuracy * 100:.2f}%")
    print(f"")
    print(f"Training Loss:       {train_loss:.4f}")
    print(f"Validation Loss:     {val_loss:.4f}")
    print(f"Test Loss:           {test_loss:.4f}")
    print("="*50)

if __name__ == "__main__":
    main()
