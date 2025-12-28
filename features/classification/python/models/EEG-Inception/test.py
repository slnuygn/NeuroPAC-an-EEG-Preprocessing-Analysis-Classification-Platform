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
    
    # Apply same reshaping as training
    if analysis_type == 'erp':
        if X.ndim == 4:
            X = np.transpose(X, (0, 3, 2, 1))
        elif X.ndim == 3:
            X = np.transpose(X, (0, 2, 1))
            X = X[..., np.newaxis]
        if X.ndim == 3:
            X = X[..., np.newaxis]
    elif analysis_type in ['time_frequency', 'intertrial_coherence']:
        if X.ndim == 4:
            b, c, f, t = X.shape
            X = X.reshape(b, c * f, t)
            X = np.transpose(X, (0, 2, 1))
        elif X.ndim == 3:
            X = np.transpose(X, (0, 2, 1))
        if X.ndim == 3:
            X = X[..., np.newaxis]
    
    if X.ndim == 3:
        X = X[..., np.newaxis]
    
    print(f"Reshaped for testing: {X.shape}")
    
    conditions = y['condition']
    subject_ids = y['subject_id']
    nb_classes = len(np.unique(conditions))
    
    # -------------------------------------------------------------------------
    # 3. Split Data (Same as training)
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    
    train_subs, temp_subs = train_test_split(unique_subjects, test_size=0.4, random_state=42)
    val_subs, test_subs = train_test_split(temp_subs, test_size=0.5, random_state=42)
    
    test_mask = np.isin(subject_ids, test_subs)
    X_test = X[test_mask]
    y_test = conditions[test_mask]
    
    if X_test.ndim == 3:
        X_test = X_test[..., np.newaxis]
    
    y_test_cat = to_categorical(y_test, num_classes=nb_classes)
    
    print(f"\nTest Set: {X_test.shape} samples ({len(test_subs)} subjects)")
    
    # -------------------------------------------------------------------------
    # 4. Load Model and Evaluate
    # -------------------------------------------------------------------------
    print(f"\nLoading model from {weights_path}...")
    model = load_model(weights_path)
    
    print("\nEvaluating on Test Set...")
    test_loss, test_accuracy = model.evaluate(X_test, y_test_cat, verbose=0)
    
    # Get predictions
    y_pred = model.predict(X_test, verbose=0)
    y_pred_classes = np.argmax(y_pred, axis=1)
    
    # Per-class accuracy
    class_accuracies = {}
    condition_names = ["Target", "Standard", "Novelty"]
    for i in range(nb_classes):
        mask = y_test == i
        if np.sum(mask) > 0:
            class_acc = np.mean(y_pred_classes[mask] == y_test[mask])
            class_accuracies[condition_names[i]] = class_acc
    
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
    
    result = {
        "test_accuracy": float(test_accuracy),
        "test_loss": float(test_loss),
        "class_accuracies": {k: float(v) for k, v in class_accuracies.items()},
        "num_test_samples": int(len(X_test)),
        "num_test_subjects": int(len(test_subs))
    }
    print("\nJSON_RESULT:" + json.dumps(result))

if __name__ == "__main__":
    main()
