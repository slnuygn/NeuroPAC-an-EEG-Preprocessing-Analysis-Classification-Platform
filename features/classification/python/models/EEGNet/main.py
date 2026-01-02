import os
import sys
import json
import numpy as np
import warnings
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import backend as K

# Suppress TensorFlow and NumPy warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*oneDNN custom operations.*')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow logging

# -----------------------------------------------------------------------------
# Path Setup
# -----------------------------------------------------------------------------
# We need to import from 'core' which is two levels up.
current_dir = os.path.dirname(os.path.abspath(__file__))
python_root = os.path.abspath(os.path.join(current_dir, "../../"))
capstone_root = os.path.abspath(os.path.join(current_dir, "../../../../.."))

# Add paths to sys.path to allow imports from 'core' and 'features'
if python_root not in sys.path:
    sys.path.insert(0, python_root)
if capstone_root not in sys.path:
    sys.path.insert(0, capstone_root)

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
try:
    from features.classification.python.core.preprocess_bridge import PreprocessBridge
    from features.classification.python.core.labels import labels as group_list
except ImportError as e:
    try:
        from core.preprocess_bridge import PreprocessBridge
        from core.labels import labels as group_list
    except ImportError as e2:
        print(f"Error importing PreprocessBridge: {e2}")
        print(f"Ensure that '{python_root}' is in your PYTHONPATH.")
        sys.exit(1)

try:
    from .model import EEGNet
except ImportError:
    # Fallback for running script directly
    from model import EEGNet

# Explicitly disable post-run results folder/plots to avoid writing extra files
create_results_folder = None
save_metrics_json = None
generate_confusion_matrix_plot = None
generate_training_history_plot = None
generate_class_metrics_plot = None

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

def extract_unique_groups(selected_classes):
    """Extract unique group names from selected_classes list.
    
    Examples:
    - ["PD_target", "PD_standard"] -> ["PD"]
    - ["PD_target", "CTL_standard"] -> ["PD", "CTL"]
    - None or [] -> None
    """
    if not selected_classes or len(selected_classes) == 0:
        return None
    
    unique_groups = set()
    for class_str in selected_classes:
        if '_' in class_str:
            group = class_str.split('_')[0]
            unique_groups.add(group)
    
    if len(unique_groups) == 0:
        return None
    
    return sorted(list(unique_groups))

def main():
    # -------------------------------------------------------------------------
    # 1. Configuration
    # -------------------------------------------------------------------------
    # Default data folder
    data_folder = os.path.join(python_root, "data")
    
    # Determine which analysis type to use
    # Options: 'erp' (currently only ERP is supported for EEGNet)
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
    
    # Parse selected_classes from command line argument
    selected_classes = None
    if len(sys.argv) > 3:
        try:
            selected_classes = json.loads(sys.argv[3])
            print(f"Selected classes: {selected_classes}")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Could not parse selected_classes: {e}")
            selected_classes = None

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
    
    # Apply class filtering if selected classes provided
    if selected_classes and len(selected_classes) > 0:
        print(f"Filtering data for selected classes: {selected_classes}")
        try:
            # Extract the lists for filtering
            group_labels = y.get('group', [])
            condition_labels = y.get('condition', [])
            
            # Use the filter method from bridge
            X_filtered, group_filtered, condition_filtered, kept_indices = bridge.filter_by_selected_classes(
                X, group_labels, condition_labels, selected_classes
            )
            
            if len(X_filtered) > 0:
                X = np.array(X_filtered)
                # Update y dict with filtered values as numpy arrays
                y['group'] = np.array(group_filtered)
                y['condition'] = np.array(condition_filtered)
                # Filter subject_id using kept_indices
                if 'subject_id' in y and isinstance(y['subject_id'], (list, np.ndarray)):
                    original_ids = y['subject_id'] if isinstance(y['subject_id'], list) else y['subject_id'].tolist()
                    y['subject_id'] = np.array([original_ids[i] for i in kept_indices])
                print(f"After filtering: {len(X)} samples selected")
            else:
                print("Warning: Filtering resulted in no samples. Using all classes.")
        except Exception as e:
            print(f"Warning: Could not filter data by selected classes: {e}")
            print("Proceeding with all classes.")
    
    # Transpose to (Batch, Channels, Time, 1) for Keras channels_last
    # Input is (Batch, 1, Channels, Time) -> (Batch, Channels, Time, 1)
    X = np.transpose(X, (0, 2, 3, 1))
    print(f"Transposed Shape for Keras: {X.shape}")

    # Extract dimensions
    _, chans, samples, _ = X.shape

    # y is a dictionary: {'condition': ..., 'group': ..., 'subject_id': ...}
    conditions = y['condition']
    groups = y['group']
    subject_ids = y['subject_id']

    # ---------------------------------------------------------------------
    # Combine condition + group into a single multi-class label
    # Example (2 groups x 3 conditions): Target-HC, Standard-HC, Novelty-HC,
    # Target-Parkinson's, Standard-Parkinson's, Novelty-Parkinson's.
    # ---------------------------------------------------------------------
    group_count = len(group_list)
    if group_count == 0:
        print("Error: No group labels found; please populate core/labels.py")
        return

    valid_group_mask = np.isin(groups, np.arange(group_count))
    if not np.all(valid_group_mask):
        dropped = np.sum(~valid_group_mask)
        print(f"Warning: Dropping {dropped} samples with invalid group ids")
        X = X[valid_group_mask]
        conditions = conditions[valid_group_mask]
        groups = groups[valid_group_mask]
        subject_ids = subject_ids[valid_group_mask]

    combined_labels = conditions * group_count + groups
    
    # Get unique classes actually present in the filtered data
    unique_class_indices = np.unique(combined_labels)
    nb_classes_data = len(unique_class_indices)
    
    # Remap labels to contiguous range [0, nb_classes-1] for the model
    label_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(unique_class_indices)}
    combined_labels = np.array([label_mapping[label] for label in combined_labels])
    
    nb_classes = nb_classes_data
    
    print(f"Number of classes after filtering: {nb_classes}")
    print(f"Class indices present: {unique_class_indices.tolist()}")
    
    if nb_classes_data <= 1:
        print("Error: Need at least two combined classes to train.")
        return

    # Override nb_classes from config with the classes actually present
    if nb_classes != nb_classes_data:
        print(f"Overriding nb_classes from config ({nb_classes}) with data-derived value {nb_classes_data}")
        nb_classes = nb_classes_data
    
    # -------------------------------------------------------------------------
    # 3. Subject-Wise Split (Train/Validation/Test)
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    print(f"Total unique subjects found: {len(unique_subjects)}")
    
    if len(unique_subjects) < 3:
        print(f"Warning: Only {len(unique_subjects)} subject(s) available; using all for training and skipping val/test splits.")
        train_subs = unique_subjects
        val_subs = np.array([], dtype=unique_subjects.dtype)
        test_subs = np.array([], dtype=unique_subjects.dtype)
    else:
        # First split: 60% train, 40% temp (which will be split into val and test)
        train_subs, temp_subs = train_test_split(unique_subjects, test_size=0.4, random_state=42)
        # Second split: 20% validation, 20% test (50/50 split of the 40%)
        val_subs, test_subs = train_test_split(temp_subs, test_size=0.5, random_state=42)

    denom = len(unique_subjects) if len(unique_subjects) > 0 else 1
    print(f"Training Subjects:   {len(train_subs)} ({len(train_subs)/denom*100:.1f}%)")
    print(f"Validation Subjects: {len(val_subs)} ({len(val_subs)/denom*100:.1f}%)")
    print(f"Test Subjects:       {len(test_subs)} ({len(test_subs)/denom*100:.1f}%)")
    
    train_mask = np.isin(subject_ids, train_subs)
    val_mask = np.isin(subject_ids, val_subs)
    test_mask = np.isin(subject_ids, test_subs)
    
    X_train = X[train_mask]
    y_train = combined_labels[train_mask]
    
    X_val = X[val_mask]
    y_val = combined_labels[val_mask]
    
    X_test = X[test_mask]
    y_test = combined_labels[test_mask]
    
    # One-hot encode labels
    y_train_cat = to_categorical(y_train, num_classes=nb_classes)
    y_val_cat = to_categorical(y_val, num_classes=nb_classes) if len(y_val) > 0 else None
    y_test_cat = to_categorical(y_test, num_classes=nb_classes) if len(y_test) > 0 else None

    print("-" * 30)
    print(f"Training Set:   {X_train.shape} samples")
    print(f"Validation Set: {X_val.shape} samples")
    print(f"Test Set:       {X_test.shape} samples")
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

    # Create checkpoint path in data folder (no results subfolder)
    # Checkpoint to save best model with naming: EEGNet_{analysis}_g{groups}_weights_best.keras
    unique_groups = extract_unique_groups(selected_classes)
    if unique_groups:
        groups_str = "_".join(unique_groups)
        weights_filename = f"EEGNet_{analysis_mode}_g{groups_str}_weights_best.keras"
    else:
        weights_filename = f"EEGNet_{analysis_mode}_weights_best.keras"
    
    checkpoint_path = os.path.join(data_folder, weights_filename)
    
    checkpointer = ModelCheckpoint(filepath=checkpoint_path, 
                                   verbose=1, 
                                   save_best_only=True,
                                   monitor='val_accuracy')

    print("Starting Training...")
    if y_val_cat is not None and len(X_val) > 0:
        history = model.fit(X_train, y_train_cat, 
                            batch_size=batch_size, 
                            epochs=epochs, 
                            verbose=2, 
                            validation_data=(X_val, y_val_cat),
                            callbacks=[checkpointer])
    else:
        history = model.fit(X_train, y_train_cat, 
                            batch_size=batch_size, 
                            epochs=epochs, 
                            verbose=2, 
                            callbacks=[checkpointer])
    
    print(f"Training complete. Best model saved to {checkpoint_path}")
    
    # -------------------------------------------------------------------------
    # 5. Final Evaluation on Test Set
    # -------------------------------------------------------------------------
    print("\n" + "="*50)
    print("FINAL EVALUATION ON HELD-OUT TEST SET")
    print("="*50)
    
    # Load best weights
    model.load_weights(checkpoint_path)
    
    # Evaluate on available sets
    train_loss, train_accuracy = model.evaluate(X_train, y_train_cat, verbose=0)
    print(f"Training Accuracy:   {train_accuracy * 100:.2f}%")
    print(f"Training Loss:       {train_loss:.4f}")

    if y_val_cat is not None and len(X_val) > 0:
        val_loss, val_accuracy = model.evaluate(X_val, y_val_cat, verbose=0)
        print(f"Validation Accuracy: {val_accuracy * 100:.2f}%")
        print(f"Validation Loss:     {val_loss:.4f}")
    else:
        print("Validation set skipped (not enough subjects)")

    if y_test_cat is not None and len(X_test) > 0:
        test_loss, test_accuracy = model.evaluate(X_test, y_test_cat, verbose=0)
        print(f"Test Accuracy:       {test_accuracy * 100:.2f}%")
        print(f"Test Loss:           {test_loss:.4f}")
    else:
        print("Test set skipped (not enough subjects)")
    print("="*50)
    
    # -------------------------------------------------------------------------
    # 6. Results generation disabled (requested: no results folder or artifacts)
    # -------------------------------------------------------------------------
    # Intentionally omitted: metrics JSON, plots, and results folder creation

if __name__ == "__main__":
    main()
