import os
import scipy.io as sio
import numpy as np
import h5py
# Importing the group labels from your common folder
from features.classification.python.core.labels import labels as group_list


class MatlabStructElement:
    """
    Represents a single element of a MATLAB struct array.
    Supports subscript access like record[fieldname] to access fields.
    """
    def __init__(self, data_dict):
        self._data = data_dict
        # Also set as attributes for compatibility
        for key, value in data_dict.items():
            setattr(self, key, value)
    
    def __getitem__(self, key):
        """Support subscript access like record['fieldname']"""
        if key in self._data:
            return self._data[key]
        raise KeyError(f"'{key}' not found in struct. Available keys: {list(self._data.keys())}")
    
    def __setitem__(self, key, value):
        """Support subscript assignment"""
        self._data[key] = value
        setattr(self, key, value)
    
    def __contains__(self, key):
        """Support 'in' operator"""
        return key in self._data
    
    def keys(self):
        """Return available keys"""
        return self._data.keys()
    
    def get(self, key, default=None):
        """Support dict.get() method"""
        return self._data.get(key, default)
    
    def __repr__(self):
        return f"MatlabStructElement(keys={list(self._data.keys())})"
    
    @property
    def dtype(self):
        """Provide dtype attribute for compatibility"""
        return type('dtype', (object,), {'names': list(self._data.keys())})()
    
    @property
    def ndim(self):
        """Provide ndim attribute"""
        return 0
    
    @property
    def shape(self):
        """Provide shape attribute"""
        return ()

class PreprocessBridge:
    def __init__(self, data_folder="data/"):
        # Normalize the data folder path
        if data_folder:
            # Handle both forward and backslashes
            self.data_path = data_folder.replace('\\', '/').rstrip('/')
            # Remove file:// prefix if present
            if self.data_path.startswith('file:///'):
                self.data_path = self.data_path[8:]
            elif self.data_path.startswith('file://'):
                self.data_path = self.data_path[7:]
        else:
            self.data_path = "data/"
        
        print(f"[PreprocessBridge] Initialized with data_path: {self.data_path}")
        
        # HDF5 file handle (kept open during loading for reference dereferencing)
        self._h5_file = None
        
        # Map analysis types to their actual .mat filenames
        self.file_map = {
            "erp": "erp_output.mat",
            "time_frequency": "timefreq_output.mat",
            "spectral": "spectral_output.mat",
            "connectivity": "channelwise_coherence_output.mat",
            "intertrial_coherence": "intertrial_coherence_output.mat"
        }
        
        # Define the fields expected in your MATLAB struct
        # Updated order: target (0), standard (1), novelty (2)
        self.conditions = ["target", "standard", "novelty"]
        
        # Map text labels to numeric values for the model (allow common variants)
        self.group_mapping = {
            "HC": 0,
            "Hc": 0,
            "hc": 0,
            "CTL": 0,  # Control group
            "ctl": 0,
            "P": 1,
            "PD": 1,
            "pd": 1,
            "Parkinson": 1,
            "Parkinsons": 1,
            "Parkinson's": 1,
            "parkinson": 1,
            "parkinsons": 1,
            "parkinson's": 1,
        }

    def set_data_path(self, path):
        self.data_path = path

    def filter_by_selected_classes(self, samples, group_labels, condition_labels, selected_classes):
        """
        Filter samples to include only selected classes.
        
        Args:
            samples: List of sample data
            group_labels: List of group labels (indices or names)
            condition_labels: List of condition labels (0=target, 1=standard, 2=novelty)
            selected_classes: List of selected class names (e.g., ["PD_target", "CTL_standard"])
        
        Returns:
            Filtered samples, group_labels, condition_labels, kept_indices
        """
        if not selected_classes or len(selected_classes) == 0:
            # If no classes selected, return all samples
            indices = list(range(len(samples)))
            return samples, group_labels, condition_labels, indices
        
        print(f"[PreprocessBridge] DEBUG: Filtering with selected_classes = {selected_classes}")
        print(f"[PreprocessBridge] DEBUG: Total samples = {len(samples)}")
        print(f"[PreprocessBridge] DEBUG: Sample group_labels (first 10) = {group_labels[:10] if len(group_labels) >= 10 else group_labels}")
        print(f"[PreprocessBridge] DEBUG: Sample condition_labels (first 10) = {condition_labels[:10] if len(condition_labels) >= 10 else condition_labels}")
        
        # Parse selected classes into (group_name, condition) tuples
        selected_combos = []
        for class_str in selected_classes:
            parts = class_str.rsplit('_', 1)  # Split from the right to handle multi-word groups
            if len(parts) == 2:
                group_name, condition = parts
                # Map condition name to index
                condition_idx = self.conditions.index(condition.lower()) if condition.lower() in self.conditions else -1
                if condition_idx != -1:
                    selected_combos.append((group_name.upper(), condition_idx))
        
        print(f"[PreprocessBridge] DEBUG: Parsed selected_combos = {selected_combos}")
        
        if not selected_combos:
            indices = list(range(len(samples)))
            return samples, group_labels, condition_labels, indices
        
        # Filter samples
        filtered_samples = []
        filtered_group_labels = []
        filtered_condition_labels = []
        kept_indices = []
        
        for i, (sample, group_label, cond_label) in enumerate(zip(samples, group_labels, condition_labels)):
            # Normalize group_label for comparison
            # group_label can be int, float, numpy int types, or string
            try:
                # Try to convert to int (works for int, float, numpy types, and numeric strings)
                group_idx = int(group_label)
            except (ValueError, TypeError):
                # If conversion fails, treat as string and look up in mapping
                group_idx = self.group_mapping.get(str(group_label).upper(), -1)
            
            if i < 5:  # Debug first 5 samples
                print(f"[PreprocessBridge] DEBUG: Sample {i}: group_label={group_label} (type={type(group_label)}), group_idx={group_idx}, cond_label={cond_label}")
            
            # Check if this sample matches any selected combo
            for selected_group, selected_cond in selected_combos:
                # Get the index that selected_group maps to
                selected_group_idx = self.group_mapping.get(selected_group, -1)
                
                if i < 5:  # Debug first 5 samples
                    print(f"[PreprocessBridge] DEBUG: Sample {i}: Checking {selected_group} (idx={selected_group_idx}) vs group_idx={group_idx}, cond {selected_cond} vs {cond_label}")
                
                if selected_group_idx == group_idx and selected_cond == cond_label:
                    filtered_samples.append(sample)
                    filtered_group_labels.append(group_label)
                    filtered_condition_labels.append(cond_label)
                    kept_indices.append(i)
                    break
        
        print(f"[PreprocessBridge] Filtered {len(filtered_samples)} samples from {len(samples)} total (selected classes: {selected_classes})")
        
        return filtered_samples, filtered_group_labels, filtered_condition_labels, kept_indices

    def load_and_transform(self, analysis_type, target_model, data_path=None):
        if data_path is None:
            data_path = self.data_path
        else:
            # Normalize provided data_path
            data_path = data_path.replace('\\', '/').rstrip('/')
            if data_path.startswith('file:///'):
                data_path = data_path[8:]
            elif data_path.startswith('file://'):
                data_path = data_path[7:]
        
        filename = self.file_map.get(analysis_type)
        # Construct full path with forward slashes, then convert to OS-specific
        full_path = f"{data_path}/{filename}".replace('\\', '/').replace('//', '/')
        # Convert to OS-specific path
        full_path = full_path.replace('/', os.sep)
        
        print(f"[PreprocessBridge] Loading: {full_path}")
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Data file not found: {full_path}")

        try:
            print(f"[PreprocessBridge] Attempting scipy.io.loadmat...")
            # Use squeeze_me=True to avoid 1x1 wrapper arrays around structs
            mat_data = sio.loadmat(full_path, struct_as_record=False, squeeze_me=True)
            print(f"[PreprocessBridge] Successfully loaded with scipy.io.loadmat")
        except (ValueError, NotImplementedError) as e:
            error_msg = str(e)
            if "HDF reader" in error_msg or "matlab v7.3" in error_msg.lower():
                # Fallback to h5py for MATLAB v7.3 files
                print(f"[PreprocessBridge] scipy.io.loadmat failed: {error_msg}")
                print(f"[PreprocessBridge] Falling back to h5py for MATLAB v7.3...")
                mat_data = self._load_mat_v73(full_path)
                print(f"[PreprocessBridge] Successfully loaded with h5py")
            else:
                raise
        
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
        
        print(f"[PreprocessBridge] Using struct_key='{struct_key}', data_field='{data_field}'")
        print(f"[PreprocessBridge] Available keys in mat_data: {list(mat_data.keys())}")
            
        raw_records = mat_data[struct_key]
        
        # Handle ndim for both numpy arrays and custom HDF5Struct objects
        if hasattr(raw_records, 'ndim'):
            ndim = raw_records.ndim
            shape = raw_records.shape if hasattr(raw_records, 'shape') else (1,)
        else:
            ndim = 1
            shape = (1,) if not isinstance(raw_records, np.ndarray) else raw_records.shape
        
        print(f"[PreprocessBridge] raw_records ndim: {ndim}, shape: {shape}")
        
        all_samples = []
        condition_labels = [] 
        group_labels = []     
        subject_ids = []
        dataset_names = []  # Track dataset names for each sample

        # Handle MATLAB 1xN or Nx1 struct arrays
        if ndim > 1:
            if shape[0] == 1:
                num_subjects = shape[1]
            else:
                num_subjects = shape[0]
        else:
            num_subjects = len(raw_records) if hasattr(raw_records, '__len__') else 1

        print(f"[PreprocessBridge] Processing {num_subjects} subjects...")
        for i in range(num_subjects):
            print(f"[PreprocessBridge] Processing subject {i+1}/{num_subjects}... ", end="", flush=True)
            try:
                if ndim > 1:
                    if shape[0] == 1: 
                        record = raw_records[0, i]
                    else: 
                        record = raw_records[i, 0]
                else:
                    record = raw_records[i]
                
                # Extract dataset name from cfg if available
                dataset_name = "S" + str(i).zfill(3)  # Default: S001, S002, etc.
                try:
                    if hasattr(record, 'dtype') and record.dtype.names and 'cfg' in record.dtype.names:
                        cfg = record['cfg']
                        if hasattr(cfg, 'dtype') and cfg.dtype.names and 'dataset' in cfg.dtype.names:
                            ds = cfg['dataset']
                            if isinstance(ds, str):
                                dataset_name = os.path.splitext(os.path.basename(ds))[0]
                            elif hasattr(ds, '__len__') and len(ds) > 0:
                                ds_val = ds.flat[0] if hasattr(ds, 'flat') else ds[0]
                                if isinstance(ds_val, str):
                                    dataset_name = os.path.splitext(os.path.basename(ds_val))[0]
                except (AttributeError, IndexError, KeyError, TypeError):
                    pass  # Use default dataset_name
                
                try:
                    raw_group_label = group_list[i]
                    group_val = self.group_mapping.get(raw_group_label, -1)
                    if group_val == -1:
                        print(f"\nWarning: Unmapped group label '{raw_group_label}' for subject index {i}; assigning -1")
                except (IndexError, TypeError):
                    group_val = -1
                    print(f"\nWarning: No group label provided for subject index {i}; assigning -1")

                for label_idx, cond in enumerate(self.conditions):
                    try:
                        # Access like MATLAB: record.target (cond_struct is target/standard/novelty struct)
                        # Support both attribute-style (mat_struct) and dict-like access.
                        if isinstance(record, MatlabStructElement):
                            cond_struct = record.get(cond)
                        else:
                            cond_struct = getattr(record, cond, None)
                            if cond_struct is None:
                                if isinstance(record, dict):
                                    cond_struct = record.get(cond)
                                else:
                                    try:
                                        cond_struct = record[cond]
                                    except Exception:
                                        cond_struct = None

                        # If we got a 1-element ndarray wrapping the struct, unwrap it
                        if isinstance(cond_struct, np.ndarray) and cond_struct.size == 1:
                            try:
                                cond_struct = cond_struct.flat[0]
                            except Exception:
                                pass

                        if cond_struct is None:
                            raise KeyError(f"{cond} not found in record")
                        
                        # Debug: print what we got for first subject
                        if i == 0 and label_idx == 0:
                            print(f"[PreprocessBridge] DEBUG: record type={type(record)}")
                            if isinstance(record, MatlabStructElement):
                                print(f"[PreprocessBridge] DEBUG: record keys={list(record.keys())}")
                            print(f"[PreprocessBridge] DEBUG: cond_struct ({cond}) type={type(cond_struct)}")
                            if isinstance(cond_struct, MatlabStructElement):
                                print(f"[PreprocessBridge] DEBUG: cond_struct keys={list(cond_struct.keys())}")
                        
                        # Access like MATLAB: record.target.powspctrm
                        if isinstance(cond_struct, MatlabStructElement):
                            raw_data = cond_struct[data_field]
                        elif isinstance(cond_struct, np.ndarray):
                            # If it's already an array, it might be the data
                            raw_data = cond_struct
                        else:
                            raw_data = getattr(cond_struct, data_field, None)
                        
                        if raw_data is None:
                            # Fallback: try trial field and average
                            trial_data = getattr(cond_struct, 'trial', None) if not isinstance(cond_struct, MatlabStructElement) else cond_struct.get('trial')
                            if trial_data is not None:
                                raw_data = np.mean(np.array(trial_data, dtype=np.float32), axis=0)
                            else:
                                raise KeyError(f"{data_field} not found in {cond}")

                        # If raw_data is still wrapped in a 1-element ndarray, unwrap
                        if isinstance(raw_data, np.ndarray) and raw_data.size == 1 and raw_data.dtype == object:
                            try:
                                raw_data = raw_data.flat[0]
                            except Exception:
                                pass

                        # If avg exists but is empty, fallback to trial
                        if isinstance(raw_data, np.ndarray) and raw_data.size == 0:
                            trial_data = getattr(cond_struct, 'trial', None) if not isinstance(cond_struct, MatlabStructElement) else cond_struct.get('trial')
                            if trial_data is not None:
                                raw_data = np.mean(np.array(trial_data, dtype=np.float32), axis=0)
                            else:
                                raise KeyError(f"{data_field} empty in {cond} and no trial fallback")
                        
                        # Debug: print raw_data info for first subject
                        if i == 0 and label_idx == 0:
                            print(f"[PreprocessBridge] DEBUG: raw_data ({data_field}) type={type(raw_data)}")
                            if isinstance(raw_data, np.ndarray):
                                print(f"[PreprocessBridge] DEBUG: raw_data shape={raw_data.shape}, dtype={raw_data.dtype}")
                        
                        # Convert to numpy array; for complex data use magnitude to keep real values
                        if np.iscomplexobj(raw_data):
                            raw_data = np.abs(raw_data)

                        sample = np.array(raw_data, dtype=np.float32)
                        sample = np.squeeze(sample)
                        
                        # Debug: print sample info for first subject
                        if i == 0 and label_idx == 0:
                            print(f"[PreprocessBridge] DEBUG: sample shape after squeeze={sample.shape}")
                        
                        # Skip empty samples
                        if sample.size == 0:
                            print(f"[PreprocessBridge] Skipping empty sample for {cond} subject {i}")
                            continue
                        
                        # Extract dimord if provided to understand dimension ordering
                        dimord = None
                        try:
                            dimord = cond_struct.get('dimord') if isinstance(cond_struct, MatlabStructElement) else getattr(cond_struct, 'dimord', None)
                        except Exception:
                            dimord = None
                        if isinstance(dimord, bytes):
                            dimord = dimord.decode('utf-8', errors='ignore')

                        # --- Special handling for Spectral ---
                        if analysis_type == "spectral":
                            # If 4D (trials x chans x freq x time), average over trials/tapers
                            if sample.ndim == 4:
                                sample = np.nanmean(sample, axis=0)
                            # If 3D and the first axis is trials/tapers (common dimord: rpt*_chan_freq(_time))
                            elif sample.ndim == 3:
                                dimord_str = dimord or ""
                                if dimord_str.startswith("rpt") or dimord_str.startswith("rpttap"):
                                    sample = np.nanmean(sample, axis=0)
                                else:
                                    # Heuristic: if first axis differs across subjects, averaging removes variability
                                    sample = np.nanmean(sample, axis=0)
                            else:
                                # Unexpected shape; attempt squeeze once
                                sample = np.squeeze(sample)

                        # --- Special handling for Connectivity ---
                        if analysis_type == "connectivity" and sample.ndim == 4:
                            if target_model == "riemannian":
                                sample = np.nanmean(sample, axis=(2, 3))

                        # Replace any remaining NaNs/Infs in the sample to avoid all-zero degeneration
                        if np.isnan(sample).any() or np.isinf(sample).any():
                            if np.isnan(sample).all():
                                print(f"[PreprocessBridge] WARNING: sample for subject {i}, cond {cond} is all NaN; filling with 0")
                            sample = np.nan_to_num(sample, nan=0.0, posinf=0.0, neginf=0.0)
                        
                        all_samples.append(sample)
                        condition_labels.append(label_idx)
                        group_labels.append(group_val)
                        subject_ids.append(i)
                        dataset_names.append(dataset_name)  # Track dataset name for each sample
                    except (KeyError, ValueError, IndexError, TypeError, AttributeError) as e:
                        print(f"[PreprocessBridge] Warning: Failed to extract {cond}.{data_field} for subject {i}: {e}")
                
                print("[OK]")
            except Exception as e:
                print(f"[ERROR] Error processing subject {i}: {e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"[PreprocessBridge] Loaded {len(all_samples)} samples")
        if len(all_samples) == 0:
            raise ValueError(
                f"No samples loaded for analysis '{analysis_type}'. "
                f"Check that expected fields ({', '.join(self.conditions)}) and '{data_field}' exist in the .mat file."
            )

        # Normalize shapes across all samples before stacking to avoid ragged arrays
        max_ndim = max(sample.ndim for sample in all_samples)
        normalized_samples = []
        for sample in all_samples:
            arr = sample
            while arr.ndim < max_ndim:
                arr = np.expand_dims(arr, axis=-1)
            normalized_samples.append(arr)

        max_shape = [max(arr.shape[dim] for arr in normalized_samples) for dim in range(max_ndim)]
        padded_samples = []
        for idx, arr in enumerate(normalized_samples):
            pad_width = [(0, max_shape[dim] - arr.shape[dim]) for dim in range(max_ndim)]
            padded = np.pad(arr, pad_width, mode='constant')
            padded_samples.append(padded)
            if idx == 0:
                print(f"[PreprocessBridge] DEBUG: padding target shape {max_shape}")

        try:
            X = np.stack(padded_samples, axis=0)
        except ValueError as e:
            shape_summary = [arr.shape for arr in padded_samples[:5]]
            raise ValueError(f"Failed to stack samples due to shape mismatch: {shape_summary}") from e
        
        y = {
            "condition": np.array(condition_labels),
            "group": np.array(group_labels),
            "subject_id": np.array(subject_ids),
            "dataset_name": dataset_names  # Include dataset names
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
                if data.ndim < 3:
                    raise ValueError(
                        f"ERP data has inconsistent shape {data.shape}; expected (samples, channels, time)."
                    )
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

    def _load_mat_v73(self, mat_path):
        """
        Load MATLAB v7.3 files using h5py.
        MATLAB stores struct arrays using HDF5 references which need to be dereferenced.
        
        Structure: timefreq_data(1).target.powspctrm -> channels x freq x time
        """
        print(f"[PreprocessBridge] Opening HDF5 file: {mat_path}")
        mat_dict = {}
        
        try:
            self._h5_file = h5py.File(mat_path, 'r')
            print(f"[PreprocessBridge] HDF5 file structure: {list(self._h5_file.keys())}")
            
            for key in self._h5_file.keys():
                if not key.startswith('#'):
                    print(f"[PreprocessBridge] Processing top-level key: {key}")
                    mat_dict[key] = self._convert_mat73_struct_array(self._h5_file[key])
            
            print(f"[PreprocessBridge] Successfully loaded HDF5 with keys: {list(mat_dict.keys())}")
            
            # Close the file after conversion is complete
            if self._h5_file is not None:
                self._h5_file.close()
                self._h5_file = None
            
            return mat_dict
            
        except Exception as e:
            print(f"[PreprocessBridge] Error loading HDF5 file: {e}")
            import traceback
            traceback.print_exc()
            if self._h5_file is not None:
                self._h5_file.close()
                self._h5_file = None
            raise
    
    def _deref(self, ref):
        """Dereference an HDF5 reference"""
        return self._h5_file[ref]
    
    def _convert_mat73_struct_array(self, h5_obj):
        """
        Convert MATLAB v7.3 struct array (top level like timefreq_data).
        Only extracts the fields we need for analysis.
        """
        if isinstance(h5_obj, h5py.Dataset):
            data = np.array(h5_obj)
            # If it's not a reference array, just return the data
            if data.dtype != h5py.ref_dtype:
                return data
            # Scalar reference - shouldn't happen at top level
            return data
        
        elif isinstance(h5_obj, h5py.Group):
            keys = [k for k in h5_obj.keys() if not k.startswith('#')]
            
            if not keys:
                return None
            
            # Check first field to determine if this is a struct array
            first_key = keys[0]
            first_item = h5_obj[first_key]
            
            if isinstance(first_item, h5py.Dataset):
                data = np.array(first_item)
                
                if data.dtype == h5py.ref_dtype and data.ndim == 2:
                    # This is a struct array - fields contain references to elements
                    # Shape is typically (1, N) for 1xN struct array
                    num_elements = max(data.shape)
                    print(f"[PreprocessBridge] Creating struct array with {num_elements} elements, fields: {keys}")
                    
                    struct_array = np.empty(num_elements, dtype=object)
                    
                    for idx in range(num_elements):
                        elem_dict = {}
                        for field_name in keys:
                            field_refs = np.array(h5_obj[field_name])
                            if field_refs.shape[0] == 1:
                                ref = field_refs[0, idx]
                            else:
                                ref = field_refs[idx, 0]
                            
                            # Dereference and convert the condition struct (target/standard/novelty)
                            dereffed = self._deref(ref)
                            elem_dict[field_name] = self._convert_condition_struct(dereffed)
                        
                        struct_array[idx] = MatlabStructElement(elem_dict)
                    
                    return struct_array
            
            # Fallback: just convert as simple struct
            result_dict = {}
            for key in keys:
                child = h5_obj[key]
                if isinstance(child, h5py.Dataset):
                    result_dict[key] = np.array(child)
            return MatlabStructElement(result_dict) if result_dict else None
        
        return h5_obj
    
    def _convert_condition_struct(self, h5_obj):
        """
        Convert a condition struct (target/standard/novelty).
        Only extracts data fields we need (powspctrm, avg, etc.), ignores cfg and other metadata.
        """
        if isinstance(h5_obj, h5py.Dataset):
            data = np.array(h5_obj)
            if data.dtype == h5py.ref_dtype:
                # Single reference - dereference it
                if data.ndim == 0:
                    return self._convert_condition_struct(self._deref(data[()]))
                elif data.size == 1:
                    return self._convert_condition_struct(self._deref(data.flat[0]))
            return data
        
        elif isinstance(h5_obj, h5py.Group):
            keys = [k for k in h5_obj.keys() if not k.startswith('#')]
            
            # Data fields we care about - these contain the actual EEG data
            data_fields = ['powspctrm', 'avg', 'fourierspctrm', 'cohspctrm', 'itpc', 
                          'trial', 'time', 'freq', 'label', 'dimord']
            
            result_dict = {}
            for key in keys:
                # Only process data fields, skip cfg and other metadata to avoid deep recursion
                if key in data_fields or key not in ['cfg', 'hdr', 'grad', 'elec']:
                    child = h5_obj[key]
                    if isinstance(child, h5py.Dataset):
                        data = np.array(child)
                        if data.dtype == h5py.ref_dtype:
                            # It's a reference - dereference it
                            if data.size == 1:
                                ref = data.flat[0]
                                dereffed = self._deref(ref)
                                if isinstance(dereffed, h5py.Dataset):
                                    result_dict[key] = np.array(dereffed)
                                else:
                                    # Skip complex nested groups
                                    pass
                            else:
                                # Array of references - just get the data directly
                                result_dict[key] = data
                        else:
                            result_dict[key] = data
                    elif isinstance(child, h5py.Group):
                        # For nested groups (rare for data fields), try to get data
                        if key in data_fields:
                            nested_data = self._extract_data_from_group(child)
                            if nested_data is not None:
                                result_dict[key] = nested_data
            
            return MatlabStructElement(result_dict) if result_dict else None
        
        return h5_obj
    
    def _extract_data_from_group(self, h5_group):
        """Extract numerical data from an HDF5 group, avoiding deep recursion."""
        keys = [k for k in h5_group.keys() if not k.startswith('#')]
        
        for key in keys:
            child = h5_group[key]
            if isinstance(child, h5py.Dataset):
                data = np.array(child)
                if data.dtype != h5py.ref_dtype:
                    return data
        
        return None