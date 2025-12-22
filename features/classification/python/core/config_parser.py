import os
import json
from pathlib import Path


class ConfigParser:
    """Parser for classifier configuration files"""
    
    def __init__(self):
        # Get the base path for config files
        self.base_path = Path(__file__).parent.parent / "models"
        
        # Map config file base names to human-readable analysis names
        self.analysis_name_map = {
            "erp_config": "ERP Analysis",
            "it_config": "Intertrial Coherence Analysis",
            "tf_config": "Time-Frequency Analysis",
            "connectivity_config": "Channel-Wise Connectivity Analysis",
            "spectral_config": "Spectral Analysis"
        }
        
        # Reverse map: display name -> config file base name (without _config)
        self.analysis_display_to_key = {
            "ERP Analysis": "erp",
            "Intertrial Coherence Analysis": "it",
            "Time-Frequency Analysis": "tf",
            "Channel-Wise Connectivity Analysis": "connectivity",
            "Spectral Analysis": "spectral"
        }
        
        # Define classifier configurations
        self.classifier_configs = {
            "EEGNet": {
                "display_text": "EEGNet Classifier",
                "configs": ["EEGNet/configs/erp_config.json"]
            },
            "EEG-Inception": {
                "display_text": "EEG-Inception Classifier",
                "configs": [
                    "EEG-Inception/configs/erp_config.json",
                    "EEG-Inception/configs/it_config.json",
                    "EEG-Inception/configs/tf_config.json"
                ]
            },
            "Riemannian": {
                "display_text": "Riemannian Classifier",
                "configs": [
                    "Riemannian/configs/connectivity_config.json",
                    "Riemannian/configs/spectral_config.json"
                ]
            }
        }
    
    def get_analysis_key(self, display_name):
        """Convert display name to internal analysis key"""
        return self.analysis_display_to_key.get(display_name, "")
    
    def load_config(self, config_path):
        """Load a single config file"""
        full_path = self.base_path / config_path
        if not full_path.exists():
            print(f"Warning: Config file not found: {full_path}")
            return {}
        
        try:
            with open(full_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {full_path}: {e}")
            return {}
        except Exception as e:
            print(f"Error loading config {full_path}: {e}")
            return {}
    
    def merge_configs(self, config_paths):
        """Merge multiple config files into one dictionary"""
        merged = {}
        for config_path in config_paths:
            config_data = self.load_config(config_path)
            # Flatten nested configs if needed
            for key, value in config_data.items():
                if isinstance(value, dict):
                    # Add nested dict items with prefix
                    for nested_key, nested_value in value.items():
                        merged[f"{key}.{nested_key}"] = nested_value
                else:
                    merged[key] = value
        return merged
    
    def get_classifier_params(self, classifier_name):
        """Get merged parameters for a specific classifier"""
        if classifier_name not in self.classifier_configs:
            return {}
        
        config_info = self.classifier_configs[classifier_name]
        return self.merge_configs(config_info["configs"])
    
    def get_all_classifiers(self):
        """Get all classifier configurations with their parameters"""
        result = {}
        for classifier_name, config_info in self.classifier_configs.items():
            result[classifier_name] = {
                "display_text": config_info["display_text"],
                "parameters": self.merge_configs(config_info["configs"])
            }
        return result
    
    def get_classifier_params_as_json(self, classifier_name):
        """Get classifier parameters as JSON string (for QML)"""
        params = self.get_classifier_params(classifier_name)
        return json.dumps(params)
    
    def get_all_classifiers_as_json(self):
        """Get all classifier configurations as JSON string (for QML)"""
        all_classifiers = self.get_all_classifiers()
        return json.dumps(all_classifiers)
    
    def get_available_analyses(self, classifier_name):
        """Get list of available analyses for a classifier based on config files"""
        if classifier_name not in self.classifier_configs:
            return []
        
        config_paths = self.classifier_configs[classifier_name]["configs"]
        analyses = []
        
        for config_path in config_paths:
            # Extract the base name (e.g., "erp_config" from "EEGNet/configs/erp_config.json")
            config_basename = Path(config_path).stem
            
            # Check if file exists
            full_path = self.base_path / config_path
            if full_path.exists():
                # Map to human-readable name
                analysis_name = self.analysis_name_map.get(config_basename, config_basename)
                analyses.append(analysis_name)
        
        return analyses
    
    def get_available_analyses_as_json(self, classifier_name):
        """Get available analyses as JSON string (for QML)"""
        analyses = self.get_available_analyses(classifier_name)
        return json.dumps(analyses)
    
    def get_params_for_analysis(self, classifier_name, analysis_name):
        """Get parameters for a specific classifier and analysis combination"""
        if classifier_name not in self.classifier_configs:
            return {}
        
        # Find the config file that matches this analysis
        config_paths = self.classifier_configs[classifier_name]["configs"]
        
        for config_path in config_paths:
            config_basename = Path(config_path).stem
            mapped_analysis_name = self.analysis_name_map.get(config_basename, config_basename)
            
            if mapped_analysis_name == analysis_name:
                # Load this specific config file
                config_data = self.load_config(config_path)
                
                # Flatten nested configs if needed
                flattened = {}
                for key, value in config_data.items():
                    if isinstance(value, dict):
                        # Add nested dict items with prefix
                        for nested_key, nested_value in value.items():
                            flattened[f"{key}.{nested_key}"] = nested_value
                    else:
                        flattened[key] = value
                
                return flattened
        
        return {}
    
    def get_params_for_analysis_as_json(self, classifier_name, analysis_name):
        """Get parameters for a specific analysis as JSON string (for QML)"""
        params = self.get_params_for_analysis(classifier_name, analysis_name)
        return json.dumps(params)
