import json
import re
import os
from typing import Dict, List, Any, Optional

class MatlabParameterParser:
    """Parses MATLAB files to extract cfg parameters and their types."""

    def __init__(self):
        self.parameter_patterns = {
            'range': re.compile(r'cfg\.(\w+)\s*=\s*\[([^\]]+)\]'),  # cfg.param = [0 1]
            'string': re.compile(r'cfg\.(\w+)\s*=\s*[\'"]([^\'"]*)[\'"]'),  # cfg.param = 'value'
            'number': re.compile(r'cfg\.(\w+)\s*=\s*([0-9]+(?:\.[0-9]+)?)'),  # cfg.param = 1.5
            'array': re.compile(r'cfg\.(\w+)\s*=\s*([0-9\s:]+)'),  # cfg.param = 1:2:40
        }

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a MATLAB file and extract cfg parameters."""
        if not os.path.exists(file_path):
            return {}

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        parameters = {}

        # Parse different parameter types
        for param_type, pattern in self.parameter_patterns.items():
            matches = pattern.findall(content)
            for match in matches:
                param_name = match[0]
                param_value = match[1]

                if param_name not in parameters:  # Take first occurrence
                    parameters[param_name] = self._parse_parameter_value(param_type, param_value, param_name)

        return parameters

    def _parse_parameter_value(self, param_type: str, value_str: str, param_name: str = "") -> Dict[str, Any]:
        """Parse the parameter value based on its type."""
        if param_type == 'range':
            # Parse [0 1] or [0, 1] format
            values = re.findall(r'[0-9]+(?:\.[0-9]+)?', value_str)
            if len(values) >= 2:
                return {
                    'type': 'range',
                    'from': float(values[0]),
                    'to': float(values[1]),
                    'unit': 'ms' if 'latency' in param_name.lower() else ''
                }
        elif param_type == 'string':
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
                values = [float(x) for x in re.findall(r'[0-9]+(?:\.[0-9]+)?', value_str)]
                return {
                    'type': 'array',
                    'values': values
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
            'Spectral Analysis': 'features/analysis/matlab/spectral/spectralanalysis.m'
        }

    def get_matlab_file(self, module_name: str) -> str:
        """Get the MATLAB file path for a module."""
        return self.module_mapping.get(module_name, '')

    def get_all_modules(self) -> List[str]:
        """Get all available module names."""
        return list(self.module_mapping.keys())


class DropdownOptionStore:
    """Loads curated dropdown option sets from JSON for analysis parameters."""

    def __init__(self, options_path: Optional[str] = None):
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

def create_ui_component(
    parameter_name: str,
    parameter_info: Dict[str, Any],
    option_entry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create UI component configuration based on parameter type."""
    component = {
        'parameter_name': parameter_name,
        'matlab_property': f'cfg.{parameter_name}'
    }

    option_entry = option_entry or {}

    if parameter_info['type'] == 'range':
        component.update({
            'component_type': 'RangeSliderTemplate',
            'label': f'{parameter_name.replace("_", " ").title()}',
            'from': parameter_info.get('from', 0),
            'to': parameter_info.get('to', 1),
            'first_value': parameter_info.get('from', 0),
            'second_value': parameter_info.get('to', 1),
            'step_size': 0.1,
            'unit': parameter_info.get('unit', ''),
            'width_factor': 0.1,
            'background_color': 'white'
        })
    elif parameter_info['type'] == 'string':
        configured_options = option_entry.get('options') if option_entry else None
        base_options = parameter_info.get('options') or [parameter_info.get('value', '')]
        options = [str(item) for item in configured_options or base_options if str(item)]

        current_value = parameter_info.get('value', '')
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
            'current_index': current_index,
            'has_add_feature': bool(option_entry.get('has_add_feature', False)),
            'is_multi_select': bool(option_entry.get('is_multi_select', False))
        })

        if option_entry.get('max_selections') is not None:
            component['max_selections'] = option_entry['max_selections']
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