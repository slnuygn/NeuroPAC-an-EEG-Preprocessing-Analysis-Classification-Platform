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
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

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
except ImportError:
    from core.preprocess_bridge import PreprocessBridge


def main():
    if len(sys.argv) < 3:
        print("Usage: python load_samples.py <analysis_mode> <data_folder>")
        sys.exit(1)
    
    analysis_mode = sys.argv[1]
    data_folder = sys.argv[2]
    
    print(f"Loading TEST samples for {analysis_mode} analysis...")
    print(f"Data folder: {data_folder}")
    
    # Analysis type mapping
    analysis_type_map = {
        'erp': 'erp',
        'tf': 'time_frequency',
        'it': 'intertrial_coherence'
    }
    analysis_type = analysis_type_map.get(analysis_mode, 'erp')
    
    # Load ALL data first
    bridge = PreprocessBridge(data_folder=data_folder)
    
    try:
        X, y = bridge.load_and_transform(analysis_type, "eeg_inception")
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
    group_names = ["HC", "PD"]
    
    # Build combined labels (same as training)
    combined_labels = groups * 3 + conditions
    class_names = ['HC-Target', 'HC-Standard', 'HC-Novelty', 'PD-Target', 'PD-Standard', 'PD-Novelty']
    
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
    
    print(f"Test samples: {len(test_indices)}")
    
    # Build sample list from TEST split only
    samples = []
    for idx in test_indices:
        label_idx = combined_labels[idx]
        label_name = class_names[label_idx] if label_idx < len(class_names) else f"Class_{label_idx}"
        
        sample_name = dataset_names[idx] if idx < len(dataset_names) else f"Sample_{idx}"
        if isinstance(sample_name, str):
            sample_name = sample_name.replace('\\', '/').replace('"', "'")
        else:
            sample_name = str(sample_name)
        
        samples.append({
            "index": int(idx),  # Original index in full dataset (needed for classify_sample.py)
            "name": sample_name,
            "label": label_name,  # Hidden from user until prediction
            "group": group_names[groups[idx]] if groups[idx] < len(group_names) else f"Group_{groups[idx]}",
            "condition": condition_names[conditions[idx]] if conditions[idx] < len(condition_names) else f"Cond_{conditions[idx]}"
        })
    
    print(f"Found {len(samples)} TEST samples")
    print("JSON_SAMPLES:" + json.dumps(samples, ensure_ascii=True))


if __name__ == "__main__":
    main()
