import os
import sys
import json
import numpy as np
import warnings
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import load_model
from tensorflow.keras import backend as K

# Suppress warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*oneDNN custom operations.*')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

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
    from features.classification.python.core.labels import labels as group_list
except ImportError as e:
    try:
        from core.preprocess_bridge import PreprocessBridge
        from core.labels import labels as group_list
    except ImportError as e2:
        print(f"Error importing PreprocessBridge: {e2}")
        sys.exit(1)

# Set image data format to channels_last
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
    
    # Auto-detect weights path if not provided
    if len(sys.argv) > 3:
        weights_path = sys.argv[3]
    else:
        weights_filename = f"EEGNet_{analysis_mode}_weights_best.keras"
        weights_path = os.path.join(data_folder, weights_filename)
    
    print(f"Testing EEGNet with {analysis_mode} analysis")
    print(f"Data folder: {data_folder}")
    print(f"Weights file: {weights_path}")
    
    if not os.path.exists(weights_path):
        print(f"Error: Weights file not found at {weights_path}")
        sys.exit(1)
    
    # -------------------------------------------------------------------------
    # 2. Load Data
    # -------------------------------------------------------------------------
    print("\nInitializing PreprocessBridge...")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print(f"Loading {analysis_mode} data...")
    try:
        X, y = bridge.load_and_transform(analysis_mode, "eeg_net")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    print(f"Data Loaded. Shape: {X.shape}")
    
    # Transpose to (Batch, Channels, Time, 1)
    X = np.transpose(X, (0, 2, 3, 1))
    print(f"Transposed Shape: {X.shape}")
    
    conditions = y['condition']
    groups = y['group']
    subject_ids = y['subject_id']
    group_count = len(group_list)

    valid_group_mask = np.isin(groups, np.arange(group_count))
    if not np.all(valid_group_mask):
        dropped = np.sum(~valid_group_mask)
        print(f"Warning: Dropping {dropped} samples with invalid group ids")
    conditions = conditions[valid_group_mask]
    groups = groups[valid_group_mask]
    subject_ids = subject_ids[valid_group_mask]
    X = X[valid_group_mask]

    combined_labels = conditions * group_count + groups
    nb_classes = len(np.unique(combined_labels))
    if nb_classes <= 1:
        print("Error: Need at least two combined classes to evaluate.")
        sys.exit(1)
    
    # -------------------------------------------------------------------------
    # 3. Split Data (Same as training - MUST use same random_state!)
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)

    if len(unique_subjects) == 0:
        print("Error: No subjects found in the dataset.")
        sys.exit(1)

    if len(unique_subjects) < 3:
        # Not enough subjects to perform train/val/test split; evaluate on all
        print(f"Warning: Only {len(unique_subjects)} subject(s) available; using all samples for testing.")
        test_subs = unique_subjects
    else:
        # Use same split as training
        train_subs, temp_subs = train_test_split(unique_subjects, test_size=0.4, random_state=42)
        val_subs, test_subs = train_test_split(temp_subs, test_size=0.5, random_state=42)

    test_mask = np.isin(subject_ids, test_subs)
    X_test = X[test_mask]
    y_test_combined = combined_labels[test_mask]
    y_test_cat = to_categorical(y_test_combined, num_classes=nb_classes)
    test_groups = groups[test_mask]
    group_name_lookup = {idx: name for idx, name in enumerate(group_list)}
    group_counts = {}
    for g in np.unique(test_groups):
        name = group_name_lookup.get(g, f"group_{g}")
        group_counts[name] = int(np.sum(test_groups == g))
    subject_group_labels = [
        {
            "subject_id": int(sub_id),
            "label": group_name_lookup.get(group_val, f"group_{group_val}")
        }
        for sub_id, group_val in zip(subject_ids[test_mask], test_groups)
    ]
    
    print(f"\nTest Set: {X_test.shape} samples ({len(test_subs)} subjects)")
    
    # -------------------------------------------------------------------------
    # 4. Load Model and Evaluate
    # -------------------------------------------------------------------------
    print(f"\nLoading model from {weights_path}...")
    model = load_model(weights_path)
    
    print("\nEvaluating on Test Set...")
    test_loss, test_accuracy = model.evaluate(X_test, y_test_cat, verbose=0)
    
    # Get predictions for detailed analysis
    y_pred = model.predict(X_test, verbose=0)
    y_pred_classes = np.argmax(y_pred, axis=1)
    
    # Calculate per-class accuracy for combined condition+group
    class_accuracies = {}
    condition_names = ["Target", "Standard", "Novelty"]
    for cls_id in np.unique(y_test_combined):
        mask = y_test_combined == cls_id
        if np.sum(mask) == 0:
            continue
        class_acc = np.mean(y_pred_classes[mask] == y_test_combined[mask])
        cond_idx = int(cls_id // group_count)
        grp_idx = int(cls_id % group_count)
        cond_name = condition_names[cond_idx] if cond_idx < len(condition_names) else f"condition_{cond_idx}"
        grp_name = group_name_lookup.get(grp_idx, f"group_{grp_idx}")
        class_accuracies[f"{cond_name}-{grp_name}"] = class_acc
    
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

    print("\nGroup label distribution in test set:")
    for name, count in group_counts.items():
        print(f"  {name}: {count} samples")
    
    # Output JSON for programmatic parsing
    result = {
        "test_accuracy": float(test_accuracy),
        "test_loss": float(test_loss),
        "class_accuracies": {k: float(v) for k, v in class_accuracies.items()},
        "num_test_samples": int(len(X_test)),
        "num_test_subjects": int(len(test_subs)),
        "group_counts": group_counts,
        "subject_group_labels": subject_group_labels
    }
    print("\nJSON_RESULT:" + json.dumps(result))

if __name__ == "__main__":
    main()
