"""
Load available TEST samples (from the test split) without classifying them.
Returns a JSON list of samples with their metadata.
Uses the same train/val/test split as the training script (random_state=42).
"""
import os
import sys
import json
import warnings

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore', category=FutureWarning)

import numpy as np
from sklearn.model_selection import train_test_split

# Path Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
python_root = os.path.abspath(os.path.join(current_dir, "../../"))
capstone_root = os.path.abspath(os.path.join(current_dir, "../../../../.."))

if python_root not in sys.path:
    sys.path.insert(0, python_root)
if capstone_root not in sys.path:
    sys.path.insert(0, capstone_root)

try:
    from features.classification.python.core.preprocess_bridge import PreprocessBridge
    from features.classification.python.core.labels import labels as group_list
except ImportError:
    from core.preprocess_bridge import PreprocessBridge
    from core.labels import labels as group_list


def main():
    if len(sys.argv) < 3:
        print("Usage: python load_samples.py <analysis_mode> <data_folder>")
        sys.exit(1)
    
    analysis_mode = sys.argv[1]
    data_folder = sys.argv[2]
    
    print(f"Loading TEST samples for {analysis_mode} analysis...")
    print(f"Data folder: {data_folder}")
    
    # Load ALL data first
    bridge = PreprocessBridge(data_folder=data_folder)
    
    try:
        X, y = bridge.load_and_transform(analysis_mode, "eeg_net")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    print(f"Total data loaded. Shape: {X.shape}")
    
    conditions = y['condition']
    groups = y['group']
    subject_ids = y['subject_id']
    dataset_names = y['dataset_name']
    
    # Build class names
    condition_names = ["Target", "Standard", "Novelty"]
    group_count = len(group_list)
    
    # -------------------------------------------------------------------------
    # Apply the SAME train/val/test split as training (random_state=42)
    # -------------------------------------------------------------------------
    unique_subjects = np.unique(subject_ids)
    print(f"Total subjects: {len(unique_subjects)}")
    
    # Same split ratios and random_state as training
    train_subs, temp_subs = train_test_split(unique_subjects, test_size=0.4, random_state=42)
    val_subs, test_subs = train_test_split(temp_subs, test_size=0.5, random_state=42)
    
    print(f"Train subjects: {len(train_subs)}, Val subjects: {len(val_subs)}, Test subjects: {len(test_subs)}")
    
    # Get only TEST samples
    test_mask = np.isin(subject_ids, test_subs)
    test_indices = np.where(test_mask)[0]
    
    # Filter valid samples
    valid_mask = np.isin(groups, np.arange(group_count)) & np.isin(conditions, np.arange(3))
    
    print(f"Test samples: {len(test_indices)}")
    
    # Build sample list from TEST split only
    samples = []
    for idx in test_indices:
        if not valid_mask[idx]:
            continue
            
        cond_idx = conditions[idx]
        grp_idx = groups[idx]
        
        cond_name = condition_names[cond_idx] if cond_idx < len(condition_names) else f"Cond_{cond_idx}"
        grp_name = group_list[grp_idx] if grp_idx < len(group_list) else f"Group_{grp_idx}"
        label_name = f"{cond_name}-{grp_name}"
        
        sample_name = dataset_names[idx] if idx < len(dataset_names) else f"Sample_{idx}"
        if isinstance(sample_name, str):
            sample_name = sample_name.replace('\\', '/').replace('"', "'")
        else:
            sample_name = str(sample_name)
        
        samples.append({
            "index": int(idx),  # Original index in full dataset (needed for classify_sample.py)
            "name": sample_name,
            "label": label_name,  # Hidden from user until prediction
            "group": grp_name,
            "condition": cond_name
        })
    
    print(f"Found {len(samples)} TEST samples")
    print("JSON_SAMPLES:" + json.dumps(samples, ensure_ascii=True))


if __name__ == "__main__":
    main()
