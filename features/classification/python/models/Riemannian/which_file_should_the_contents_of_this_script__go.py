import os
import sys
import numpy as np
import json
import joblib
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler

# Authentic pyRiemann imports as per official documentation/GitHub
from pyriemann.estimation import Covariances
from pyriemann.tangentmap import TangentSpace
from pyriemann.classification import MDM

# Path Setup to reach core.preprocess_bridge
current_dir = os.path.dirname(os.path.abspath(__file__))
python_root = os.path.abspath(os.path.join(current_dir, "../../"))
if python_root not in sys.path:
    sys.path.append(python_root)

from core.preprocess_bridge import PreprocessBridge

def run_riemannian_analysis(analysis_type="spectral"):
    """
    Authentic pyRiemann implementation for Spectral or Connectivity data.
    analysis_type: "spectral" (12x15) or "connectivity" (12x12)
    """
    # 1. Load Data
    data_folder = os.path.join(python_root, "data")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print(f"--- Starting Riemannian Analysis: {analysis_type.upper()} ---")
    
    # We use 'riemannian' as the target_model in the bridge
    X, y_meta = bridge.load_and_transform(analysis_type, "riemannian")
    
    # Labels and Subjects
    y = y_meta['condition']  # 0: Target, 1: Standard, 2: Novelty
    subject_ids = y_meta['subject_id']
    unique_subjects = np.unique(subject_ids)

    # 2. Subject-Wise Split (Mandatory for clinical EEG)
    train_subs, test_subs = train_test_split(unique_subjects, test_size=0.3, random_state=42)
    
    train_mask = np.isin(subject_ids, train_subs)
    test_mask = np.isin(subject_ids, test_subs)
    
    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    # 3. Authentic Riemannian Pipeline
    # pattern: Covariance -> TangentSpace -> Classifier
    # This is the 'Tangent Space Mapping' (TSM) architecture from the pyRiemann GitHub
    clf = Pipeline([
        ('cov', Covariances(estimator='scm')),        # Sample Covariance Matrix
        ('ts', TangentSpace(metric='riemann')),       # Mapping to the Tangent Space
        ('scaler', StandardScaler()),                 # Norm for the SVM
        ('svm', SVC(kernel='linear', probability=True))
    ])

    # 4. Fit and Evaluate
    print(f"Training on {len(train_subs)} subjects ({len(X_train)} samples)...")
    clf.fit(X_train, y_train)
    
    accuracy = clf.score(X_test, y_test)
    print(f"Test Accuracy: {accuracy * 100:.2f}%")

    # 5. Save the Pipeline
    os.makedirs(os.path.join(current_dir, "weights"), exist_ok=True)
    weight_path = os.path.join(current_dir, "weights", f"riemann_{analysis_type}.pkl")
    joblib.dump(clf, weight_path)
    print(f"Model saved to: {weight_path}")

if __name__ == "__main__":
    # You can change this to "connectivity" to run the connectivity analysis
    run_riemannian_analysis("spectral")