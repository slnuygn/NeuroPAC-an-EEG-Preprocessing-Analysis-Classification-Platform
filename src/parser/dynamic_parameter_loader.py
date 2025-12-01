#!/usr/bin/env python3
"""
Dynamic Parameter Loader for MATLAB Analysis Modules
This script parses MATLAB files and generates UI component configurations.
"""

import sys
import os
import json
from parser.matlab_parameter_parser import (
    MatlabParameterParser,
    ModuleParameterMapper,
    DropdownOptionStore,
    create_ui_component,
)

def get_module_parameters(module_name: str) -> dict:
    """Get parameter configurations for a specific module."""
    parser = MatlabParameterParser()
    mapper = ModuleParameterMapper()
    option_store = DropdownOptionStore()

    matlab_files = mapper.get_matlab_file(module_name)
    if not matlab_files:
        return {}

    # Convert relative path to absolute path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))  # Go up to Capstone root
    
    parameters = {}
    
    # Handle both single file string and list of files
    if isinstance(matlab_files, str):
        matlab_files = [matlab_files]
        
    for matlab_file in matlab_files:
        matlab_file_path = os.path.join(project_root, matlab_file)
        file_params = parser.parse_file(matlab_file_path)
        parameters.update(file_params)

    # Convert parameters to UI components
    ui_components = {}
    for param_name, param_info in parameters.items():
        option_entry = option_store.get_option_entry(param_name, module_name)
        ui_components[param_name] = create_ui_component(param_name, param_info, option_entry)

    return ui_components

def main():
    if len(sys.argv) < 2:
        print("Usage: python dynamic_parameter_loader.py <module_name>")
        sys.exit(1)

    module_name = sys.argv[1]
    parameters = get_module_parameters(module_name)

    # Output as JSON for QML to consume
    print(json.dumps(parameters, indent=2))

if __name__ == "__main__":
    main()