import os
import sys
import numpy as np
from sklearn.model_selection import train_test_split

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

# Import training function
# Note: train.py uses relative imports (from .model import EEGNet).
# This script should ideally be run as a module: python -m models.EEGNet.main
try:
    from .train import train_eegnet
except ImportError:
    try:
        # Fallback if running as script, though train.py's relative import might still fail
        import train
        train_eegnet = train.train_eegnet
    except ImportError as e:
        if "attempted relative import" in str(e):
            print("\nCRITICAL ERROR: Import failed due to relative imports in train.py.")
            print("Please run this script as a module from the 'features/classification/python' directory:")
            print("  python -m models.EEGNet.main")
            sys.exit(1)
        else:
            raise e

def main():
    # -------------------------------------------------------------------------
    # 1. Configuration
    # -------------------------------------------------------------------------
    # Define where your .mat files are located. 
    # Assuming a 'data' folder in the python root or passed explicitly.
    data_folder = os.path.join(python_root, "data") 
    
    # Check if data folder exists
    if not os.path.exists(data_folder):
        print(f"Warning: Data folder not found at {data_folder}.")
        print("Please ensure your .mat files (erp_output.mat, etc.) are in the correct location.")
        # You can override this path if your data is elsewhere:
        # data_folder = "C:/Path/To/Your/Data"

    # -------------------------------------------------------------------------
    # 2. Load Data using Bridge
    # -------------------------------------------------------------------------
    print("Initializing PreprocessBridge...")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print("Loading ERP data for EEGNet...")
    try:
        # We use 'erp' analysis and 'eeg_net' model target as per bridge code
        # This ensures the data is reshaped to (Batch, 1, Channels, Time)
        X, y = bridge.load_and_transform("erp", "eeg_net")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
        return

    print(f"Data Loaded Successfully. X shape: {X.shape}")
    
    # y is a dictionary: {'condition': ..., 'group': ..., 'subject_id': ...}
    conditions = y['condition']
    subject_ids = y['subject_id']
    
    # -------------------------------------------------------------------------
    # 3. Subject-Wise Split
    # -------------------------------------------------------------------------
    # CRITICAL: We must split by Subject ID, not by trial.
    # This prevents the model from memorizing subject-specific features (Data Leakage).
    # If we just used train_test_split on X, we might get Subject 1's trials in both sets.
    
    unique_subjects = np.unique(subject_ids)
    print(f"Total unique subjects found: {len(unique_subjects)}")
    
    # Split subjects into Train and Validation sets
    train_subs, val_subs = train_test_split(unique_subjects, test_size=0.2, random_state=42)
    
    print(f"Training Subjects ({len(train_subs)}): {train_subs}")
    print(f"Validation Subjects ({len(val_subs)}): {val_subs}")
    
    # Create boolean masks for indexing the full dataset
    train_mask = np.isin(subject_ids, train_subs)
    val_mask = np.isin(subject_ids, val_subs)
    
    # Apply masks to get the actual data subsets
    X_train = X[train_mask]
    y_train = conditions[train_mask] # We train on 'condition' labels (0, 1, 2)
    
    X_val = X[val_mask]
    y_val = conditions[val_mask]
    
    print("-" * 30)
    print(f"Training Set:   {X_train.shape} samples")
    print(f"Validation Set: {X_val.shape} samples")
    print("-" * 30)
    
    # -------------------------------------------------------------------------
    # 4. Run Training
    # -------------------------------------------------------------------------
    print("Starting Training Process...")
    
    # Config path relative to this script
    config_path = os.path.join(current_dir, "configs", "erp_config.json")
    
    # Call the training function from train.py
    model = train_eegnet(X_train, y_train, X_val, y_val, config_path=config_path)
    
    print("Main process complete.")

if __name__ == "__main__":
    main()
