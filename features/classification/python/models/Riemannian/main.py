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

try:
    from .model import create_riemannian_pipeline, get_default_config
except ImportError:
    from model import create_riemannian_pipeline, get_default_config


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
    
    # Determine which analysis type to use
    # Options: 'spectral' or 'connectivity'
    analysis_type = 'spectral'
    if len(sys.argv) > 1:
        analysis_type = sys.argv[1]
    
    # Override data folder if provided as command line argument
    if len(sys.argv) > 2:
        data_folder = sys.argv[2]
        print(f"Using data folder from argument: {data_folder}")
    
    # Map analysis types for config files
    # spectral -> spectral_config.json
    # connectivity -> connectivity_config.json
    config_file = f"{analysis_type}_config.json"
    config_path = os.path.join(current_dir, "configs", config_file)
    
    print(f"Using configuration: {config_file}")
    config = load_config(config_path)
    
    # Merge with defaults
    default_config = get_default_config()
    for key, value in default_config.items():
        if key not in config:
            config[key] = value
    
    # Extract hyperparameters
    estimator = config.get('estimator', 'scm')
    metric = config.get('metric', 'riemann')
    kernel = config.get('kernel', 'linear')
    C = config.get('C', 1.0)
    use_mdm = config.get('use_mdm', False)
    test_size = config.get('test_size', 0.3)
    random_state = config.get('random_state', 42)
    
    # -------------------------------------------------------------------------
    # 2. Load Data using Bridge
    # -------------------------------------------------------------------------
    print("Initializing PreprocessBridge...")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print(f"Loading {analysis_type} data for Riemannian...")
    try:
        # Bridge returns data in format (n_trials, n_channels, n_features)
        # spectral: (n_trials, 12, 15)
        # connectivity: (n_trials, 12, 12)
        X, y_meta = bridge.load_and_transform(analysis_type, "riemannian")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
        return
    
    print(f"Data Loaded. Shape: {X.shape}")
    
    # Extract labels and subject IDs
    y = y_meta['condition']  # 0: Target, 1: Standard, 2: Novelty
    subject_ids = y_meta['subject_id']
    
    # -------------------------------------------------------------------------
    # 3. Subject-Wise Split
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    print(f"Total unique subjects found: {len(unique_subjects)}")
    
    train_subs, test_subs = train_test_split(
        unique_subjects, 
        test_size=test_size, 
        random_state=random_state
    )
    
    print(f"Training Subjects: {len(train_subs)}")
    print(f"Test Subjects: {len(test_subs)}")
    
    train_mask = np.isin(subject_ids, train_subs)
    test_mask = np.isin(subject_ids, test_subs)
    
    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    
    print("-" * 30)
    print(f"Training Set:   {X_train.shape} samples")
    print(f"Test Set:       {X_test.shape} samples")
    print("-" * 30)
    
    # -------------------------------------------------------------------------
    # 4. Model Initialization & Training
    # -------------------------------------------------------------------------
    print("Initializing Riemannian Pipeline...")
    clf = create_riemannian_pipeline(
        estimator=estimator,
        metric=metric,
        kernel=kernel,
        C=C,
        use_mdm=use_mdm
    )
    
    print("Pipeline Steps:")
    for step_name, step_obj in clf.steps:
        print(f"  - {step_name}: {step_obj.__class__.__name__}")
    
    print("\nStarting Training...")
    clf.fit(X_train, y_train)
    
    # Evaluate
    train_accuracy = clf.score(X_train, y_train)
    test_accuracy = clf.score(X_test, y_test)
    
    print(f"Training Accuracy: {train_accuracy * 100:.2f}%")
    print(f"Test Accuracy:     {test_accuracy * 100:.2f}%")
    
    # -------------------------------------------------------------------------
    # 5. Save the Pipeline in data folder with naming: Riemannian_{analysis}_weights_best.pkl
    # -------------------------------------------------------------------------
    os.makedirs(data_folder, exist_ok=True)
    weights_filename = f"Riemannian_{analysis_type}_weights_best.pkl"
    weight_path = os.path.join(data_folder, weights_filename)
    joblib.dump(clf, weight_path)
    print(f"\nModel saved to: {weight_path}")


if __name__ == "__main__":
    main()

