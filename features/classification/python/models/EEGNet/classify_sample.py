"""
Classify a single sample using the saved model.
Returns JSON with the classification result.
"""
import os
import sys
import json
import warnings

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore', category=FutureWarning)

import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras import backend as K

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

K.set_image_data_format('channels_last')


def main():
    if len(sys.argv) < 5:
        print("Usage: python classify_sample.py <analysis_mode> <data_folder> <weights_path> <sample_index>")
        sys.exit(1)
    
    analysis_mode = sys.argv[1]
    data_folder = sys.argv[2]
    weights_path = sys.argv[3]
    sample_index = int(sys.argv[4])
    
    print(f"Classifying sample {sample_index}...")
    print(f"Model: EEGNet, Analysis: {analysis_mode}")
    
    if not os.path.exists(weights_path):
        print(f"Error: Weights file not found at {weights_path}")
        sys.exit(1)
    
    # Load data
    bridge = PreprocessBridge(data_folder=data_folder)
    
    try:
        X, y = bridge.load_and_transform(analysis_mode, "eeg_net")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    if sample_index < 0 or sample_index >= len(X):
        print(f"Error: Sample index {sample_index} out of range (0-{len(X)-1})")
        sys.exit(1)
    
    # Transpose to (Batch, Channels, Time, 1)
    X = np.transpose(X, (0, 2, 3, 1))
    
    # Get the single sample
    X_sample = X[sample_index:sample_index+1]
    
    conditions = y['condition']
    groups = y['group']
    dataset_names = y['dataset_name']
    
    # Build class names
    condition_names = ["Target", "Standard", "Novelty"]
    group_count = len(group_list)
    
    # Build full class names list (condition × group)
    class_names = []
    for cond in condition_names:
        for grp in group_list:
            class_names.append(f"{cond}-{grp}")
    
    # Get actual label
    cond_idx = conditions[sample_index]
    grp_idx = groups[sample_index]
    combined_label = cond_idx * group_count + grp_idx
    
    cond_name = condition_names[cond_idx] if cond_idx < len(condition_names) else f"Cond_{cond_idx}"
    grp_name = group_list[grp_idx] if grp_idx < len(group_list) else f"Group_{grp_idx}"
    actual_label = f"{cond_name}-{grp_name}"
    
    # Load model
    print("Loading model...")
    model = load_model(weights_path)
    
    # Check model output classes
    model_output_classes = model.output_shape[-1]
    nb_classes = model_output_classes
    
    # Adjust class names if model has different output
    if model_output_classes != len(class_names):
        class_names = [f"Class_{i}" for i in range(model_output_classes)]
    
    # Make prediction
    print("Running inference...")
    prediction = model.predict(X_sample, verbose=0)
    predicted_class = np.argmax(prediction[0])
    confidence = float(np.max(prediction[0]))
    predicted_label = class_names[predicted_class] if predicted_class < len(class_names) else f"Class_{predicted_class}"
    
    # Build probabilities dict
    probabilities = {}
    for i in range(len(prediction[0])):
        class_name = class_names[i] if i < len(class_names) else f"Class_{i}"
        probabilities[class_name] = float(prediction[0][i])
    
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
