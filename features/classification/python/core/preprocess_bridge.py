import os
import scipy.io as sio
import numpy as np
# Importing the group labels from your common folder
from features.classification.python.core.labels import labels as group_list

class PreprocessBridge:
    def __init__(self, data_folder="data/"):
        self.data_path = data_folder
        
        # Map analysis types to their actual .mat filenames
        self.file_map = {
            "erp": "erp_output.mat",
            "time_frequency": "timefreq_output.mat",
            "spectral": "spectral_output.mat",
            "connectivity": "channelwise_coherence_output.mat",
            "intertrial_coherence": "itc_output.mat"
        }
        
        # Define the fields expected in your MATLAB struct
        # Updated order: target (0), standard (1), novelty (2)
        self.conditions = ["target", "standard", "novelty"]
        
        # Map text labels to numeric values for the model
        self.group_mapping = {"HC": 0, "P": 1}

    def set_data_path(self, path):
        self.data_path = path

    def load_and_transform(self, analysis_type, target_model, data_path=None):
        if data_path is None:
            data_path = self.data_path
        
        filename = self.file_map.get(analysis_type)
        full_path = os.path.join(data_path, filename)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Data file not found: {full_path}")

        mat_data = sio.loadmat(full_path)
        
        # Determine the correct key for the struct and the internal data field
        if analysis_type == "erp":
            struct_key = 'ERP_data' if 'ERP_data' in mat_data else 'data'
            data_field = 'avg'
        elif analysis_type == "time_frequency":
            struct_key = 'timefreq_data' if 'timefreq_data' in mat_data else 'data'
            data_field = 'powspctrm'
        elif analysis_type == "spectral":
            struct_key = 'spectral_data' if 'spectral_data' in mat_data else 'data'
            data_field = 'fourierspctrm'
        elif analysis_type == "connectivity":
            struct_key = 'coherence_data' if 'coherence_data' in mat_data else 'data'
            data_field = 'cohspctrm'
        elif analysis_type == "intertrial_coherence":
            struct_key = 'itc_data' if 'itc_data' in mat_data else 'data'
            data_field = 'itpc'
        else:
            struct_key = 'data'
            data_field = 'data'
            
        raw_records = mat_data[struct_key]
        
        all_samples = []
        condition_labels = [] 
        group_labels = []     
        subject_ids = []      

        # Handle MATLAB 1xN or Nx1 struct arrays
        if raw_records.ndim > 1:
            if raw_records.shape[0] == 1:
                num_subjects = raw_records.shape[1]
            else:
                num_subjects = raw_records.shape[0]
        else:
            num_subjects = len(raw_records)

        for i in range(num_subjects):
            if raw_records.ndim > 1:
                if raw_records.shape[0] == 1: record = raw_records[0, i]
                else: record = raw_records[i, 0]
            else:
                record = raw_records[i]
            
            try:
                raw_group_label = group_list[i]
                group_val = self.group_mapping.get(raw_group_label, -1)
            except IndexError:
                group_val = -1

            for label_idx, cond in enumerate(self.conditions):
                try:
                    cond_struct = record[cond]
                    sample = cond_struct[data_field][0, 0] 
                    
                    sample = np.array(sample, dtype=np.float32)
                    sample = np.squeeze(sample) 
                    
                    # --- Special handling for Spectral ---
                    if analysis_type == "spectral" and sample.ndim == 3:
                        sample = np.mean(sample, axis=0)

                    # --- Special handling for Connectivity ---
                    if analysis_type == "connectivity" and sample.ndim == 4:
                        if target_model == "riemannian":
                            sample = np.mean(sample, axis=(2, 3))
                    
                    all_samples.append(sample)
                    condition_labels.append(label_idx)
                    group_labels.append(group_val)
                    subject_ids.append(i)
                except (KeyError, ValueError, IndexError) as e:
                    print(f"Warning: Failed to extract {cond}.{data_field} for subject {i}: {e}")

        X = np.array(all_samples) 
        
        y = {
            "condition": np.array(condition_labels),
            "group": np.array(group_labels),
            "subject_id": np.array(subject_ids)
        }
        
        X_transformed = self._apply_transform(X, analysis_type, target_model)
        
        return X_transformed, y

    def _apply_transform(self, data, analysis_type, target_model):
        """
        Handles the specific tensor shaping for SOTA models.
        """
        # --- ERP TRANSFORMATIONS ---
        if analysis_type == "erp":
            if target_model in ["eeg_net", "eeg_inception"]:
                return data.reshape(data.shape[0], 1, data.shape[1], -1)

        # --- TIME-FREQUENCY & INTER-TRIAL COHERENCE (12x29x401) ---
        # Both use the same shape for EEG-Inception
        if analysis_type in ["time_frequency", "intertrial_coherence"]:
            if target_model == "eeg_inception":
                # Input: (Batch, 12, 29, 401)
                # Keep as 4D: Batch, Channels, Freq, Time
                return data 

        # --- RIEMANNIAN / SPECTRAL / CONNECTIVITY ---
        if target_model == "riemannian":
            return data

        return data