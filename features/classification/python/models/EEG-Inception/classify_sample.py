"""
Classify a single sample using the saved model.
Returns JSON with the classification result.
"""
import os
import sys
import json
import warnings
import importlib.util

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

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
except ImportError:
    from core.preprocess_bridge import PreprocessBridge

# Import focal_loss using importlib to handle hyphenated module name
focal_loss = None
try:
    # Try to load model_tf from the same directory
    spec = importlib.util.spec_from_file_location("model_tf", os.path.join(current_dir, "model_tf.py"))
    if spec and spec.loader:
        model_tf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_tf)
        focal_loss = model_tf.focal_loss
except Exception as e:
    print(f"Warning: Could not load focal_loss: {e}")
    focal_loss = None

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
    print(f"Model: EEG-Inception, Analysis: {analysis_mode}")
    
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
    
    # Load data
    bridge = PreprocessBridge(data_folder=data_folder)
    
    try:
        X, y = bridge.load_and_transform(analysis_type, "eeg_inception")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    
    if sample_index < 0 or sample_index >= len(X):
        print(f"Error: Sample index {sample_index} out of range (0-{len(X)-1})")
        sys.exit(1)
    
    # Reshape data based on analysis type
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
            b, d1, d2, d3 = X.shape
            if d1 > d2 > d3:
                pass  # Already correct
            elif d3 > d2 > d1:
                X = np.transpose(X, (0, 3, 2, 1))
            elif d1 < min(d2, d3):
                X = np.transpose(X, (0, 2, 3, 1))
        elif X.ndim == 3:
            X = X[..., np.newaxis]
    else:
        if X.ndim == 3:
            X = X[..., np.newaxis]
    
    # Get the single sample
    X_sample = X[sample_index:sample_index+1]
    
    conditions = y['condition']
    groups = y['group']
    dataset_names = y['dataset_name']
    
    # Build class names
    condition_names = ["Target", "Standard", "Novelty"]
    group_names = ["HC", "PD"]
    class_names = ['HC-Target', 'HC-Standard', 'HC-Novelty', 'PD-Target', 'PD-Standard', 'PD-Novelty']
    
    # Get actual label
    combined_label = groups[sample_index] * 3 + conditions[sample_index]
    actual_label = class_names[combined_label] if combined_label < len(class_names) else f"Class_{combined_label}"
    
    # Load model
    print("Loading model...")
    custom_objects = {}
    if focal_loss is not None:
        # Register the focal_loss function factory so it can be deserialized
        custom_objects['focal_loss_fixed'] = focal_loss(gamma=4.0, alpha=0.5)
    
    model = load_model(weights_path, custom_objects=custom_objects)
    
    # Check model output classes
    model_output_classes = model.output_shape[-1]
    nb_classes = model_output_classes
    
    # Adjust class names if model has different output
    if model_output_classes == 2:
        class_names = ["HC", "PD"]
        actual_label = group_names[groups[sample_index]]
    elif model_output_classes == 3:
        class_names = ["Target", "Standard", "Novelty"]
        actual_label = condition_names[conditions[sample_index]]
    
    # Make prediction
    print("Running inference...")
    prediction = model.predict(X_sample, verbose=0)
    predicted_class = np.argmax(prediction[0])
    confidence = float(np.max(prediction[0]))
    predicted_label = class_names[predicted_class] if predicted_class < len(class_names) else f"Class_{predicted_class}"
    
    # Build probabilities dict
    probabilities = {}
    for i, class_name in enumerate(class_names):
        if i < len(prediction[0]):
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
