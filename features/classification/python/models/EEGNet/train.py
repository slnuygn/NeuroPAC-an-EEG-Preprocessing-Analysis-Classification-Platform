import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import json
import os

# Import the model you just put into model.py
from .model import EEGNet

def train_eegnet(X_train, y_train, X_val=None, y_val=None, config_path="models/eegnet/configs/erp_config.json"):
    """
    Modern training loop for EEGNet.
    X_train: (Batch, 1, 12, 500) numpy array
    y_train: (Batch,) numpy array of labels [0, 1, 2]
    """
    
    # 1. Load Hyperparameters from your erp_config.json
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        # Fallback defaults if config is missing
        config = {"batch_size": 16, "epochs": 50, "lr": 0.001, "dropout": 0.5}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    # 2. Initialize Model
    # We pull chans and samples directly from the data shape for robustness
    model = EEGNet(
        num_classes=3, 
        chans=X_train.shape[2], 
        samples=X_train.shape[3],
        dropout_rate=config.get("dropout", 0.5)
    ).to(device)

    # 3. Prepare DataLoaders (Modern way to handle batching)
    train_ds = TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long())
    train_loader = DataLoader(train_ds, batch_size=config['batch_size'], shuffle=True)

    if X_val is not None:
        val_ds = TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long())
        val_loader = DataLoader(val_ds, batch_size=config['batch_size'], shuffle=False)

    # 4. Loss and Optimizer
    # CrossEntropyLoss is used for multi-class (0, 1, 2)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=config['lr'])

    # 5. Training Loop
    for epoch in range(config['epochs']):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            
            # Track training accuracy
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

        train_acc = 100 * correct / total
        avg_loss = running_loss / len(train_loader)
        
        print(f"Epoch [{epoch+1}/{config['epochs']}] - Loss: {avg_loss:.4f} - Acc: {train_acc:.2f}%")

        # 6. Optional Validation Check
        if X_val is not None:
            model.eval()
            val_correct = 0
            val_total = 0
            with torch.no_grad():
                for v_inputs, v_labels in val_loader:
                    v_inputs, v_labels = v_inputs.to(device), v_labels.to(device)
                    v_outputs = model(v_inputs)
                    _, v_pred = torch.max(v_outputs.data, 1)
                    val_total += v_labels.size(0)
                    val_correct += (v_pred == v_labels).sum().item()
            print(f" >> Val Acc: {100 * val_correct / val_total:.2f}%")

    # 7. Save the trained weights
    os.makedirs("models/eegnet/weights", exist_ok=True)
    torch.save(model.state_dict(), "models/eegnet/weights/erp_model.pth")
    print("Training Complete. Weights saved to models/eegnet/weights/erp_model.pth")
    
    return model