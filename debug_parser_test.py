
import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from parser.matlab_parameter_parser import MatlabParameterParser, create_ui_component

parser = MatlabParameterParser()
file_path = r'c:\Users\mamam\Desktop\Capstone\features\preprocessing\matlab\preprocess_data.m'

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    sys.exit(1)

params = parser.parse_file(file_path)
print(json.dumps(params, indent=2))

print("-" * 20)

for param_name, param_info in params.items():
    ui = create_ui_component(param_name, param_info)
    print(f"{param_name}: {ui['component_type']}")
