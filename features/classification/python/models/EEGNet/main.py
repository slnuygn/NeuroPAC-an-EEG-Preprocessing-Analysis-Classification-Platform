import os
import sys
import json
import numpy as np
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import backend as K

# -----------------------------------------------------------------------------
# Path Setup
# -----------------------------------------------------------------------------
# We need to import from 'core' which is two levels up.
current_dir = os.path.dirname(os.path.abspath(__file__))
python_root = os.path.abspath(os.path.join(current_dir, "../../"))

# Add python_root to sys.path to allow imports from 'core'
if python_root not in sys.path:
    sys.path.append(python_root)

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
try:
    from core.preprocess_bridge import PreprocessBridge
except ImportError as e:
    print(f"Error importing PreprocessBridge: {e}")
    print(f"Ensure that '{python_root}' is in your PYTHONPATH.")
    sys.exit(1)

try:
    from .model import EEGNet
except ImportError:
    # Fallback for running script directly
    from model import EEGNet

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
    data_folder = os.path.join(python_root, "data")
    
    # Determine which analysis type to use
    # Options: 'erp' (currently only ERP is supported for EEGNet)
    analysis_mode = 'erp'
    if len(sys.argv) > 1:
        analysis_mode = sys.argv[1]
    
    config_file = f"{analysis_mode}_config.json"
    config_path = os.path.join(current_dir, "configs", config_file)
    
    if not os.path.exists(config_path):
        print(f"Error: Config file {config_path} not found.")
        print(f"Note: EEGNet currently only supports 'erp' analysis.")
        return
    
    print(f"Using configuration: {config_file}")
    config = load_config(config_path)
    
    # Defaults
    nb_classes = config.get('num_classes', 3)
    batch_size = config.get('batch_size', 16)
    epochs = config.get('epochs', 50)
    lr = config.get('lr', 0.001)
    dropout_rate = config.get('dropout', 0.5)
    kern_length = config.get('kern_length', 64)
    f1 = config.get('f1', 8)
    d = config.get('d', 2)
    f2 = config.get('f2', 16)
    
    # Analysis type mapping (EEGNet uses same key for bridge)
    analysis_type = analysis_mode  # 'erp' -> 'erp'

    # -------------------------------------------------------------------------
    # 2. Load Data using Bridge
    # -------------------------------------------------------------------------
    print("Initializing PreprocessBridge...")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print(f"Loading {analysis_type} data for EEGNet...")
    try:
        # Bridge returns (Batch, 1, Channels, Time) for 'eeg_net'
        X, y = bridge.load_and_transform(analysis_type, "eeg_net")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
        return

    print(f"Data Loaded. Original Shape: {X.shape}")
    
    # Transpose to (Batch, Channels, Time, 1) for Keras channels_last
    # Input is (Batch, 1, Channels, Time) -> (Batch, Channels, Time, 1)
    X = np.transpose(X, (0, 2, 3, 1))
    print(f"Transposed Shape for Keras: {X.shape}")

    # Extract dimensions
    _, chans, samples, _ = X.shape

    # y is a dictionary: {'condition': ..., 'group': ..., 'subject_id': ...}
    conditions = y['condition']
    subject_ids = y['subject_id']
    
    # -------------------------------------------------------------------------
    # 3. Subject-Wise Split
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    print(f"Total unique subjects found: {len(unique_subjects)}")
    
    train_subs, val_subs = train_test_split(unique_subjects, test_size=0.2, random_state=42)
    
    print(f"Training Subjects: {len(train_subs)}")
    print(f"Validation Subjects: {len(val_subs)}")
    
    train_mask = np.isin(subject_ids, train_subs)
    val_mask = np.isin(subject_ids, val_subs)
    
    X_train = X[train_mask]
    y_train = conditions[train_mask]
    
    X_val = X[val_mask]
    y_val = conditions[val_mask]
    
    # One-hot encode labels
    y_train_cat = to_categorical(y_train, num_classes=nb_classes)
    y_val_cat = to_categorical(y_val, num_classes=nb_classes)

    print("-" * 30)
    print(f"Training Set:   {X_train.shape} samples")
    print(f"Validation Set: {X_val.shape} samples")
    print("-" * 30)
    
    # -------------------------------------------------------------------------
    # 4. Model Initialization & Training
    # -------------------------------------------------------------------------
    print("Initializing EEGNet Model...")
    model = EEGNet(nb_classes=nb_classes, 
                   Chans=chans, 
                   Samples=samples, 
                   dropoutRate=dropout_rate, 
                   kernLength=kern_length, 
                   F1=f1, 
                   D=d, 
                   F2=f2, 
                   dropoutType='Dropout')

    optimizer = Adam(learning_rate=lr)
    model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['accuracy'])
    model.summary()

    # Checkpoint to save best model
    checkpoint_path = os.path.join(current_dir, "weights", "best_model.h5")
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    
    checkpointer = ModelCheckpoint(filepath=checkpoint_path, 
                                   verbose=1, 
                                   save_best_only=True,
                                   monitor='val_accuracy')

    print("Starting Training...")
    history = model.fit(X_train, y_train_cat, 
                        batch_size=batch_size, 
                        epochs=epochs, 
                        verbose=2, 
                        validation_data=(X_val, y_val_cat),
                        callbacks=[checkpointer])
    
    print(f"Training complete. Best model saved to {checkpoint_path}")

if __name__ == "__main__":
    main()
