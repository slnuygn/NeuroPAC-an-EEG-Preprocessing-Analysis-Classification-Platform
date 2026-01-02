"""
Classify a single sample using the saved model.
Returns JSON with the classification result.
"""
import os
import sys
import json
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

import numpy as np
import joblib

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
    if len(sys.argv) < 5:
        print("Usage: python classify_sample.py <analysis_mode> <data_folder> <weights_path> <sample_index>")
        sys.exit(1)
    
    analysis_mode = sys.argv[1]
    data_folder = sys.argv[2]
    weights_path = sys.argv[3]
    sample_index = int(sys.argv[4])
    
    print(f"Classifying sample {sample_index}...")
    print(f"Model: Riemannian, Analysis: {analysis_mode}")
    
    if not os.path.exists(weights_path):
        print(f"Error: Weights file not found at {weights_path}")
        sys.exit(1)
    
    # Load data
    bridge = PreprocessBridge(data_folder=data_folder)
    
    try:
        X, y_meta = bridge.load_and_transform(analysis_mode, "riemannian")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    if sample_index < 0 or sample_index >= len(X):
        print(f"Error: Sample index {sample_index} out of range (0-{len(X)-1})")
        sys.exit(1)
    
    # Get the single sample
    X_sample = X[sample_index:sample_index+1]
    
    conditions = y_meta['condition']
    dataset_names = y_meta['dataset_name']
    
    # Build class names
    condition_names = ["Target", "Standard", "Novelty"]
    
    # Get actual label
    cond_idx = conditions[sample_index]
    actual_label = condition_names[cond_idx] if cond_idx < len(condition_names) else f"Class_{cond_idx}"
    
    # Load model
    print("Loading model...")
    clf = joblib.load(weights_path)
    
    # Make prediction
    print("Running inference...")
    predicted_class = clf.predict(X_sample)[0]
    predicted_label = condition_names[predicted_class] if predicted_class < len(condition_names) else f"Class_{predicted_class}"
    
    # Get probabilities if available
    probabilities = {}
    try:
        proba = clf.predict_proba(X_sample)[0]
        confidence = float(np.max(proba))
        for i, class_name in enumerate(condition_names):
            if i < len(proba):
                probabilities[class_name] = float(proba[i])
    except:
        confidence = 1.0 if predicted_label == actual_label else 0.0
        for i, class_name in enumerate(condition_names):
            probabilities[class_name] = 1.0 if i == predicted_class else 0.0
    
    sample_name = dataset_names[sample_index] if sample_index < len(dataset_names) else f"Sample_{sample_index}"
    if isinstance(sample_name, str):
        sample_name = sample_name.replace('\\', '/').replace('"', "'")
    else:
        sample_name = str(sample_name)
    
    result = {
        "sample_index": sample_index,
        "sample_name": sample_name,
        "predicted_label": predicted_label,
        "predicted_class": int(predicted_class),
        "actual_label": actual_label,
        "confidence": confidence,
        "is_correct": predicted_label == actual_label,
        "probabilities": probabilities
    }
    
    print(f"Prediction: {predicted_label} (confidence: {confidence*100:.1f}%)")
    print(f"Actual: {actual_label}")
    print(f"Result: {'CORRECT' if result['is_correct'] else 'INCORRECT'}")
    
    print("JSON_CLASSIFICATION:" + json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
