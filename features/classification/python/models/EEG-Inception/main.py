import os
import sys
import json
import warnings

# Suppress TensorFlow and NumPy warnings BEFORE importing TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logging (3 = ERROR only)
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom operations
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='.*tf.function retracing.*')

import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, StratifiedGroupKFold
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau, LearningRateScheduler
from tensorflow.keras import backend as K
import tensorflow as tf
from tensorflow.keras.callbacks import Callback


class StopOnAccuracy(Callback):
    """Stop training early once validation accuracy reaches target."""

    def __init__(self, target=0.68):
        super().__init__()
        self.target = target

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        val_acc = logs.get("val_accuracy")
        if val_acc is not None and val_acc >= self.target:
            self.model.stop_training = True

# -----------------------------------------------------------------------------
# Data Augmentation Functions
# -----------------------------------------------------------------------------
def augment_tf_data(X, y, augmentation_factor=5):
    """
    Augment time-frequency data with various transformations.
    
    Parameters
    ----------
    X : np.ndarray
        Input data of shape (N, Freq, Time, Channels)
    y : np.ndarray
        Labels
    augmentation_factor : int
        How many augmented copies to create per sample
    
    Returns
    -------
    X_aug, y_aug : augmented data and labels
    """
    X_augmented = [X]
    y_augmented = [y]
    
    n_samples, n_freqs, n_times, n_channels = X.shape
    
    for _ in range(augmentation_factor):
        X_new = X.copy()
        
        for i in range(n_samples):
            # Random combination of augmentations
            aug_type = np.random.randint(0, 6)
            
            if aug_type == 0:
                # Gaussian noise
                noise_level = np.random.uniform(0.05, 0.2)
                X_new[i] += np.random.normal(0, noise_level, X_new[i].shape)
            
            elif aug_type == 1:
                # Time shift (roll along time axis)
                shift = np.random.randint(-3, 4)
                X_new[i] = np.roll(X_new[i], shift, axis=1)
            
            elif aug_type == 2:
                # Frequency masking (zero out random freq bands)
                mask_width = np.random.randint(1, 8)
                mask_start = np.random.randint(0, n_freqs - mask_width)
                X_new[i, mask_start:mask_start+mask_width, :, :] *= 0.1
            
            elif aug_type == 3:
                # Time masking (zero out random time points)
                mask_width = np.random.randint(1, 4)
                mask_start = np.random.randint(0, n_times - mask_width)
                X_new[i, :, mask_start:mask_start+mask_width, :] *= 0.1
            
            elif aug_type == 4:
                # Channel dropout (zero out random channels)
                n_drop = np.random.randint(1, 3)
                drop_idx = np.random.choice(n_channels, n_drop, replace=False)
                X_new[i, :, :, drop_idx] *= 0.1
            
            elif aug_type == 5:
                # Scaling
                scale = np.random.uniform(0.8, 1.2)
                X_new[i] *= scale
        
        X_augmented.append(X_new)
        y_augmented.append(y.copy())
    
    return np.concatenate(X_augmented, axis=0), np.concatenate(y_augmented, axis=0)


def mixup(X, y, alpha=0.2):
    """Apply mixup augmentation."""
    n_samples = len(X)
    indices = np.random.permutation(n_samples)
    
    lam = np.random.beta(alpha, alpha, n_samples)
    lam = lam.reshape(-1, 1, 1, 1)
    
    X_mixed = lam * X + (1 - lam) * X[indices]
    
    lam_y = lam.reshape(-1, 1)
    y_mixed = lam_y * y + (1 - lam_y) * y[indices]
    
    return X_mixed, y_mixed

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
    from .model_tf import EEGInceptionTF, LightweightTFNet, SimpleTFNet
except ImportError:
    from model import EEGInception
    from model_tf import EEGInceptionTF, LightweightTFNet, SimpleTFNet

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
    selected_classes = None  # Will store selected classes if provided
    
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
    
    # Parse selected classes if provided as third argument (JSON string)
    if len(sys.argv) > 3:
        try:
            selected_classes = json.loads(sys.argv[3])
            if selected_classes:
                print(f"Using selected classes: {selected_classes}")
        except json.JSONDecodeError:
            print("Warning: Could not parse selected classes argument, using all classes.")
            selected_classes = None

    config_file = f"{analysis_mode}_config.json"
    config_path = os.path.join(current_dir, "configs", config_file)
    
    if not os.path.exists(config_path):
        print(f"Error: Config file {config_path} not found.")
        return

    print(f"Using configuration: {config_file}")
    config = load_config(config_path)
    
    # Defaults
    batch_size = config.get('batch_size', 32)
    epochs = config.get('epochs', 25)
    lr = config.get('learning_rate', 0.001)
    dropout_rate = config.get('dropout_rate', 0.25)
    filters_per_branch = config.get('filters_per_branch', 8)
    scales_time = config.get('scales_time', [500, 250, 125])
    activation = config.get('activation', 'elu')
    fs = config.get('fs', 128)
    normalize_data = config.get('normalize_data', False)
    target_val_acc = config.get('target_val_acc', 0.68)
    use_kfold = config.get('use_kfold', False)
    n_folds = config.get('n_folds', 3)
    
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
    print(f"Data stats - Min: {X.min():.4f}, Max: {X.max():.4f}, Mean: {X.mean():.4f}, Std: {X.std():.4f}")
    
    # Debug: Show selected_classes value
    print(f"DEBUG: selected_classes = {selected_classes}, type = {type(selected_classes)}")
    
    # Apply class filtering if selected classes provided
    if selected_classes and len(selected_classes) > 0:
        print(f"Filtering data for selected classes: {selected_classes}")
        try:
            # y is a dict with keys: 'sample', 'condition', 'group', 'subject_id', 'dataset_name'
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
                # Filter other fields using kept_indices
                for key in ['subject_id', 'dataset_name']:
                    if key in y and isinstance(y[key], (list, np.ndarray)):
                        original_list = y[key] if isinstance(y[key], list) else y[key].tolist()
                        filtered_list = [original_list[i] for i in kept_indices]
                        y[key] = np.array(filtered_list) if key == 'subject_id' else filtered_list
                print(f"After filtering: {len(X)} samples selected")
                print(f"DEBUG: y dict lengths after filtering: group={len(y['group'])}, condition={len(y['condition'])}, subject_id={len(y['subject_id'])}")
            else:
                print("Warning: Filtering resulted in no samples. Using all classes.")
        except Exception as e:
            print(f"Warning: Could not filter data by selected classes: {e}")
            print("Proceeding with all classes.")
    
    # Check for NaN or Inf values
    if np.isnan(X).any():
        print("WARNING: NaN values detected in data! Replacing with 0.")
        X = np.nan_to_num(X, nan=0.0)
    if np.isinf(X).any():
        print("WARNING: Inf values detected in data! Clipping.")
        X = np.clip(X, -1e10, 1e10)
    
    # Normalize data if configured (important for TF power values)
    if normalize_data:
        print("Normalizing data (z-score per sample)...")
        # Normalize each sample independently
        for i in range(X.shape[0]):
            sample = X[i]
            mean = sample.mean()
            std = sample.std()
            if std > 0:
                X[i] = (sample - mean) / std
            else:
                X[i] = sample - mean
        print(f"After normalization - Min: {X.min():.4f}, Max: {X.max():.4f}, Mean: {X.mean():.4f}, Std: {X.std():.4f}")
    
    # -------------------------------------------------------------------------
    # 3. Data Reshaping Logic
    # -------------------------------------------------------------------------
    # EEG-Inception expects: (Batch, Time, Channels, 1)
    
    print(f"Input data shape: {X.shape}, ndim: {X.ndim}")
    
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
        # Data from HDF5 comes as (Batch, Freq, Time, Channels)
        # For lightweight model: keep as (Batch, Freq, Time, Channels) - treat as 2D image
        
        print(f"TF/ITC input shape: {X.shape}, ndim: {X.ndim}")
        
        if X.ndim == 4:
            b, d1, d2, d3 = X.shape
            print(f"Dimensions: d1={d1}, d2={d2}, d3={d3}")
            
            # Identify dims: Channels smallest (12), Time medium (29), Freq largest (91)
            if d3 <= min(d1, d2):
                # Already (Batch, Freq, Time, Channels) - perfect for 2D CNN
                n_freqs, n_times, n_channels = d1, d2, d3
                print(f"Data is (B, Freq={n_freqs}, Time={n_times}, Channels={n_channels})")
            elif d1 <= min(d2, d3):
                # (Batch, Channels, Freq, Time) -> (Batch, Freq, Time, Channels)
                X = np.transpose(X, (0, 2, 3, 1))
                n_freqs, n_times, n_channels = d2, d3, d1
                print(f"Transposed to (B, Freq={n_freqs}, Time={n_times}, Channels={n_channels})")
            else:
                # (Batch, Time, Freq, Channels) -> (Batch, Freq, Time, Channels)
                X = np.transpose(X, (0, 2, 1, 3))
                n_freqs, n_times, n_channels = d2, d1, d3
                print(f"Transposed to (B, Freq={n_freqs}, Time={n_times}, Channels={n_channels})")
        
        elif X.ndim == 3:
            # Add channel dimension
            X = X[..., np.newaxis]
            print(f"Added channel dim: {X.shape}")

    print(f"Final Shape for Keras: {X.shape}")

    # Extract dimensions
    _, samples, chans, _ = X.shape
    
    # For EEG-Inception, we pass input_samples directly to avoid rounding issues
    # when converting between milliseconds and samples
    print(f"Using direct input_samples: {samples}, Channels: {chans}")

    conditions = y['condition']  # 0=target, 1=standard, 2=novelty
    groups = y['group']          # 0=HC/CTL, 1=PD
    subject_ids = y['subject_id']
    
    print(f"DEBUG: After extraction - len(conditions)={len(conditions)}, len(groups)={len(groups)}, len(subject_ids)={len(subject_ids)}")
    
    # --------------------------------------------------------------------------
    # CLASSIFICATION MODE: Multi-class (PD/HC × condition)
    # --------------------------------------------------------------------------
    # Create combined labels: group * 3 + condition
    # Original mapping: HC-target=0, HC-standard=1, HC-novelty=2, PD-target=3, PD-standard=4, PD-novelty=5
    combined_labels = groups * 3 + conditions
    
    # Get unique classes actually present in the filtered data
    unique_class_indices = np.unique(combined_labels)
    nb_classes = len(unique_class_indices)
    
    # Remap labels to contiguous range [0, nb_classes-1] for the model
    label_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(unique_class_indices)}
    combined_labels_remapped = np.array([label_mapping[label] for label in combined_labels])
    
    # Create class names for the filtered classes
    all_class_names = ['HC-target', 'HC-standard', 'HC-novelty', 'PD-target', 'PD-standard', 'PD-novelty']
    class_names = [all_class_names[i] for i in unique_class_indices]
    
    print(f"Number of classes after filtering: {nb_classes}")
    print(f"Classes present: {class_names}")
    print(f"Class distribution:")
    for new_idx, old_idx in enumerate(unique_class_indices):
        count = np.sum(combined_labels == old_idx)
        print(f"  {all_class_names[old_idx]}: {count} samples (remapped to class {new_idx})")
    
    # Use remapped labels for training
    combined_labels = combined_labels_remapped

    # -------------------------------------------------------------------------
    # 3. Subject-Wise K-Fold Cross-Validation for better performance estimate
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    print(f"Total unique subjects found: {len(unique_subjects)}")
    
    # Use K-Fold CV for more robust accuracy estimation
    n_folds = n_folds if n_folds > 1 else 3
    use_kfold = bool(use_kfold)  # Set via config; default is single train/val/test split for speed
    
    if use_kfold:
        print(f"\n=== Using {n_folds}-Fold Cross-Validation (Subject-Wise) ===")
        
        # Group subjects by their label (PD or HC)
        subject_labels = []
        for sub in unique_subjects:
            mask = subject_ids == sub
            label = combined_labels[mask][0]  # All trials for same subject have same group label
            subject_labels.append(label)
        subject_labels = np.array(subject_labels)
        
        skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
        
        fold_scores = []
        all_predictions = []
        all_true_labels = []
        best_fold_accuracy = 0
        best_model = None
        
        for fold, (train_sub_idx, val_sub_idx) in enumerate(skf.split(unique_subjects, subject_labels)):
            print(f"\n{'='*50}")
            print(f"FOLD {fold + 1}/{n_folds}")
            print(f"{'='*50}")
            
            train_subs = unique_subjects[train_sub_idx]
            val_subs = unique_subjects[val_sub_idx]
            
            train_mask = np.isin(subject_ids, train_subs)
            val_mask = np.isin(subject_ids, val_subs)
            
            X_train = X[train_mask]
            y_train = combined_labels[train_mask]
            
            X_val = X[val_mask]
            y_val = combined_labels[val_mask]
            
            print(f"Train subjects: {len(train_subs)}, samples: {len(X_train)}")
            print(f"Val subjects: {len(val_subs)}, samples: {len(X_val)}")
            
            # Data augmentation for training
            if analysis_type in ['time_frequency', 'intertrial_coherence']:
                aug_factor = 3  # Increased from 2 to 3; 3+1=4x total augmentation
                print(f"Applying data augmentation (factor: {aug_factor})...")
                X_train_aug, y_train_aug = augment_tf_data(X_train, y_train, augmentation_factor=aug_factor)
                
                # Extra augmentation passes for the hardest classes (HC-novelty=2, PD-standard=4)
                # These need more samples to learn better
                print(f"Applying extra targeted augmentation for hard classes...")
                for hard_class in [2, 4]:  # HC-novelty and PD-standard
                    mask = y_train == hard_class
                    if mask.sum() > 0:
                        X_hard = X_train[mask]
                        y_hard = y_train[mask]
                        # Do 2 more augmentation passes for these classes
                        X_hard_aug, y_hard_aug = augment_tf_data(X_hard, y_hard, augmentation_factor=2)
                        X_train_aug = np.concatenate([X_train_aug, X_hard_aug])
                        y_train_aug = np.concatenate([y_train_aug, y_hard_aug])
                
                # Shuffle
                shuffle_idx = np.random.permutation(len(X_train_aug))
                X_train_aug = X_train_aug[shuffle_idx]
                y_train_aug = y_train_aug[shuffle_idx]
                print(f"Augmented training set: {X_train_aug.shape[0]} samples (original: {X_train.shape[0]})")
            else:
                X_train_aug = X_train
                y_train_aug = y_train
            
            y_train_cat = to_categorical(y_train_aug, num_classes=nb_classes)
            y_val_cat = to_categorical(y_val, num_classes=nb_classes)
            
            # AGGRESSIVE class-specific sample weights for hard classes
            from sklearn.utils.class_weight import compute_class_weight
            class_weights = compute_class_weight('balanced', classes=np.unique(y_train_aug), y=y_train_aug)
            class_weight_dict = {i: w for i, w in enumerate(class_weights)}
            
            # Apply VERY aggressive class-specific sample weights
            # Based on your confusion matrix - these classes need the most help:
            sample_weights = np.ones(len(y_train_aug))
            for i, label in enumerate(y_train_aug):
                base_weight = class_weight_dict[label]
                
                if label == 2:  # HC-novelty - 24% recall, WORST
                    sample_weights[i] = base_weight * 3.0  # TRIPLE the weight
                elif label == 4:  # PD-standard - 28% recall, VERY BAD
                    sample_weights[i] = base_weight * 2.8  # 2.8x weight
                elif label == 0:  # HC-target - 44% recall, needs improvement
                    sample_weights[i] = base_weight * 1.8  # 1.8x weight
                elif label == 3:  # PD-target - 44% recall, needs improvement
                    sample_weights[i] = base_weight * 1.7  # 1.7x weight
                elif label == 5:  # PD-novelty - 40% recall, okay but help
                    sample_weights[i] = base_weight * 1.2  # 1.2x weight
                else:  # HC-standard - 56% recall, already good, barely boost
                    sample_weights[i] = base_weight * 1.1  # 1.1x weight
            
            # Normalize weights so average = 1.0 to keep loss magnitude stable
            sample_weights = sample_weights / sample_weights.mean()
            
            print(f"Class weights (balanced): {class_weight_dict}")
            print(f"Sample weight stats - min: {sample_weights.min():.3f}, max: {sample_weights.max():.3f}, mean: {sample_weights.mean():.3f}")
            
            # Build fresh model for each fold
            K.clear_session()
            
            if analysis_type in ['time_frequency', 'intertrial_coherence']:
                n_freqs, n_times, n_channels = X_train.shape[1], X_train.shape[2], X_train.shape[3]
                model = EEGInceptionTF(
                    n_freqs=n_freqs, n_times=n_times, n_channels=n_channels,
                    n_classes=nb_classes, filters_per_branch=filters_per_branch,
                    dropout_rate=dropout_rate, activation=activation, learning_rate=lr
                )
            else:
                model = EEGInception(input_samples=samples, fs=fs, ncha=chans,
                                    filters_per_branch=filters_per_branch,
                                    scales_time=scales_time, dropout_rate=dropout_rate,
                                    activation=activation, n_classes=nb_classes, learning_rate=lr)
            
            if fold == 0:
                model.summary()
            
            callbacks = [
                EarlyStopping(monitor='val_accuracy', min_delta=0.0005, patience=20,
                              verbose=1, restore_best_weights=True),
                ReduceLROnPlateau(monitor='val_loss', factor=0.7, patience=8, min_lr=1e-7, verbose=1),
                StopOnAccuracy(target=target_val_acc)
            ]
            
            print(f"\nTraining Fold {fold + 1}/{n_folds} for {epochs} epochs...")
            print("-" * 50)
            history = model.fit(X_train_aug, y_train_cat, batch_size=batch_size, epochs=epochs,
                               verbose=2, validation_data=(X_val, y_val_cat), callbacks=callbacks,
                               sample_weight=sample_weights)
            
            # Evaluate
            print(f"\nEvaluating Fold {fold + 1}...")
            val_loss, val_accuracy = model.evaluate(X_val, y_val_cat, verbose=0)
            fold_scores.append(val_accuracy)
            
            # Track best model
            if val_accuracy > best_fold_accuracy:
                best_fold_accuracy = val_accuracy
                best_model = model
            
            # Get predictions
            predictions = model.predict(X_val, verbose=0)
            pred_labels = np.argmax(predictions, axis=1)
            all_predictions.extend(pred_labels)
            all_true_labels.extend(y_val)
            
            print(f"{'='*50}")
            print(f"[COMPLETE] Fold {fold + 1} Finished")
            print(f"  Validation Accuracy: {val_accuracy * 100:.2f}%")
            print(f"  Validation Loss:     {val_loss:.4f}")
            print(f"  Best So Far:         {best_fold_accuracy * 100:.2f}%")
            print(f"{'='*50}")
        
        # Final CV Results
        print("\n" + "="*60)
        print("K-FOLD CROSS-VALIDATION RESULTS")
        print("="*60)
        print(f"Fold Accuracies: {[f'{s*100:.1f}%' for s in fold_scores]}")
        print(f"Mean Accuracy:   {np.mean(fold_scores)*100:.2f}% (+/- {np.std(fold_scores)*100:.2f}%)")
        print(f"Min Accuracy:    {np.min(fold_scores)*100:.2f}%")
        print(f"Max Accuracy:    {np.max(fold_scores)*100:.2f}%")
        
        # Confusion matrix summary
        from sklearn.metrics import confusion_matrix, classification_report
        cm = confusion_matrix(all_true_labels, all_predictions)
        print(f"\nOverall Confusion Matrix:")
        print(cm)
        print(f"\nClassification Report:")
        print(classification_report(all_true_labels, all_predictions, target_names=class_names))
        print("="*60)
        
        # Save the best model from K-Fold CV to the data folder
        if best_model is not None:
            model_name = "EEG-Inception"
            unique_groups = extract_unique_groups(selected_classes)
            if unique_groups:
                groups_str = "_".join(unique_groups)
                weights_filename = f"{model_name}_{analysis_mode}_g{groups_str}_weights_best.keras"
            else:
                weights_filename = f"{model_name}_{analysis_mode}_weights_best.keras"
            checkpoint_path = os.path.join(data_folder, weights_filename)
            best_model.save(checkpoint_path)
            print(f"\nBest model (accuracy: {best_fold_accuracy*100:.2f}%) saved to: {checkpoint_path}")
        
        return  # Exit after K-Fold CV
    
    # -------------------------------------------------------------------------
    # SINGLE SPLIT (if not using K-Fold)
    # -------------------------------------------------------------------------
    
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
    y_train = combined_labels[train_mask]
    
    X_val = X[val_mask]
    y_val = combined_labels[val_mask]
    
    X_test = X[test_mask]
    y_test = combined_labels[test_mask]
    
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
    print(f"Training Set (before augmentation):   {X_train.shape} samples")
    print(f"Validation Set: {X_val.shape} samples")
    print(f"Test Set:       {X_test.shape} samples")
    print("-" * 30)
    
    # -------------------------------------------------------------------------
    # 3.5 Data Augmentation (for TF data)
    # -------------------------------------------------------------------------
    if analysis_type in ['time_frequency', 'intertrial_coherence']:
        print("\nApplying data augmentation...")
        aug_factor = 6  # Leaner augmentation for faster epochs
        X_train_aug, y_train_aug = augment_tf_data(X_train, y_train, augmentation_factor=aug_factor)
        y_train_cat_aug = to_categorical(y_train_aug, num_classes=nb_classes)
        
        # Shuffle augmented data
        shuffle_idx = np.random.permutation(len(X_train_aug))
        X_train_aug = X_train_aug[shuffle_idx]
        y_train_cat_aug = y_train_cat_aug[shuffle_idx]
        
        print(f"Training Set (after augmentation): {X_train_aug.shape} samples")
        print(f"Augmentation factor: {aug_factor+1}x")
    else:
        X_train_aug = X_train
        y_train_cat_aug = y_train_cat

    # -------------------------------------------------------------------------
    # 4. Model Initialization & Training
    # -------------------------------------------------------------------------
    
    # Choose model based on analysis type
    if analysis_type in ['time_frequency', 'intertrial_coherence']:
        # Use EEG-Inception adapted for TF data
        print("Initializing EEG-Inception TF Model...")
        # X_train shape is (Batch, Freq, Time, Channels)
        n_freqs, n_times, n_channels = X_train.shape[1], X_train.shape[2], X_train.shape[3]
        print(f"TF Model input: n_freqs={n_freqs}, n_times={n_times}, n_channels={n_channels}")
        
        model = EEGInceptionTF(
            n_freqs=n_freqs,
            n_times=n_times,
            n_channels=n_channels,
            n_classes=nb_classes,
            filters_per_branch=filters_per_branch,
            dropout_rate=dropout_rate,
            activation=activation,
            learning_rate=lr
        )
    else:
        # Use EEG-Inception for raw EEG data
        print("Initializing EEG-Inception Model...")
        model = EEGInception(input_samples=samples,
                             fs=fs, 
                             ncha=chans, 
                             filters_per_branch=filters_per_branch,
                             scales_time=scales_time,
                             dropout_rate=dropout_rate,
                             activation=activation,
                             n_classes=nb_classes,
                             learning_rate=lr)

    model.summary()

    # Checkpoint to save best model in data folder
    # Use "EEG-Inception" to match QML ClassifierTemplate expectations
    model_name = "EEG-Inception"
    
    # Use .keras extension for Keras 3.x compatibility
    unique_groups = extract_unique_groups(selected_classes)
    if unique_groups:
        groups_str = "_".join(unique_groups)
        weights_filename = f"{model_name}_{analysis_mode}_g{groups_str}_weights_best.keras"
    else:
        weights_filename = f"{model_name}_{analysis_mode}_weights_best.keras"

    # Save best weights directly in data folder; avoid creating a results folder
    checkpoint_path = os.path.join(data_folder, weights_filename)
    
    callbacks = [
        ModelCheckpoint(filepath=checkpoint_path, 
                        verbose=0, 
                        save_best_only=True,
                        monitor='val_accuracy'),
        EarlyStopping(monitor='val_accuracy', 
                      min_delta=0.002,
                      patience=8,
                      verbose=0,
                      restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss',
                          factor=0.5,
                          patience=4,
                          min_lr=1e-6,
                          verbose=0),
        StopOnAccuracy(target=target_val_acc)
    ]

    print("Starting Training...")
    
    # Final shape check right before training
    print(f"PRE-TRAINING CHECK - X_train_aug.shape: {X_train_aug.shape}, X_val.shape: {X_val.shape}")
    
    # Force reshape to 4D if needed
    if X_train_aug.ndim == 3:
        X_train_aug = np.expand_dims(X_train_aug, axis=-1)
        print(f"FORCED X_train_aug to 4D: {X_train_aug.shape}")
    if X_val.ndim == 3:
        X_val = np.expand_dims(X_val, axis=-1)
        print(f"FORCED X_val to 4D: {X_val.shape}")
    
    print(f"FINAL - X_train_aug.shape: {X_train_aug.shape}, X_val.shape: {X_val.shape}")
    
    # Train with augmented data
    history = model.fit(X_train_aug, y_train_cat_aug, 
                        batch_size=batch_size, 
                        epochs=epochs, 
                        verbose=0, 
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
