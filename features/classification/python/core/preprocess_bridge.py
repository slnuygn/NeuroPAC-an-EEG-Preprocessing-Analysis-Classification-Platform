import os
import scipy.io as sio
import numpy as np

class PreprocessBridge:
    def __init__(self, data_folder="data/"):
        # You can set the path here once
        self.data_path = data_folder
        
        # Map analysis types to their actual .mat filenames
        # Files are assumed to be directly in the selected data_path folder
        self.file_map = {
            "erp": "erp_output.mat",
            "time_frequency": "timefreq_output.mat",
            "spectral": "spectral_output.mat",
            "connectivity": "channelwise_coherence_output.mat",
            "intertrial_coherence": "intertrial_coherence_output.mat"
        }

    def set_data_path(self, path):
        """
        Dynamically set the data path (e.g., from FileBrowserUI.currentFolder).
        Call this when the user changes the folder in the UI.
        """
        self.data_path = path

    def load_and_transform(self, analysis_type, target_model, data_path=None):
        """
        The main function your UI will call.
        If data_path is provided, uses it; otherwise uses self.data_path (set via set_data_path).
        """
        if data_path is None:
            data_path = self.data_path
        
        # 1. Construct File Path
        filename = self.file_map.get(analysis_type)
        full_path = os.path.join(data_path, filename)
        
        # 2. Load the .mat file
        mat_data = sio.loadmat(full_path)
        
        # 3. Extract the numeric data 
        # (Note: 'data' is the variable name inside your MATLAB script)
        raw_array = mat_data['data'] 
        
        # 4. Transform for the specific model
        return self._apply_transform(raw_array, analysis_type, target_model)

    def _apply_transform(self, data, analysis_type, target_model):
        """
        Main entry point for data reshaping.
        """

        # Example: Reshaping ERP for CNN-LSTM
        if target_model == "cnn_lstm" and analysis_type == "erp":
            # ERP is (Samples, Channels, Time)
            # LSTM expects (Samples, Time, Channels)
            return data.transpose(0, 2, 1)

        # Reshaping ERP for EEGNet (Best)
        if target_model == "eeg_net" and analysis_type == "erp":
            # ERP is (Samples, Channels, Time)
            # EEGNet expects (Samples, 1, Channels, Time)
            return data.reshape(data.shape[0], 1, data.shape[1], data.shape[2])

        # Reshaping ERP for EEG-Inception (Best)
        if target_model == "eeg_inception" and analysis_type == "erp":
            # ERP is (Samples, Channels, Time)
            # Assuming Inception expects (Samples, Time, Channels)
            return data.transpose(0, 2, 1)

        # Reshaping Time-Frequency for EEG-Inception (Excellent)
        if target_model == "eeg_inception" and analysis_type == "time_frequency":
            # TF is (Samples, Channels, Freq, Time)
            # Assuming Inception can handle 4D input
            return data

        # Reshaping Inter-trial Phase for CNN-LSTM (Excellent)
        if target_model == "cnn_lstm" and analysis_type == "inter_trial_phase":
            # Assuming Inter-trial Phase is (Samples, Channels, Time)
            # LSTM expects (Samples, Time, Channels)
            return data.transpose(0, 2, 1)

        # Reshaping Spectral for Riemannian (Best)
        if target_model == "riemannian" and analysis_type == "spectral":
            # Spectral is (Samples, Channels, Freq)
            # Assuming Riemannian can handle this
            return data

        # Reshaping Connectivity for Riemannian (Best)
        if target_model == "riemannian" and analysis_type == "connectivity":
            # Connectivity is (Samples, Channels, Channels)
            # Assuming this is the covariance matrix for Riemannian
            return data

        return data