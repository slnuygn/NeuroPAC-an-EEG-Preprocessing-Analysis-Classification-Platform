import os
import sys
import json
import warnings

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import numpy as np
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import load_model
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

K.set_image_data_format('channels_last')

def main():
    # -------------------------------------------------------------------------
    # 1. Parse Arguments
    # -------------------------------------------------------------------------
    if len(sys.argv) < 2:
        print("Usage: python test.py <analysis_mode> [data_folder] [weights_path]")
        print("Example: python test.py erp /path/to/data /path/to/weights.h5")
        sys.exit(1)
    
    analysis_mode = sys.argv[1]
    data_folder = sys.argv[2] if len(sys.argv) > 2 else os.path.join(python_root, "data")
    
    # Auto-detect weights path
    if len(sys.argv) > 3:
        weights_path = sys.argv[3]
    else:
        weights_filename = f"EEG-Inception_{analysis_mode}_weights_best.keras"
        weights_path = os.path.join(data_folder, weights_filename)
    
    # Auto-detect weights path
    if len(sys.argv) > 3:
        weights_path = sys.argv[3]
    else:
        weights_filename = f"EEG-Inception_{analysis_mode}_weights_best.keras"
        weights_path = os.path.join(data_folder, weights_filename)
    
    print(f"Testing EEG-Inception with {analysis_mode} analysis")
    print(f"Data folder: {data_folder}")
    print(f"Weights file: {weights_path}")
    
    if not os.path.exists(weights_path):
        print(f"Error: Weights file not found at {weights_path}")
        sys.exit(1)
    
    # Analysis type mapping
    analysis_type_map = {
        'erp': 'erp',
        'tf': 'time_frequency',
        'it': 'intertrial_coherence'
    }
    analysis_type = analysis_type_map.get(analysis_mode, 'erp')
    
    # -------------------------------------------------------------------------
    # 2. Load Data
    # -------------------------------------------------------------------------
    print("\nInitializing PreprocessBridge...")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print(f"Loading {analysis_type} data...")
    try:
        X, y = bridge.load_and_transform(analysis_type, "eeg_inception")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    print(f"Data Loaded. Shape: {X.shape}")
    
    # Apply same reshaping as training to match model input
    # Model expects: (Batch, Freq=91, Time=29, Channels=12)
    if analysis_type == 'erp':
        # ERP data: (Batch, 1, Channels, Time) -> (Batch, Time, Channels, 1)
        if X.ndim == 4:
            X = np.transpose(X, (0, 3, 2, 1))
        elif X.ndim == 3:
            X = np.transpose(X, (0, 2, 1))
            X = X[..., np.newaxis]
        if X.ndim == 3:
            X = X[..., np.newaxis]
    elif analysis_type in ['time_frequency', 'intertrial_coherence']:
        # Time-frequency data - model expects: (Batch, Freq, Time, Channels)
        # Freq is typically largest (91), Channels smallest (12), Time medium (29)
        if X.ndim == 4:
            b, d1, d2, d3 = X.shape
            print(f"Detecting dimension order: d1={d1}, d2={d2}, d3={d3}")
            
            # Identify dims by their typical sizes: Freq~91, Time~29, Channels~12
            # Check if already in correct order (Freq, Time, Channels)
            if d1 > d2 > d3:
                # Already (Batch, Freq, Time, Channels) - no change needed
                print(f"Data already in correct order (B, Freq={d1}, Time={d2}, Channels={d3})")
            elif d3 > d2 > d1:
                # (Batch, Channels, Time, Freq) -> (Batch, Freq, Time, Channels)
                X = np.transpose(X, (0, 3, 2, 1))
                print(f"Transposed from (B, C, T, F) to (B, F={d3}, T={d2}, C={d1})")
            elif d1 < min(d2, d3):
                # (Batch, Channels, Freq, Time) -> (Batch, Freq, Time, Channels)
                X = np.transpose(X, (0, 2, 3, 1))
                print(f"Transposed from (B, C, F, T) to (B, F={d2}, T={d3}, C={d1})")
            else:
                # Keep as-is if dimensions don't match expected patterns
                print(f"Keeping original shape - dimensions don't match expected patterns")
        elif X.ndim == 3:
            X = X[..., np.newaxis]
    else:
        # Default: ensure 4D
        if X.ndim == 3:
            X = X[..., np.newaxis]
    
    print(f"Final shape for model: {X.shape}")
    
    conditions = y['condition']  # 0=target, 1=standard, 2=novelty
    groups = y['group']  # 0=HC, 1=PD
    subject_ids = y['subject_id']
    dataset_names = y['dataset_name']  # Extract dataset names
    
    # -------------------------------------------------------------------------
    # 3. Load Model first to detect number of classes
    # -------------------------------------------------------------------------
    print(f"\nLoading model from {weights_path}...")
    model = load_model(weights_path)
    
    # Detect number of classes from model output layer
    model_output_classes = model.output_shape[-1]
    print(f"Model output classes: {model_output_classes}")
    
    # Always use 6-class mode: group × condition (HC/PD × Target/Standard/Novelty)
    # Labels = group * 3 + condition
    # HC-Target=0, HC-Standard=1, HC-Novelty=2, PD-Target=3, PD-Standard=4, PD-Novelty=5
    condition_names = ["Target", "Standard", "Novelty"]
    group_names = ["HC", "PD"]
    
    # Build combined labels for each sample
    combined_labels = groups * 3 + conditions
    class_names = ['HC-Target', 'HC-Standard', 'HC-Novelty', 'PD-Target', 'PD-Standard', 'PD-Novelty']
    nb_classes = 6
    
    # Check if model expects different number of classes
    if model_output_classes != nb_classes:
        print(f"WARNING: Model has {model_output_classes} output classes but data has {nb_classes} classes")
        print(f"Adjusting to match model output...")
        if model_output_classes == 2:
            # Model was trained for binary (HC vs PD), use group labels
            combined_labels = groups
            class_names = ["HC", "PD"]
            nb_classes = 2
        elif model_output_classes == 3:
            # Model was trained for conditions only
            combined_labels = conditions
            class_names = ["Target", "Standard", "Novelty"]
            nb_classes = 3
    
    print(f"Using {nb_classes}-class mode: {class_names}")
    
    # -------------------------------------------------------------------------
    # 4. Split Data (Same as training)
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    
    train_subs, temp_subs = train_test_split(unique_subjects, test_size=0.4, random_state=42)
    val_subs, test_subs = train_test_split(temp_subs, test_size=0.5, random_state=42)
    
    test_mask = np.isin(subject_ids, test_subs)
    X_test_all = X[test_mask]
    y_test_all = combined_labels[test_mask]  # Use the combined labels (group × condition)
    
    # Extract and sanitize test dataset names for all test samples
    all_test_dataset_names = []
    test_indices = np.where(test_mask)[0]
    for idx in test_indices:
        name = dataset_names[idx] if idx < len(dataset_names) else f"Sample_{len(all_test_dataset_names)}"
        # Sanitize name: remove special characters that could break JSON
        if isinstance(name, str):
            name = name.replace('\\', '/').replace('"', "'")
        else:
            name = str(name)
        all_test_dataset_names.append(name)
    
    # Balanced sampling: equal number of samples per unique label (automatic)
    print(f"\\nApplying balanced sampling automatically...")
    unique_labels = np.unique(y_test_all)
    
    # Find minimum samples across all labels
    min_samples_per_label = min(np.sum(y_test_all == label) for label in unique_labels)
    print(f"Minimum samples per label: {min_samples_per_label}")
    
    balanced_indices = []
    for label in unique_labels:
        label_indices = np.where(y_test_all == label)[0]
        # Use all available samples up to min_samples_per_label for balanced classes
        sampled_indices = np.random.choice(label_indices, size=min_samples_per_label, replace=False)
        balanced_indices.extend(sampled_indices)
        label_name = class_names[label] if label < len(class_names) else f"Class_{label}"
        print(f"  {label_name}: {min_samples_per_label} samples")
    
    balanced_indices = np.array(balanced_indices)
    np.random.shuffle(balanced_indices)  # Shuffle to mix labels
    
    X_test = X_test_all[balanced_indices]
    y_test = y_test_all[balanced_indices]
    test_dataset_names = [all_test_dataset_names[i] for i in balanced_indices]
    print(f"Total balanced test samples: {len(X_test)}")
    
    if X_test.ndim == 3:
        X_test = X_test[..., np.newaxis]
    
    # Validate test labels before conversion
    if np.max(y_test) >= nb_classes or np.min(y_test) < 0:
        print(f"Error: Invalid test labels. Range: {np.min(y_test)} to {np.max(y_test)}, but nb_classes={nb_classes}")
        sys.exit(1)
    
    y_test_cat = to_categorical(y_test, num_classes=nb_classes)
    
    print(f"\nTest Set: {X_test.shape} samples ({len(test_subs)} subjects)")
    
    # -------------------------------------------------------------------------
    # 5. Evaluate Model
    # -------------------------------------------------------------------------
    print("\nEvaluating on Test Set...")
    test_loss, test_accuracy = model.evaluate(X_test, y_test_cat, verbose=0)
    
    # Get predictions
    y_pred = model.predict(X_test, verbose=0)
    y_pred_classes = np.argmax(y_pred, axis=1)
    y_pred_confidence = np.max(y_pred, axis=1)  # Confidence score for each prediction
    
    # Build per-sample results for the UI
    per_sample_results = []
    for i in range(len(X_test)):
        sample_result = {
            "index": i,
            "dataset_name": test_dataset_names[i] if i < len(test_dataset_names) else f"Sample_{i}",
            "predicted_class": int(y_pred_classes[i]),
            "predicted_label": class_names[y_pred_classes[i]] if y_pred_classes[i] < len(class_names) else f"Class_{y_pred_classes[i]}",
            "actual_class": int(y_test[i]),
            "actual_label": class_names[y_test[i]] if y_test[i] < len(class_names) else f"Class_{y_test[i]}",
            "confidence": float(y_pred_confidence[i]),
            "is_correct": bool(y_pred_classes[i] == y_test[i]),
            "probabilities": {class_names[j] if j < len(class_names) else f"Class_{j}": float(y_pred[i][j]) for j in range(nb_classes)}
        }
        per_sample_results.append(sample_result)
    
    # Per-class accuracy
    class_accuracies = {}
    for i in range(nb_classes):
        mask = y_test == i
        if np.sum(mask) > 0:
            class_acc = np.mean(y_pred_classes[mask] == y_test[mask])
            class_accuracies[class_names[i] if i < len(class_names) else f"Class_{i}"] = class_acc
    
    # -------------------------------------------------------------------------
    # 5. Print Results
    # -------------------------------------------------------------------------
    print("\n" + "="*60)
    print("TEST SET RESULTS")
    print("="*60)
    print(f"Test Accuracy: {test_accuracy * 100:.2f}%")
    print(f"Test Loss:     {test_loss:.4f}")
    print("\nPer-Class Accuracy:")
    for class_name, acc in class_accuracies.items():
        print(f"  {class_name}: {acc * 100:.2f}%")
    print("="*60)
    
    # Ensure all strings in dataset_names are properly encoded
    sanitized_dataset_names = [str(name) for name in test_dataset_names]
    
    # Helper function to sanitize values for JSON (handle NaN, Inf)
    def sanitize_for_json(val):
        if isinstance(val, float):
            if np.isnan(val) or np.isinf(val):
                return None
        return val
    
    # Sanitize per-sample results
    sanitized_per_sample = []
    for sample in per_sample_results:
        sanitized_sample = {}
        for k, v in sample.items():
            if isinstance(v, dict):
                sanitized_sample[k] = {sk: sanitize_for_json(sv) for sk, sv in v.items()}
            else:
                sanitized_sample[k] = sanitize_for_json(v)
        sanitized_per_sample.append(sanitized_sample)
    
    result = {
        "test_accuracy": sanitize_for_json(float(test_accuracy)),
        "test_loss": sanitize_for_json(float(test_loss)),
        "class_accuracies": {k: sanitize_for_json(float(v)) for k, v in class_accuracies.items()},
        "num_test_samples": int(len(X_test)),
        "num_test_subjects": int(len(test_subs)),
        "dataset_names": sanitized_dataset_names,
        "condition_names": class_names[:nb_classes],
        "per_sample_results": sanitized_per_sample,
        "classification_mode": f"{nb_classes}-class"
    }
    
    # Output JSON on a single line with ensure_ascii for safe parsing
    json_output = json.dumps(result, ensure_ascii=True, separators=(',', ':'))
    print("\nJSON_RESULT:" + json_output)
    sys.stdout.flush()  # Ensure output is flushed

if __name__ == "__main__":
    main()
