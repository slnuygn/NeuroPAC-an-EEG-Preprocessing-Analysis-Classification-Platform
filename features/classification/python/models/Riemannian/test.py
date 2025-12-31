import os
import sys
import json
import numpy as np
import joblib
import warnings
from sklearn.model_selection import train_test_split

# Suppress warnings
warnings.filterwarnings('ignore', category=FutureWarning)

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

def main():
    # -------------------------------------------------------------------------
    # 1. Parse Arguments
    # -------------------------------------------------------------------------
    if len(sys.argv) < 2:
        print("Usage: python test.py <analysis_type> [data_folder] [weights_path]")
        print("Example: python test.py spectral /path/to/data /path/to/weights.pkl")
        sys.exit(1)
    
    analysis_type = sys.argv[1]  # 'spectral' or 'connectivity'
    data_folder = sys.argv[2] if len(sys.argv) > 2 else os.path.join(python_root, "data")
    
    # Auto-detect weights path
    if len(sys.argv) > 3:
        weights_path = sys.argv[3]
    else:
        weights_filename = f"Riemannian_{analysis_type}_weights_best.pkl"
        weights_path = os.path.join(data_folder, weights_filename)
    
    print(f"Testing Riemannian classifier with {analysis_type} analysis")
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
    
    print(f"Loading {analysis_type} data...")
    try:
        X, y_meta = bridge.load_and_transform(analysis_type, "riemannian")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    print(f"Data Loaded. Shape: {X.shape}")
    
    y = y_meta['condition']
    subject_ids = y_meta['subject_id']
    dataset_names = y_meta['dataset_name']  # Extract dataset names
    nb_classes = len(np.unique(y))
    
    # -------------------------------------------------------------------------
    # 3. Split Data (Same as training - use same random_state!)
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    random_state = 42  # Same as training
    
    train_subs, temp_subs = train_test_split(
        unique_subjects, 
        test_size=0.4, 
        random_state=random_state
    )
    val_subs, test_subs = train_test_split(
        temp_subs, 
        test_size=0.5, 
        random_state=random_state
    )
    
    test_mask = np.isin(subject_ids, test_subs)
    X_test = X[test_mask]
    y_test = y[test_mask]
    test_dataset_names = [dataset_names[i] for i in range(len(dataset_names)) if test_mask[i]]  # Extract test dataset names
    test_dataset_names = [dataset_names[i] for i in range(len(dataset_names)) if test_mask[i]]  # Extract test dataset names
    
    print(f"\nTest Set: {X_test.shape} samples ({len(test_subs)} subjects)")
    
    # -------------------------------------------------------------------------
    # 4. Load Model and Evaluate
    # -------------------------------------------------------------------------
    print(f"\nLoading model from {weights_path}...")
    clf = joblib.load(weights_path)
    
    print("\nEvaluating on Test Set...")
    test_accuracy = clf.score(X_test, y_test)
    
    # Get predictions
    y_pred = clf.predict(X_test)
    
    # Per-class accuracy
    class_accuracies = {}
    condition_names = ["Target", "Standard", "Novelty"]
    for i in range(nb_classes):
        mask = y_test == i
        if np.sum(mask) > 0:
            class_acc = np.mean(y_pred[mask] == y_test[mask])
            class_accuracies[condition_names[i]] = class_acc
    
    # -------------------------------------------------------------------------
    # 5. Print Results
    # -------------------------------------------------------------------------
    print("\n" + "="*60)
    print("TEST SET RESULTS")
    print("="*60)
    print(f"Test Accuracy: {test_accuracy * 100:.2f}%")
    print("\nPer-Class Accuracy:")
    for class_name, acc in class_accuracies.items():
        print(f"  {class_name}: {acc * 100:.2f}%")
    print("="*60)
    
    result = {
        "test_accuracy": float(test_accuracy),
        "class_accuracies": {k: float(v) for k, v in class_accuracies.items()},
        "num_test_samples": int(len(X_test)),
        "num_test_subjects": int(len(test_subs)),
        "dataset_names": test_dataset_names
    }
    print("\nJSON_RESULT:" + json.dumps(result))

if __name__ == "__main__":
    main()
