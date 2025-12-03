import json
import re
import os
from typing import Dict, List, Any, Optional

class MatlabParameterParser:
    """Parses MATLAB files to extract cfg parameters and their types."""

    def __init__(self):
        self.parameter_patterns = {
            'range': re.compile(r'cfg\.([\w\.]+)\s*=\s*\[([^\]]+)\]'),  # cfg.param = [0 1]
            'string': re.compile(r'cfg\.([\w\.]+)\s*=\s*[\'"]([^\'"]*)[\'"]'),  # cfg.param = 'value'
            'number': re.compile(r'cfg\.([\w\.]+)\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)'),  # cfg.param = 1.5
            'array': re.compile(r'cfg\.([\w\.]+)\s*=\s*([0-9:\.\-]+(?:\s+[0-9:\.\-]+)*)'),  # cfg.param = 1:2:40
            'cell_array': re.compile(r'cfg\.([\w\.]+)\s*=\s*\{([^\}]+)\}'), # cfg.param = {'a' 'b'}
            'standalone_cell_array': re.compile(r'(?<!\.)\b(\w+)\s*=\s*\{([^\}]+)\}'), # var = {'a' 'b'}
        }

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a MATLAB file and extract cfg parameters."""
        if not os.path.exists(file_path):
            return {}

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        parameters = {}
        all_matches = []

        # Define priority for types to resolve conflicts (same start position)
        # Lower index = higher priority
        type_priority = {t: i for i, t in enumerate(self.parameter_patterns.keys())}

        # Collect all matches with their positions
        for param_type, pattern in self.parameter_patterns.items():
            for match in pattern.finditer(content):
                try:
                    param_name = match.group(1)
                    param_value = match.group(2)
                    all_matches.append({
                        'start': match.start(),
                        'name': param_name,
                        'value': param_value,
                        'type': param_type,
                        'priority': type_priority[param_type]
                    })
                except IndexError:
                    continue

        # Sort by position in file, then by priority
        all_matches.sort(key=lambda x: (x['start'], x['priority']))

        # Process in order
        for match in all_matches:
            param_name = match['name']
            param_type = match['type']
            param_value = match['value']
            
            if param_name not in parameters:
                print(f"Matched {param_name} as {param_type} with value: {repr(param_value)}")
                parameters[param_name] = self._parse_parameter_value(param_type, param_value, param_name)

        return parameters

    def _parse_parameter_value(self, param_type: str, value_str: str, param_name: str = "") -> Dict[str, Any]:
        """Parse the parameter value based on its type."""
        if param_type == 'range':
            # Parse [0 1] or [0, 1] format
            values = re.findall(r'-?[0-9]+(?:\.[0-9]+)?', value_str)
            if len(values) >= 2:
                return {
                    'type': 'range',
                    'from': float(values[0]),
                    'to': float(values[1]),
                    'unit': 'ms' if 'latency' in param_name.lower() else ''
                }
        elif param_type == 'string':
            # Check for boolean-like strings
            lower_val = value_str.lower()
            if lower_val in ['yes', 'no', 'true', 'false']:
                return {
                    'type': 'boolean',
                    'value': lower_val in ['yes', 'true']
                }
            return {
                'type': 'string',
                'value': value_str,
                'options': [value_str]  # Could be extended to find alternatives
            }
        elif param_type == 'number':
            return {
                'type': 'number',
                'value': float(value_str)
            }
        elif param_type == 'array':
            # Parse arrays like 2:2:40 or [2 4 6]
            if ':' in value_str:
                parts = value_str.split(':')
                if len(parts) == 3:
                    start, step, end = map(float, parts)
                    values = list(range(int(start), int(end) + 1, int(step)))
                    return {
                        'type': 'array',
                        'values': values
                    }
            else:
                values = [float(x) for x in re.findall(r'-?[0-9]+(?:\.[0-9]+)?', value_str)]
                return {
                    'type': 'array',
                    'values': values
                }
        elif param_type == 'cell_array' or param_type == 'standalone_cell_array':
            # Parse {'S200' 'S201'}
            # Extract strings inside quotes
            options = re.findall(r'[\'"]([^\'"]*)[\'"]', value_str)
            return {
                'type': 'string', # Treat as string dropdown
                'value': options[0] if options else '',
                'options': options,
                'is_multi_select': True, # Cell arrays usually imply multiple values
                'is_standalone': param_type == 'standalone_cell_array'
            }

        return {'type': 'unknown', 'raw_value': value_str}

class ModuleParameterMapper:
    """Maps analysis modules to their corresponding MATLAB files."""

    def __init__(self):
        # Mapping from module display text to MATLAB file path
        self.module_mapping = {
            'ERP Analysis': 'features/analysis/matlab/ERP/timelock_func.m',
            'Time-Frequency Analysis': 'features/analysis/matlab/timefrequency/timefreqanalysis.m',
            'Inter-Trial Coherence Analysis': 'features/analysis/matlab/connectivity/intertrial/intertrialcoherenceanalysis.m',
            'Channel-Wise Coherence Analysis': 'features/analysis/matlab/connectivity/channelwise/channelwise.m',
            'Spectral Analysis': 'features/analysis/matlab/spectral/spectralanalysis.m',
            'Preprocessing': [
                'features/preprocessing/matlab/preprocessing.m',
                'features/preprocessing/matlab/preprocess_data.m'
            ]
        }

    def get_matlab_file(self, module_name: str) -> Any:
        """Get the MATLAB file path(s) for a module."""
        return self.module_mapping.get(module_name, '')

    def get_all_modules(self) -> List[str]:
        """Get all available module names."""
        return list(self.module_mapping.keys())


class DropdownOptionStore:
    """Loads curated dropdown option sets from JSON for analysis parameters."""

    def __init__(self, options_path: Optional[str] = None):
        self._project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.options_path = options_path or os.path.join(
            self._project_root, "config", "analysis_dropdown_options.json"
        )
        self._options = self._load_options()

    def _load_options(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(self.options_path):
            return {}

        try:
            with open(self.options_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError) as error:
            print(f"Warning: Unable to load dropdown options file: {error}")
            return {}

        parameters = payload.get("parameters", {}) if isinstance(payload, dict) else {}
        normalized: Dict[str, Dict[str, Any]] = {}
        for key, value in parameters.items():
            if not isinstance(value, dict):
                continue
            normalized[key.lower()] = value
        return normalized

    def get_option_entry(
        self, parameter_name: str, module_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        key = (parameter_name or "").strip().lower()
        if not key:
            return None

        entry = self._options.get(key)
        if not entry:
            return None

        modules = entry.get("modules")
        if modules and module_name and module_name not in modules:
            return None

        return entry

    def update_range_limits(self, parameter_name: str, min_val: float, max_val: float, module_name: str) -> bool:
        """Update the min/max range limits for a parameter if necessary."""
        key = (parameter_name or "").strip().lower()
        if not key:
            return False

        if key not in self._options:
            self._options[key] = {"modules": [module_name]}
        
        entry = self._options[key]
        changed = False
        
        # Update min/max unconditionally to allow shrinking or expanding
        current_min = entry.get('min')
        if current_min is None or current_min != min_val:
            entry['min'] = float(min_val)
            changed = True
            
        current_max = entry.get('max')
        if current_max is None or current_max != max_val:
            entry['max'] = float(max_val)
            changed = True
            
        # Ensure module is listed
        if "modules" not in entry:
            entry["modules"] = [module_name]
            changed = True
        elif module_name not in entry["modules"]:
            entry["modules"].append(module_name)
            changed = True
            
        return changed

    def add_option(self, parameter_name: str, new_option: str, module_name: str, is_multi_select: bool = False) -> bool:
        """Add a new option to the dropdown list."""
        key = (parameter_name or "").strip().lower()
        if not key or not new_option:
            return False

        if key not in self._options:
            self._options[key] = {
                "modules": [module_name],
                "options": [],
                "has_add_feature": True,
                "is_multi_select": is_multi_select
            }
        
        entry = self._options[key]
        changed = False

        # Update is_multi_select if it's true (upgrade to multi-select, never downgrade)
        if is_multi_select and not entry.get("is_multi_select", False):
            entry["is_multi_select"] = True
            changed = True

        if "options" not in entry:
            entry["options"] = []
            changed = True
            
        if new_option not in entry["options"]:
            entry["options"].append(new_option)
            changed = True
            
        # Ensure module is listed
        if "modules" not in entry:
            entry["modules"] = [module_name]
            changed = True
        elif module_name and module_name not in entry["modules"]:
            entry["modules"].append(module_name)
            changed = True
                
        return changed

    def remove_option(self, parameter_name: str, option_to_remove: str, module_name: str) -> bool:
        """Remove an option from the dropdown list."""
        key = (parameter_name or "").strip().lower()
        if not key or not option_to_remove:
            return False

        if key not in self._options:
            return False
        
        entry = self._options[key]
        if "options" not in entry:
            return False
            
        if option_to_remove in entry["options"]:
            entry["options"].remove(option_to_remove)
            return True
            
        return False

    def save(self):
        """Save the current options to the JSON file."""
        if not self.options_path:
            return

        payload = {
            "version": 1,
            "updated": "2025-11-30",
            "description": "Stores curated choice lists for MATLAB cfg.* parameters that render as dropdowns in the analysis processing page.",
            "parameters": self._options
        }
        
        try:
            with open(self.options_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            print(f"Error saving dropdown options: {e}")

def create_ui_component(
    parameter_name: str,
    parameter_info: Dict[str, Any],
    option_entry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create UI component configuration based on parameter type."""
    component = {
        'parameter_name': parameter_name,
        'matlab_property': parameter_name if parameter_info.get('is_standalone') else f'cfg.{parameter_name}'
    }

    option_entry = option_entry or {}

    if parameter_info['type'] == 'range':
        # Check if explicit min/max are defined in options
        min_val = option_entry.get('min')
        max_val = option_entry.get('max')
        
        # If not defined, use the parsed values with padding as requested
        if min_val is None:
            min_val = parameter_info.get('from', 0) - 1.0
        if max_val is None:
            max_val = parameter_info.get('to', 1) + 1.0
            
        component.update({
            'component_type': 'RangeSliderTemplate',
            'label': f'{parameter_name.replace("_", " ").title()}',
            'from': float(min_val),
            'to': float(max_val),
            'first_value': parameter_info.get('from', 0),
            'second_value': parameter_info.get('to', 1),
            'step_size': 0.1,
            'unit': parameter_info.get('unit', ''),
            'width_factor': 0.1,
            'background_color': 'white'
        })
    elif parameter_info['type'] == 'boolean':
        component.update({
            'component_type': 'CheckBoxTemplate',
            'label': f'{parameter_name.replace("_", " ").title()}',
            'checked': parameter_info.get('value', False)
        })
    elif parameter_info['type'] == 'number':
        component.update({
            'component_type': 'InputBoxTemplate',
            'label': f'{parameter_name.replace("_", " ").title()}',
            'text': str(parameter_info.get('value', 0)),
            'is_numeric': True
        })
    elif parameter_info['type'] == 'string':
        configured_options = option_entry.get('options') if option_entry else None
        base_options = parameter_info.get('options') or [str(parameter_info.get('value', ''))]
        
        # Merge configured options and base options to ensure unparsed options are included
        if configured_options:
            options = list(configured_options)
            # Add any base options that aren't in the configured list
            for item in base_options:
                s_item = str(item)
                if s_item and s_item not in options:
                    options.append(s_item)
        else:
            options = [str(item) for item in base_options if str(item)]

        current_value = str(parameter_info.get('value', ''))
        if current_value and current_value not in options:
            options = [current_value] + options

        if not options:
            options = ['']

        try:
            current_index = options.index(current_value) if current_value in options else 0
        except ValueError:
            current_index = 0

        component.update({
            'component_type': 'DropdownTemplate',
            'label': f'{parameter_name.replace("_", " ").title()}',
            'model': options,
            'all_items': options,  # Ensure all_items is populated for multi-select
            'current_index': current_index,
            'has_add_feature': bool(option_entry.get('has_add_feature', True)),
            'is_multi_select': bool(option_entry.get('is_multi_select', parameter_info.get('is_multi_select', False)))
        })

        if option_entry.get('max_selections') is not None:
            component['max_selections'] = option_entry['max_selections']
            
        # If multi-select, ensure selected_items are populated from the parsed values
        if component['is_multi_select']:
            component['selected_items'] = [str(item) for item in base_options]
            
    elif parameter_info['type'] == 'array':
        # For arrays, create a multi-select dropdown
        values = parameter_info.get('values', [])
        component.update({
            'component_type': 'DropdownTemplate',
            'label': f'{parameter_name.replace("_", " ").title()}',
            'model': [str(v) for v in values],
            'current_index': 0,
            'has_add_feature': False,
            'is_multi_select': True,
            'all_items': [str(v) for v in values],
            'selected_items': [str(v) for v in values]  # Select all by default
        })

    return component

if __name__ == '__main__':
    # Example usage
    parser = MatlabParameterParser()
    mapper = ModuleParameterMapper()
    option_store = DropdownOptionStore()

    # Parse ERP analysis file
    erp_file = mapper.get_matlab_file('ERP Analysis')
    if erp_file:
        params = parser.parse_file(erp_file)
        print("ERP Analysis parameters:")
        for param_name, param_info in params.items():
            print(f"  {param_name}: {param_info}")
            option_entry = option_store.get_option_entry(param_name, 'ERP Analysis')
            ui_component = create_ui_component(param_name, param_info, option_entry)
            print(f"    UI Component: {ui_component}")
            print()