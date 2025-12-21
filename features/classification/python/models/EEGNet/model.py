import torch
import torch.nn as nn
import torch.nn.functional as F

class EEGNet(nn.Module):
    """
    EEGNet: A Compact Convolutional Neural Network for EEG-based Brain-Computer Interfaces.
    Optimized for ERP data with 12 channels and 500 timepoints.
    """
    def __init__(self, num_classes=3, chans=12, samples=500, dropout_rate=0.5, kern_length=64, f1=8, d=2, f2=16):
        super(EEGNet, self).__init__()
        
        # Block 1: Temporal & Spatial Convolution
        # Temporal Convolution (Frequency filters)
        self.conv1 = nn.Conv2d(1, f1, (1, kern_length), padding=(0, kern_length // 2), bias=False)
        self.batchnorm1 = nn.BatchNorm2d(f1)
        
        # Depthwise Convolution (Spatial filters)
        self.depthwise = nn.Conv2d(f1, f1 * d, (chans, 1), groups=f1, bias=False)
        self.batchnorm2 = nn.BatchNorm2d(f1 * d)
        self.pooling1 = nn.AvgPool2d((1, 4))
        
        # Block 2: Separable Convolution
        self.separable = nn.Conv2d(f1 * d, f2, (1, 16), padding=(0, 8), groups=f2, bias=False)
        self.batchnorm3 = nn.BatchNorm2d(f2)
        self.pooling2 = nn.AvgPool2d((1, 8))
        
        self.dropout = nn.Dropout(dropout_rate)
        
        # Calculate Flatten Feature Size based on input dimensions
        # Pooling 1 (/4) and Pooling 2 (/8) = total reduction of 32
        self.feature_size = f2 * (samples // 32)
        self.classifier = nn.Linear(self.feature_size, num_classes)

    def forward(self, x):
        # Input shape: (Batch, 1, 12, 500)
        x = self.conv1(x)
        x = self.batchnorm1(x)
        
        x = self.depthwise(x)
        x = self.batchnorm2(x)
        x = F.elu(x)
        x = self.pooling1(x)
        x = self.dropout(x)
        
        x = self.separable(x)
        x = self.batchnorm3(x)
        x = F.elu(x)
        x = self.pooling2(x)
        x = self.dropout(x)
        
        x = torch.flatten(x, 1)
        x = self.classifier(x)
        return x