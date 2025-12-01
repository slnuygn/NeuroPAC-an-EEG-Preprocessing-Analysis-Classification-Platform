import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from parser.matlab_parameter_parser import MatlabParameterParser, create_ui_component

def debug_parser():
    parser = MatlabParameterParser()
    # We need to check preprocessing.m specifically
    file_path = os.path.join('features', 'preprocessing', 'matlab', 'preprocessing.m')
    
    print(f"Parsing {file_path}...")
    params = parser.parse_file(file_path)
    
    if 'accepted_channels' in params:
        print("\nRaw parsed parameter:")
        print(json.dumps(params['accepted_channels'], indent=2))
        
        # Simulate what getModuleParameters does
        # It calls create_ui_component (implicitly or explicitly? Let's check matlab_executor)
        # Actually matlab_executor calls parser.parse_file, then updates range limits.
        # The UI (QML) receives the raw params? No, let's check preprocessing_page.qml
        
        # preprocessing_page.qml:
        # var jsonStr = matlabExecutor.getModuleParameters("Preprocessing")
        # var params = JSON.parse(jsonStr)
        
        # matlab_executor.py getModuleParameters:
        # file_params = parser.parse_file(matlab_file_path)
        # parameters.update(file_params)
        # return json.dumps(parameters)
        
        # So the UI receives the raw dictionary from parser.parse_file.
        # It does NOT go through create_ui_component in python?
        # Let's check matlab_parameter_parser.py again.
        
    else:
        print("accepted_channels not found")

if __name__ == "__main__":
    debug_parser()
