import sys
import os
sys.path.append(os.getcwd())
from src.matlab_parameter_parser import MatlabParameterParser, create_ui_component, DropdownOptionStore

def debug_parser():
    parser = MatlabParameterParser()
    option_store = DropdownOptionStore()
    
    file_path = r"features/preprocessing/matlab/preprocess_data.m"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Parsing {file_path}...")
    params = parser.parse_file(file_path)
    
    for param_name, param_info in params.items():
        print(f"Parameter: {param_name}")
        print(f"  Info: {param_info}")
        
        option_entry = option_store.get_option_entry(param_name, 'Preprocessing')
        print(f"  Option Entry: {option_entry}")
        
        ui_component = create_ui_component(param_name, param_info, option_entry)
        print(f"  UI Component: {ui_component}")
        print("-" * 20)

if __name__ == "__main__":
    debug_parser()
