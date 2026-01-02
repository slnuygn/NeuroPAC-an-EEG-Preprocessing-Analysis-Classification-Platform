"""
Results Generator: Creates JSON reports and matplotlib visualizations for classification results.
"""
import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime


def create_results_folder(data_folder):
    """No-op: results folders are disabled by request."""
    return data_folder


def save_metrics_json(results_folder, classifier_name, analysis_name, metrics_dict):
    """No-op: metrics writing disabled."""
    return None


def generate_confusion_matrix_plot(results_folder, classifier_name, analysis_name, 
                                   y_true, y_pred, class_names=None, timestamp=None):
    """No-op: plotting disabled."""
    return None


def generate_training_history_plot(results_folder, classifier_name, analysis_name, 
                                   history_dict, timestamp=None):
    """No-op: plotting disabled."""
    return None


def generate_class_metrics_plot(results_folder, classifier_name, analysis_name, 
                                metrics_per_class, timestamp=None):
    """No-op: plotting disabled."""
    return None
