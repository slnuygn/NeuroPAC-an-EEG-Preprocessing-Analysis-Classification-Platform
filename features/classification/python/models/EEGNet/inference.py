import torch
import numpy as np
import json
import os
from sklearn.metrics import accuracy_score, recall_score, precision_score, f1_score
# Relative import from the same directory
from .model import EEGNet

class ERPInference:
    """
    A modular class to handle loading trained weights and performing 
    predictions or evaluations using EEGNet.
    """
    def __init__(self, weight_path="models/eegnet/weights/erp_model.pth", 
                 config_path="models/eegnet/configs/erp_config.json"):
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 1. Load Config to get architecture parameters
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {"dropout": 0.5}

        # 2. Initialize Model Architecture
        # Note: chans and samples are hardcoded to your project defaults (12, 500)
        # but can be made dynamic if needed.
        self.model = EEGNet(
            num_classes=3,
            chans=12,
            samples=500,
            dropout_rate=self.config.get("dropout", 0.5)
        ).to(self.device)

        # 3. Load Trained Weights
        if os.path.exists(weight_path):
            self.model.load_state_dict(torch.load(weight_path, map_location=self.device))
            print(f"Successfully loaded weights from {weight_path}")
        else:
            print(f"Warning: No weights found at {weight_path}. Model is uninitialized.")
        
        self.model.eval()

    def predict(self, x_numpy):
        """
        Runs inference on a numpy array.
        x_numpy shape: (Batch, 1, 12, 500)
        Returns: predicted_classes, probabilities
        """
        self.model.eval()
        with torch.no_grad():
            x_tensor = torch.from_numpy(x_numpy).float().to(self.device)
            logits = self.model(x_tensor)
            probs = torch.softmax(logits, dim=1)
            preds = torch.argmax(probs, dim=1)
            
        return preds.cpu().numpy(), probs.cpu().numpy()

    def evaluate(self, X_test, y_test):
        """
        Replaces your legacy 'evaluate' function with modern metrics.
        Returns a dictionary of results.
        """
        preds, probs = self.predict(X_test)
        
        results = {
            "accuracy": accuracy_score(y_test, preds),
            "precision": precision_score(y_test, preds, average='weighted'),
            "recall": recall_score(y_test, preds, average='weighted'),
            "f1_measure": f1_score(y_test, preds, average='weighted')
        }
        
        return results