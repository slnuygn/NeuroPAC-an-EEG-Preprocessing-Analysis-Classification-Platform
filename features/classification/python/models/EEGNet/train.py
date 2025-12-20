import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable

from model import EEGNet
from inference import evaluate
from data_loader import load_data


def train_model(epochs=10, batch_size=32):
    # Load data
    X_train, y_train, X_val, y_val, X_test, y_test = load_data()

    if X_train is None:
        print("Data not loaded. Please implement load_data in data_loader.py")
        return

    # Initialize model, criterion, optimizer
    net = EEGNet().cuda(0)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(net.parameters())

    for epoch in range(epochs):  # loop over the dataset multiple times
        print("\nEpoch ", epoch)

        running_loss = 0.0
        for i in range(len(X_train)//batch_size - 1):
            s = i*batch_size
            e = i*batch_size+batch_size

            inputs = torch.from_numpy(X_train[s:e])
            labels = torch.FloatTensor(np.array([y_train[s:e]]).T*1.0)

            # wrap them in Variable
            inputs, labels = Variable(inputs.cuda(0)), Variable(labels.cuda(0))

            # zero the parameter gradients
            optimizer.zero_grad()

            # forward + backward + optimize
            outputs = net(inputs)
            loss = criterion(outputs, labels)
            loss.backward()

            optimizer.step()

            running_loss += loss.item()

        # Validation accuracy
        params = ["acc", "auc", "fmeasure"]
        print(params)
        print("Training Loss ", running_loss)
        print("Train - ", evaluate(net, X_train, y_train, params))
        print("Validation - ", evaluate(net, X_val, y_val, params))
        print("Test - ", evaluate(net, X_test, y_test, params))

    return net