import numpy as np
from sklearn.metrics import roc_auc_score, precision_score, recall_score, accuracy_score
import torch
from torch.autograd import Variable


def evaluate(model, X, Y, params=["acc"]):
    results = []

    inputs = Variable(torch.from_numpy(X).cuda(0))
    predicted = model(inputs)
    predicted = predicted.data.cpu().numpy()

    for param in params:
        if param == 'acc':
            results.append(accuracy_score(Y, np.round(predicted)))
        if param == "auc":
            results.append(roc_auc_score(Y, predicted))
        if param == "recall":
            results.append(recall_score(Y, np.round(predicted)))
        if param == "precision":
            results.append(precision_score(Y, np.round(predicted)))
        if param == "fmeasure":
            precision = precision_score(Y, np.round(predicted))
            recall = recall_score(Y, np.round(predicted))
            results.append(2*precision*recall / (precision+recall))
    return results