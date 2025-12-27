import os
import sys
import subprocess
import re
import threading
import json
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
import scipy.io
from parser.matlab_parameter_parser import (
    MatlabParameterParser,
    ModuleParameterMapper,
    DropdownOptionStore,
    create_ui_component,
)

# Add parent directory to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'features', 'classification', 'python', 'core'))
from preprocess_bridge import PreprocessBridge


# Function to get the resource path (works for both development and PyInstaller)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class MatlabWorkerThread(QThread):
    """Worker thread for running MATLAB commands in the background"""

    finished = pyqtSignal(dict)  # Emits result dictionary

    def __init__(self, matlab_path, script_dir, show_console=False):
        super().__init__()
        self.matlab_path = matlab_path
        self.script_dir = script_dir
        self.show_console = show_console

    def run(self):
        """Run MATLAB preprocessing in background thread"""
        try:
            script_dir_unix = self.script_dir.replace(chr(92), '/')

            if self.show_console:
                command_string = (
                    f"try, cd('{script_dir_unix}'); preprocessing; "
                    "catch e, disp(getReport(e)); pause; end; exit"
                )
                cmd = [
                    self.matlab_path,
                    '-desktop',
                    '-r',
                    command_string,
                ]
            else:
                cmd = [
                    self.matlab_path,
                    '-batch',
                    f"cd('{script_dir_unix}'); preprocessing"
                ]

            print(f"Running MATLAB command in background: {' '.join(cmd)}")

            creation_flags = 0
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creation_flags = subprocess.CREATE_NO_WINDOW

            stdout = None
            stderr = None
            if self.show_console:
                result = subprocess.run(
                    cmd,
                    timeout=600,
                    cwd=self.script_dir,
                    creationflags=creation_flags if creation_flags else 0
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    cwd=self.script_dir,
                    creationflags=creation_flags if creation_flags else 0
                )
                stdout = result.stdout
                stderr = result.stderr

            # Emit the result
            self.finished.emit({
                'returncode': result.returncode,
                'stdout': stdout,
                'stderr': stderr
            })

        except subprocess.TimeoutExpired:
            self.finished.emit({
                'returncode': -1,
                'stdout': '',
                'stderr': 'Process timed out after 10 minutes'
            })
        except Exception as e:
            self.finished.emit({
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            })


class MatlabExecutor(QObject):
    """Class to handle MATLAB script execution and communicate with QML"""
    
    # Signal to send output to QML
    outputChanged = pyqtSignal(str)
    configSaved = pyqtSignal(str)  # Signal for save confirmation
    fileExplorerRefresh = pyqtSignal()  # Signal to refresh file explorer
    processingFinished = pyqtSignal()  # Signal when ICA processing is complete
    scriptFinished = pyqtSignal(str)  # Signal for async script result
    
    def __init__(self):
        super().__init__()
        self._output = "No MATLAB output yet..."
        # Load the current data directory from the MATLAB script at startup
        self._current_data_dir = self.getCurrentDataDirectory()
        self._worker_thread = None  # For background MATLAB execution
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._preprocessing_qml_path = os.path.join(
            self._project_root,
            "features",
            "preprocessing",
            "qml",
            "preprocessing_page.qml",
        )
        self._analysis_processing_qml_path = os.path.join(
            self._project_root,
            "features",
            "analysis",
            "qml",
            "processing_page.qml",
        )
        self._option_store = DropdownOptionStore()
        
        # Initialize PreprocessBridge for classification data loading
        self._preprocess_bridge = PreprocessBridge(data_folder=self._current_data_dir or "data/")

    def _update_dropdown_state_in_qml(self, dropdown_id: str, new_state: str) -> bool:
        """Update the dropdownState property for a specific dropdown in the QML file."""
        try:
            if not os.path.exists(self._preprocessing_qml_path):
                print(f"QML file not found when updating state: {self._preprocessing_qml_path}")
                return False

            with open(self._preprocessing_qml_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Match the specific dropdown block and replace its dropdownState value
            pattern = rf'(id\s*:\s*{re.escape(dropdown_id)}[\s\S]*?dropdownState\s*:\s*")(?:[^"]+)(")'
            new_content, count = re.subn(pattern, rf'\1{new_state}\2', content, count=1)

            if count == 0:
                print(f"Could not update dropdownState for {dropdown_id} in QML file")
                return False

            with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            return True

        except Exception as e:
            print(f"Error updating dropdown state for {dropdown_id}: {str(e)}")
            return False

    @pyqtSlot(str, str, result=bool)
    def setDropdownState(self, dropdown_id: str, new_state: str) -> bool:
        """Public slot for QML to persist dropdown state changes."""
        return self._update_dropdown_state_in_qml(dropdown_id, new_state)

    # ------------------------------------------------------------------
    # Custom dropdown persistence helpers
    # ------------------------------------------------------------------

    def _escape_qml_string(self, value: str) -> str:
        return value.replace('\\', '\\\\').replace('"', '\\"') if value else ""

    def _format_qml_list(self, items) -> str:
        if not items:
            return "[]"
        escaped = [f'"{self._escape_qml_string(str(item))}"' for item in items if str(item)]
        return "[" + ", ".join(escaped) + "]"

    def _coerce_to_list(self, payload) -> list:
        if isinstance(payload, (list, tuple)):
            return [str(item) for item in payload if str(item)]

        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped:
                return []

            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if str(item)]
            except json.JSONDecodeError:
                items = [item.strip() for item in stripped.split(',') if item.strip()]
                if items:
                    return items

            return [stripped]

        return []

    def _get_custom_dropdown_block_positions(self, content: str):
        pattern = re.compile(r'(\n\s*DropdownTemplate\s*\{\s*id\s*:\s*(customDropdown\d+)[\s\S]*?\n\s*\})')
        positions = {}
        for match in pattern.finditer(content):
            block_id = match.group(2)
            positions[block_id] = (match.start(1), match.end(1))
        return positions

    def _locate_custom_container_bounds(self, content: str):
        marker = "id: customDropdownContainer"
        marker_index = content.find(marker)
        if marker_index == -1:
            return -1, -1

        open_brace_index = content.rfind('{', 0, marker_index)
        if open_brace_index == -1:
            return -1, -1

        depth = 0
        for idx in range(open_brace_index, len(content)):
            char = content[idx]
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return open_brace_index, idx
        return open_brace_index, -1

    def _next_custom_dropdown_index(self, existing_ids) -> int:
        max_index = 0
        for dropdown_id in existing_ids:
            try:
                suffix = int(re.findall(r'(\d+)$', dropdown_id)[0])
                max_index = max(max_index, suffix)
            except (IndexError, ValueError):
                continue
        return max_index + 1 if max_index >= 0 else 1

    def _build_custom_dropdown_snippet(
        self,
        dropdown_id: str,
        label: str,
        matlab_property: str,
        is_multi_select: bool,
        max_selections: int,
        all_items,
        selected_items,
    ) -> str:
        label = label.strip() or dropdown_id
        matlab_property = matlab_property.strip()
        if matlab_property and not matlab_property.startswith("cfg."):
            matlab_property = f"cfg.{matlab_property}"

        all_items_list = self._coerce_to_list(all_items)
        selected_items_list = self._coerce_to_list(selected_items)

        qml_all_items = self._format_qml_list(all_items_list)
        qml_selected_items = self._format_qml_list(selected_items_list)
        qml_model = "[]" if is_multi_select else qml_all_items

        escaped_label = self._escape_qml_string(label)
        escaped_property = self._escape_qml_string(matlab_property)

        lines = [
            "",
            "            DropdownTemplate {",
            f"                id: {dropdown_id}",
            f"                property string persistentId: \"{dropdown_id}\"",
            f"                property string customLabel: \"{escaped_label}\"",
            "                property bool persistenceConnected: false",
            f"                label: \"{escaped_label}\"",
            f"                matlabProperty: \"{escaped_property}\"",
            f"                matlabPropertyDraft: \"{escaped_property}\"",
            "                hasAddFeature: true",
            f"                isMultiSelect: {'true' if is_multi_select else 'false'}",
            f"                maxSelections: {max_selections}",
            f"                model: {qml_model}",
            f"                allItems: {qml_all_items}",
            f"                selectedItems: {qml_selected_items}",
            '                addPlaceholder: "Add option..."',
            '                dropdownState: "default"',
            '                anchors.left: parent.left',
            "            }\n",
        ]

        return "\n".join(lines)

    def _insert_custom_dropdown_snippet(self, content: str, snippet: str):
        start, end = self._locate_custom_container_bounds(content)
        if start == -1 or end == -1:
            print("Custom dropdown container not found in QML when inserting snippet.")
            return content, False

        insertion_point = end
        updated_content = content[:insertion_point] + snippet + content[insertion_point:]
        return updated_content, True

    def _replace_custom_dropdown_block(self, content: str, dropdown_id: str, snippet: str):
        positions = self._get_custom_dropdown_block_positions(content)
        if dropdown_id not in positions:
            return content, False

        start, end = positions[dropdown_id]
        snippet_to_use = snippet if snippet.startswith("\n") else "\n" + snippet
        updated_content = content[:start] + snippet_to_use + content[end:]
        return updated_content, True

    def _remove_custom_dropdown_block(self, content: str, dropdown_id: str):
        positions = self._get_custom_dropdown_block_positions(content)
        if dropdown_id not in positions:
            return content, False

        start, end = positions[dropdown_id]
        updated_content = content[:start] + content[end:]
        return updated_content, True

    def _get_preprocess_data_script_path(self) -> Optional[str]:
        """Return the absolute path to preprocess_data.m, preferring the source tree."""
        candidates = [
            os.path.join(self._project_root, "features", "preprocessing", "matlab", "preprocess_data.m"),
            resource_path("preprocessing/preprocess_data.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate

        print("Unable to resolve preprocess_data.m path.")
        return None

    def _get_timelock_script_path(self) -> Optional[str]:
        """Return the absolute path to timelock_func.m if it exists."""
        candidates = [
            os.path.join(self._project_root, "features", "analysis", "matlab", "ERP", "timelock_func.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        print("Unable to resolve timelock_func.m path.")
        return None

    def _get_spectral_script_path(self) -> Optional[str]:
        """Return the absolute path to spectralanalysis.m if it exists."""
        candidates = [
            os.path.join(self._project_root, "features", "analysis", "matlab", "spectral", "spectralanalysis.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        print("Unable to resolve spectralanalysis.m path.")
        return None

    def _get_timefreq_script_path(self) -> Optional[str]:
        """Return the absolute path to timefreqanalysis.m if it exists."""
        candidates = [
            os.path.join(self._project_root, "features", "analysis", "matlab", "timefrequency", "timefreqanalysis.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        print("Unable to resolve timefreqanalysis.m path.")
        return None

    def _get_spectral_script_path(self) -> Optional[str]:
        """Return the absolute path to spectralanalysis.m if it exists."""
        candidates = [
            os.path.join(self._project_root, "features", "analysis", "matlab", "spectral", "spectralanalysis.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        print("Unable to resolve spectralanalysis.m path.")
        return None

    def _get_timefreq_script_path(self) -> Optional[str]:
        """Return the absolute path to timefreqanalysis.m if it exists."""
        candidates = [
            os.path.join(self._project_root, "features", "analysis", "matlab", "timefrequency", "timefreqanalysis.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        print("Unable to resolve timefreqanalysis.m path.")
        return None

    def _get_channelwise_script_path(self) -> Optional[str]:
        """Return the absolute path to channelwise.m if it exists."""
        candidates = [
            os.path.join(self._project_root, "features", "analysis", "matlab", "connectivity", "channelwise", "channelwise.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        print("Unable to resolve channelwise.m path.")
        return None

    def _get_intertrial_script_path(self) -> Optional[str]:
        """Return the absolute path to intertrialcoherenceanalysis.m if it exists."""
        candidates = [
            os.path.join(self._project_root, "features", "analysis", "matlab", "connectivity", "intertrial", "intertrialcoherenceanalysis.m"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        print("Unable to resolve intertrialcoherenceanalysis.m path.")
        return None

    def _escape_matlab_single_quotes(self, value: str) -> str:
        return value.replace("'", "''") if value else value

    def _is_numeric_like(self, value: str) -> bool:
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _format_matlab_assignment_value(self, values: List[str], use_cell_format: bool) -> str:
        if not values:
            return "[]"

        if use_cell_format or len(values) > 1:
            cell_items = []
            for raw_value in values:
                if raw_value is None:
                    continue
                text_value = str(raw_value).strip()
                if text_value:
                    cell_items.append(f"'{self._escape_matlab_single_quotes(text_value)}'")
            return "{" + " ".join(cell_items) + "}"

        single = str(values[0]) if values else ""
        normalized = single.strip()
        if self._is_numeric_like(normalized):
            return normalized

        lower = normalized.lower()
        if lower in {"true", "false"}:
            return lower

        return f"'{self._escape_matlab_single_quotes(normalized)}'"

    def _format_matlab_numeric_value(self, value) -> str:
        try:
            numeric = float(value)
            if abs(numeric - round(numeric)) < 1e-9:
                return str(int(round(numeric)))
            formatted = f"{numeric:.6f}".rstrip('0').rstrip('.')
            return formatted if formatted else "0"
        except (ValueError, TypeError):
            return str(value)

    def _format_matlab_numeric_range(self, first_value, second_value) -> str:
        formatted_first = self._format_matlab_numeric_value(first_value)
        formatted_second = self._format_matlab_numeric_value(second_value)
        return f"[{formatted_first} {formatted_second}]"

    def _format_matlab_tri_range(self, first_value, second_value, third_value) -> str:
        formatted_first = self._format_matlab_numeric_value(first_value)
        formatted_second = self._format_matlab_numeric_value(second_value)
        formatted_third = self._format_matlab_numeric_value(third_value)
        return f"[{formatted_first} {formatted_second} {formatted_third}]"

    def _format_matlab_colon_range(self, first_value, step_value, third_value) -> str:
        formatted_first = self._format_matlab_numeric_value(first_value)
        formatted_step = self._format_matlab_numeric_value(step_value)
        formatted_third = self._format_matlab_numeric_value(third_value)
        return f"{formatted_first}:{formatted_step}:{formatted_third}"

    def _should_use_colon_format(self, matlab_property: str) -> bool:
        """Determine if a property should be saved in colon syntax format."""
        # Properties that represent ranges/sequences should use colon format
        colon_properties = ['cfg.toi', 'cfg.foi', 'cfg.latency', 'cfg.frequency', 'cfg.time']
        return matlab_property in colon_properties

    def _replace_or_insert_matlab_assignment(self, content: str, property_name: str, formatted_value: str):
        pattern = rf"(?m)^(\s*{re.escape(property_name)}\s*=\s*)(.*)$"

        def _replacement(match: re.Match) -> str:
            prefix = match.group(1)
            remainder = match.group(2)

            comment = ""
            if '%' in remainder:
                comment_index = remainder.find('%')
                comment = remainder[comment_index:].rstrip()
                remainder = remainder[:comment_index]

            new_line = f"{prefix}{formatted_value};"
            if comment:
                if not comment.startswith(' '):
                    new_line += ' '
                new_line += comment

            return new_line

        new_content, count = re.subn(pattern, _replacement, content, count=1)
        if count:
            return True, new_content

        insertion_pattern = r'(?m)^\s*prepped_data\s*=\s*ft_preprocessing'
        match = re.search(insertion_pattern, content)
        
        if not match:
             # Try finding the loop start in preprocessing.m
             insertion_pattern = r'(?m)^\s*for\s+i\s*=\s*1:length\(files\)'
             match = re.search(insertion_pattern, content)

        new_line = f"{property_name} = {formatted_value};\n"
        if match:
            idx = match.start()
            return False, content[:idx] + new_line + content[idx:]

        if content and not content.endswith('\n'):
            content += '\n'

        return False, content + new_line

    def _remove_matlab_assignment(self, content: str, property_name: str):
        pattern = rf"(?m)^\s*{re.escape(property_name)}\s*=.*(?:\n|$)"
        new_content, count = re.subn(pattern, "", content, count=1)
        if count:
            # Clean up excessive blank lines introduced by removal
            new_content = re.sub(r'\n{3,}', '\n\n', new_content)
            return True, new_content
        return False, content
    
    def _comment_matlab_assignment(self, content: str, property_name: str):
        """Comment out a MATLAB assignment line."""
        # Match the line, preserving existing comments
        pattern = rf"(?m)^(\s*)({re.escape(property_name)}\s*=.*)$"
        
        def _add_comment(match: re.Match) -> str:
            indent = match.group(1)
            line = match.group(2)
            # Don't double-comment
            if line.strip().startswith('%'):
                return match.group(0)
            return f"{indent}% {line}"
        
        new_content, count = re.subn(pattern, _add_comment, content, count=1)
        return count > 0, new_content
    
    def _uncomment_matlab_assignment(self, content: str, property_name: str):
        """Uncomment a MATLAB assignment line."""
        # Match commented line
        pattern = rf"(?m)^(\s*)%\s*({re.escape(property_name)}\s*=.*)$"
        
        def _remove_comment(match: re.Match) -> str:
            indent = match.group(1)
            line = match.group(2)
            return f"{indent}{line}"
        
        new_content, count = re.subn(pattern, _remove_comment, content, count=1)
        return count > 0, new_content
    
    @pyqtSlot(result=float)
    def getCurrentPrestim(self):
        """Read the current prestim value from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return 0.5

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.trialdef\.prestim\s*=\s*([\d.]+);'
            match = re.search(pattern, content)
            if match:
                return float(match.group(1))
            return 0.5  # default fallback
        except:
            return 0.5
    
    @pyqtSlot(result=float)
    def getCurrentPoststim(self):
        """Read the current poststim value from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return 1.0

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.trialdef\.poststim\s*=\s*([\d.]+);'
            match = re.search(pattern, content)
            if match:
                return float(match.group(1))
            return 1.0  # default fallback
        except:
            return 1.0
    
    @pyqtSlot(result=str)
    def getCurrentTrialfun(self):
        """Read the current trialfun value from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return "ft_trialfun_general"

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.trialfun\s*=\s*\'([^\']+)\';'
            match = re.search(pattern, content)
            if match:
                return match.group(1)
            return "ft_trialfun_general"  # default fallback
        except:
            return "ft_trialfun_general"
    
    @pyqtSlot(result=str)
    def getCurrentEventtype(self):
        """Read the current eventtype value from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return "Stimulus"

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.trialdef\.eventtype\s*=\s*\'([^\']+)\';'
            match = re.search(pattern, content)
            if match:
                return match.group(1)
            return "Stimulus"  # default fallback
        except:
            return "Stimulus"
    
    @pyqtSlot(result=list)
    def getCurrentEventvalue(self):
        """Read the current eventvalue array from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return ["S200", "S201", "S202"]

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.trialdef\.eventvalue\s*=\s*\{([^}]+)\};'
            match = re.search(pattern, content)
            if match:
                # Extract the values and clean them up
                values_str = match.group(1)
                # Remove quotes and split by spaces/commas
                values = re.findall(r"'([^']+)'", values_str)
                return values
            return ["S200", "S201", "S202"]  # default fallback
        except:
            return ["S200", "S201", "S202"]
    
    @pyqtSlot(result=bool)
    def getCurrentDemean(self):
        """Read the current demean setting from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return True

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.demean\s*=\s*\'([^\']+)\';'
            match = re.search(pattern, content)
            if match:
                return match.group(1).lower() == 'yes'
            return True  # default to True (yes)
        except:
            return True
    
    @pyqtSlot(result=list)
    def getCurrentBaselineWindow(self):
        """Read the current baseline window from preprocess_data.m (including commented lines)"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return [-0.2, 0]

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # First try to find uncommented baseline window
            pattern = r'cfg\.baselinewindow\s*=\s*\[([^\]]+)\];'
            match = re.search(pattern, content)
            
            if match:
                values_str = match.group(1)
                values = [float(x.strip()) for x in values_str.split()]
                return values
            
            # If not found, look for commented baseline window
            commented_pattern = r'%\s*cfg\.baselinewindow\s*=\s*\[([^\]]+)\];'
            commented_match = re.search(commented_pattern, content)
            
            if commented_match:
                values_str = commented_match.group(1)
                values = [float(x.strip()) for x in values_str.split()]
                return values
                
            return [-0.2, 0]  # default values
        except:
            return [-0.2, 0]

    @pyqtSlot(result=bool)
    def getCurrentDftfilter(self):
        """Read the current dftfilter setting from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return True

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.dftfilter\s*=\s*\'([^\']+)\';'
            match = re.search(pattern, content)
            if match:
                return match.group(1).lower() == 'yes'
            return True  # default to True (yes)
        except:
            return True
    
    @pyqtSlot(result=list)
    def getCurrentDftfreq(self):
        """Read the current dftfreq from preprocess_data.m"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return [50, 60]

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            pattern = r'cfg\.dftfreq\s*=\s*\[([^\]]+)\];'
            match = re.search(pattern, content)
            if match:
                values_str = match.group(1)
                values = [float(x.strip()) for x in values_str.split()]
                return values
            return [50, 60]  # default values
        except:
            return [50, 60]

    @pyqtSlot(result="QVariant")
    def getCurrentErpLatency(self):
        """Read the current cfg.latency range from timelock_func.m."""
        try:
            script_path = self._get_timelock_script_path()
            if not script_path:
                return []

            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()

            pattern = r'cfg\.latency\s*=\s*\[([^\]]+)\];'
            match = re.search(pattern, content)
            if not match:
                return []

            values = match.group(1).split()
            parsed = []
            for value in values:
                try:
                    parsed.append(float(value))
                except ValueError:
                    continue

            return parsed

        except Exception as e:
            print(f"Error reading cfg.latency range: {str(e)}")
            return []
    
    @pyqtSlot(result=str)
    def getCurrentDataDirectory(self):
        """Read the current data_dir from preprocessing.m"""
        try:
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing", "matlab", "preprocessing.m")
            
            with open(script_path, 'r') as file:
                content = file.read()
            
            # Look for the data_dir line
            import re
            pattern = r"data_dir\s*=\s*'([^']+)';"
            match = re.search(pattern, content)
            
            if match:
                matlab_path = match.group(1)
                
                # Handle file:/// URLs
                if matlab_path.startswith('file:///'):
                    matlab_path = matlab_path[8:]  # Remove file:/// prefix
                    matlab_path = matlab_path.replace('/', '\\')  # Convert to Windows paths
                
                return matlab_path
            else:
                # If no path found or using pwd, return empty string
                return ""
                
        except Exception as e:
            print(f"Error reading current data directory: {str(e)}")
            return ""
    
    @pyqtSlot(str)
    def updateDataDirectory(self, folder_path):
        """Update the data_dir in preprocessing.m with the selected folder path."""
        try:
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "features",
                "preprocessing",
                "matlab",
                "preprocessing.m",
            )

            # Normalize incoming paths from QML (often prefixed with file:///)
            normalized = folder_path or ""
            if normalized.startswith("file:///"):
                normalized = normalized[8:]
            elif normalized.startswith("file://"):
                normalized = normalized[7:]
            normalized = normalized.strip()

            print(f"updateDataDirectory: incoming='{folder_path}' normalized='{normalized}' script='{script_path}'")

            # Read the current file
            with open(script_path, "r", encoding="utf-8") as file:
                content = file.read()

            # Decide replacement (MATLAB accepts forward slashes on Windows)
            if normalized:
                matlab_path = normalized.replace("\\", "/")
                data_dir_replacement = f"data_dir = '{matlab_path}';"
                log_path = matlab_path
            else:
                data_dir_replacement = "data_dir = pwd;"
                log_path = "pwd (current directory)"

            # Replace only the data_dir line; if missing, append it
            pattern = r"^\s*data_dir\s*=\s*[^;]+;"
            new_content, count = re.subn(pattern, data_dir_replacement, content, flags=re.MULTILINE)
            if count == 0:
                if not new_content.endswith("\n"):
                    new_content += "\n"
                new_content += data_dir_replacement + "\n"

            print(f"updateDataDirectory: replacements={count} writing value='{data_dir_replacement}'")

            with open(script_path, "w", encoding="utf-8") as file:
                file.write(new_content)

            self._current_data_dir = normalized
            
            # Update PreprocessBridge with the new data path
            if hasattr(self, '_preprocess_bridge'):
                self._preprocess_bridge.set_data_path(normalized)
                print(f"PreprocessBridge data path updated to: {normalized}")
            
            print(f"Data directory updated to: {log_path}")

        except Exception as e:
            print(f"Error updating data directory: {str(e)}")

    @pyqtSlot(result=str)
    def getCurrentFieldtripPath(self):
        """Read the current FieldTrip path from preprocessing.m"""
        try:
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing", "matlab", "preprocessing.m")
            with open(script_path, 'r') as file:
                content = file.read()
            
            # Look for the addpath line with FieldTrip
            pattern = r"addpath\('([^']+)'\);"
            match = re.search(pattern, content)
            if match:
                fieldtrip_path = match.group(1)
                # Convert forward slashes to backslashes for Windows display
                return fieldtrip_path.replace('/', '\\')
            return "C:\\FIELDTRIP"  # default fallback
        except Exception as e:
            print(f"Error reading FieldTrip path: {e}")
            return "C:\\FIELDTRIP"

    @pyqtSlot(str)
    def updateFieldtripPath(self, folder_path):
        """Update the FieldTrip path in preprocessing.m with the selected folder path"""
        try:
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing", "matlab", "preprocessing.m")
            
            # Convert QML URL to local path if needed
            if folder_path.startswith("file:///"):
                folder_path = folder_path[8:]  # Remove file:/// prefix
            
            # Read the current file
            with open(script_path, 'r') as file:
                content = file.read()
            
            # Convert Windows path to MATLAB format (forward slashes work in MATLAB)
            matlab_path = folder_path.replace('\\', '/')
            
            # Replace the addpath line
            addpath_pattern = r"addpath\('([^']+)'\);"
            addpath_replacement = f"addpath('{matlab_path}');"
            
            content = re.sub(addpath_pattern, addpath_replacement, content)
            
            # Write the updated content back to the file
            with open(script_path, 'w') as file:
                file.write(content)
            
            success_msg = f"FieldTrip path updated to: {folder_path}"
            print(success_msg)
            self.configSaved.emit(success_msg)
            
        except Exception as e:
            error_msg = f"Error updating FieldTrip path: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)

    @pyqtSlot(float, float, str, str, list, list, bool, float, float, bool, float, float)
    def saveConfiguration(self, prestim_value, poststim_value, trialfun_value, eventtype_value, selected_channels, eventvalue_list, demean_enabled, baseline_start, baseline_end, dftfilter_enabled, dftfreq_start, dftfreq_end):
        """Save prestim, poststim, trialfun, eventtype, eventvalue, demean, baseline window, dftfilter, dftfreq, and selected channels to the MATLAB script"""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                raise FileNotFoundError("preprocess_data.m not found")
            
            # Read the current file
            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Replace the prestim line
            prestim_pattern = r'cfg\.trialdef\.prestim\s*=\s*[\d.]+;\s*%\s*in\s*seconds'
            prestim_replacement = f'cfg.trialdef.prestim    = {prestim_value:.1f}; % in seconds'
            content = re.sub(prestim_pattern, prestim_replacement, content)
            
            # Replace the poststim line
            poststim_pattern = r'cfg\.trialdef\.poststim\s*=\s*[\d.]+;\s*%\s*in\s*seconds'
            poststim_replacement = f'cfg.trialdef.poststim   = {poststim_value:.1f}; % in seconds'
            content = re.sub(poststim_pattern, poststim_replacement, content)
            
            # Replace the trialfun line
            trialfun_pattern = r'cfg\.trialfun\s*=\s*\'[^\']+\';\s*%.*'
            trialfun_replacement = f'cfg.trialfun             = \'{trialfun_value}\';     % it will call your function and pass the cfg'
            content = re.sub(trialfun_pattern, trialfun_replacement, content)
            
            # Replace the eventtype line
            eventtype_pattern = r'cfg\.trialdef\.eventtype\s*=\s*\'[^\']+\';'
            eventtype_replacement = f'cfg.trialdef.eventtype  = \'{eventtype_value}\';'
            content = re.sub(eventtype_pattern, eventtype_replacement, content)
            
            # Replace the eventvalue line
            if eventvalue_list:
                eventvalue_str = "' '".join(eventvalue_list)
                eventvalue_replacement = f"cfg.trialdef.eventvalue = {{'{eventvalue_str}'}};"
            else:
                eventvalue_replacement = "cfg.trialdef.eventvalue = {'S200' 'S201' 'S202'};"
            
            eventvalue_pattern = r'cfg\.trialdef\.eventvalue\s*=\s*\{[^}]+\};'
            content = re.sub(eventvalue_pattern, eventvalue_replacement, content)
            
            # Replace the demean line
            demean_value = 'yes' if demean_enabled else 'no'
            demean_pattern = r"cfg\.demean\s*=\s*'[^']*'\s*;"
            demean_replacement = f"cfg.demean = '{demean_value}';"
            content = re.sub(demean_pattern, demean_replacement, content)
            
            # Handle the baseline window line based on demean setting
            if demean_enabled:
                # Uncomment and update the baseline window line if demean is enabled
                # First handle commented lines
                commented_baseline_pattern = r'%\s*cfg\.baselinewindow\s*=\s*\[[^\]]*\]\s*;'
                baseline_replacement = f'cfg.baselinewindow = [{baseline_start:.1f} {baseline_end:.1f}];'
                content = re.sub(commented_baseline_pattern, baseline_replacement, content)
                
                # Then handle uncommented lines  
                baseline_pattern = r'cfg\.baselinewindow\s*=\s*\[[^\]]*\]\s*;'
                content = re.sub(baseline_pattern, baseline_replacement, content)
            else:
                # Comment out the baseline window line if demean is disabled
                baseline_pattern = r'cfg\.baselinewindow\s*=\s*\[[^\]]*\]\s*;'
                baseline_replacement = f'% cfg.baselinewindow = [{baseline_start:.1f} {baseline_end:.1f}];'
                content = re.sub(baseline_pattern, baseline_replacement, content)
            
            # Handle the dftfilter line
            dftfilter_value = 'yes' if dftfilter_enabled else 'no'
            dftfilter_pattern = r"cfg\.dftfilter\s*=\s*'[^']*'\s*;"
            dftfilter_replacement = f"cfg.dftfilter = '{dftfilter_value}';"
            content = re.sub(dftfilter_pattern, dftfilter_replacement, content)
            
            # Handle the dftfreq line based on dftfilter setting
            if dftfilter_enabled:
                # Uncomment and update the dftfreq line if dftfilter is enabled
                # First handle commented lines
                commented_dftfreq_pattern = r'%\s*cfg\.dftfreq\s*=\s*\[[^\]]*\]\s*;'
                dftfreq_replacement = f'cfg.dftfreq = [{dftfreq_start:.0f} {dftfreq_end:.0f}];'
                content = re.sub(commented_dftfreq_pattern, dftfreq_replacement, content)
                
                # Then handle uncommented lines  
                dftfreq_pattern = r'cfg\.dftfreq\s*=\s*\[[^\]]*\]\s*;'
                content = re.sub(dftfreq_pattern, dftfreq_replacement, content)
            else:
                # Comment out the dftfreq line if dftfilter is disabled
                dftfreq_pattern = r'cfg\.dftfreq\s*=\s*\[[^\]]*\]\s*;'
                dftfreq_replacement = f'% cfg.dftfreq = [{dftfreq_start:.0f} {dftfreq_end:.0f}];'
                content = re.sub(dftfreq_pattern, dftfreq_replacement, content)
            
            # Write the updated content back to the file
            with open(script_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            # Also update the preprocessing.m file with selected channels
            self.updateSelectedChannels(selected_channels)
            
            baseline_info = f" baseline: [{baseline_start:.1f} {baseline_end:.1f}]" if demean_enabled else ""
            success_msg = f"Configuration saved!\nprestim: {prestim_value:.1f}s, poststim: {poststim_value:.1f}s\ntrialfun: {trialfun_value}\neventtype: {eventtype_value}\neventvalue: {', '.join(eventvalue_list)}\ndemean: {'yes' if demean_enabled else 'no'}{baseline_info}\nchannels: {', '.join(selected_channels)}"
            print(success_msg)
            self.configSaved.emit(success_msg)
            
        except Exception as e:
            error_msg = f"Error saving configuration: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
    
    @pyqtSlot(str, 'QVariant', bool, str, result=bool)
    def saveDropdownPropertyToMatlab(self, matlab_property, selected_values, use_cell_format, module_name=""):
        """Persist a dropdown selection as an assignment line in preprocess_data.m."""
        try:
            normalized_property = (matlab_property or "").strip()
            if not normalized_property:
                return False

            if not normalized_property.startswith("cfg."):
                # Check if it's a standalone variable (like accepted_channels)
                # If module is Preprocessing and property is accepted_channels, it's standalone
                if module_name == "Preprocessing" and normalized_property == "accepted_channels":
                    pass # Keep as is
                else:
                    normalized_property = f"cfg.{normalized_property}"

            # Prevent saving of internal variables like ft_paths
            if normalized_property == "cfg.ft_paths":
                return False

            if hasattr(selected_values, 'toVariant'):
                selected_values = selected_values.toVariant()

            values_list = []
            if isinstance(selected_values, (list, tuple)):
                for value in selected_values:
                    value_str = str(value).strip()
                    if value_str:
                        values_list.append(value_str)
            elif isinstance(selected_values, str):
                value_str = selected_values.strip()
                if value_str:
                    values_list.append(value_str)
            elif selected_values is not None:
                value_str = str(selected_values).strip()
                if value_str and value_str.lower() not in {"undefined", "null"}:
                    values_list.append(value_str)

            if not values_list:
                info_msg = f"No values provided for {normalized_property}; skipping update."
                print(info_msg)
                self.configSaved.emit(info_msg)
                return False

            # Determine target script based on module
            target_scripts = []
            
            if module_name == "Preprocessing":
                if normalized_property == "accepted_channels":
                     # Special case for accepted_channels in preprocessing.m
                     script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing", "matlab", "preprocessing.m")
                     target_scripts.append(("preprocessing.m", script_path))
                else:
                    preprocess_path = self._get_preprocess_data_script_path()
                    if preprocess_path:
                        target_scripts.append(("preprocess_data.m", preprocess_path))
            elif module_name == "Spectral Analysis":
                 spectral_path = self._get_spectral_script_path()
                 if spectral_path:
                     target_scripts.append(("spectralanalysis.m", spectral_path))
            elif module_name == "Time-Frequency Analysis":
                 timefreq_path = self._get_timefreq_script_path()
                 if timefreq_path:
                     target_scripts.append(("timefreqanalysis.m", timefreq_path))
            elif module_name == "ERP Analysis":
                decomp_path = self._get_timelock_script_path()
                if decomp_path:
                    target_scripts.append(("timelock_func.m", decomp_path))
            else:
                # Fallback logic
                if not module_name:
                    if normalized_property in ["cfg.output", "cfg.method", "cfg.taper", "cfg.pad", "cfg.foi"]:
                         spectral_path = self._get_spectral_script_path()
                         if spectral_path:
                             target_scripts.append(("spectralanalysis.m", spectral_path))
                    elif normalized_property in ["cfg.toi", "cfg.width", "cfg.baselinetype", "cfg.parameter"]:
                         timefreq_path = self._get_timefreq_script_path()
                         if timefreq_path:
                             target_scripts.append(("timefreqanalysis.m", timefreq_path))
                    elif normalized_property == "cfg.latency":
                        decomp_path = self._get_timelock_script_path()
                        if decomp_path:
                            target_scripts.append(("timelock_func.m", decomp_path))
                    else:
                        # DANGEROUS FALLBACK REMOVED
                        print(f"Warning: No target script found for {normalized_property} (Module: {module_name})")

            if not target_scripts:
                error_msg = f"No script targets available for {normalized_property}."
                print(error_msg)
                # Suppress UI error message for missing targets to avoid annoyance
                # self.configSaved.emit(error_msg)
                return False

            messages = []
            any_changes = False
            success_count = 0

            for display_name, script_path in target_scripts:
                try:
                    # Adjust property name based on file
                    current_property = normalized_property
                    if display_name == "preprocessing.m" and normalized_property == "cfg.accepted_channels":
                        current_property = "accepted_channels"
                    elif display_name == "preprocess_data.m" and normalized_property == "accepted_channels":
                        current_property = "cfg.accepted_channels"
                    elif display_name == "preprocess_data.m" and normalized_property == "cfg.accepted_channels":
                        current_property = "cfg.accepted_channels"
                    elif display_name == "preprocessing.m" and normalized_property == "accepted_channels":
                        current_property = "accepted_channels"

                    with open(script_path, 'r', encoding='utf-8') as file:
                        content = file.read()

                    formatted_value = self._format_matlab_assignment_value(values_list, use_cell_format)
                    replaced, new_content = self._replace_or_insert_matlab_assignment(content, current_property, formatted_value)

                    if new_content == content:
                        info_msg = f"No changes required for {current_property} in {display_name}"
                        print(info_msg)
                        # messages.append(info_msg)
                        success_count += 1
                        continue

                    with open(script_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

                    any_changes = True
                    success_count += 1
                    status = "Updated" if replaced else "Inserted"
                    success_msg = f"{status} {current_property} = {formatted_value} in {display_name}"
                    print(success_msg)
                    messages.append(success_msg)
                except Exception as inner_error:
                    error_msg = f"Error updating {display_name} for {normalized_property}: {str(inner_error)}"
                    print(error_msg)
                    messages.append(error_msg)

            if not messages:
                if success_count > 0:
                    return True
                messages.append(f"No script updates performed for {normalized_property}.")

            summary = "; ".join(messages)
            self.configSaved.emit(summary)
            return success_count > 0

        except Exception as e:
            error_msg = f"Error saving {matlab_property} to preprocess_data.m: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    @pyqtSlot(str, float, float, str, result=bool)
    def saveRangeSliderBoundsToJson(self, matlab_property, min_val, max_val, module_name=""):
        """Save the min/max bounds of a range slider to the JSON configuration."""
        try:
            # Strip cfg. prefix if present
            param_name = matlab_property.strip()
            if param_name.startswith("cfg."):
                param_name = param_name[4:]
            
            # Update the option store
            if self._option_store.update_range_limits(param_name, min_val, max_val, module_name):
                self._option_store.save()
                print(f"Updated bounds for {param_name}: min={min_val}, max={max_val}")
                return True
            return False
        except Exception as e:
            print(f"Error saving range slider bounds: {e}")
            return False

    @pyqtSlot(str, str, str, bool, result=bool)
    def addCustomOption(self, matlab_property, new_option, module_name, is_multi_select=False):
        """Add a custom option to the persistent JSON store."""
        try:
            # Strip cfg. prefix if present
            param_name = matlab_property.strip()
            if param_name.startswith("cfg."):
                param_name = param_name[4:]
            
            # Try to preserve the current value in the file if it's not in the options list
            current_val = self._get_current_value_from_file(module_name, param_name)
            if current_val:
                # Add current value first so it appears in the list
                self._option_store.add_option(param_name, current_val, module_name, is_multi_select)

            if self._option_store.add_option(param_name, new_option, module_name, is_multi_select):
                self._option_store.save()
                msg = f"Added custom option '{new_option}' to {param_name}"
                print(msg)
                self.configSaved.emit(msg)
                return True
            return False
        except Exception as e:
            error_msg = f"Error adding custom option: {e}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    @pyqtSlot(str, str, str, result=bool)
    def removeCustomOption(self, matlab_property, option_to_remove, module_name):
        """Remove a custom option from the persistent JSON store."""
        try:
            # Strip cfg. prefix if present
            param_name = matlab_property.strip()
            if param_name.startswith("cfg."):
                param_name = param_name[4:]
            
            if self._option_store.remove_option(param_name, option_to_remove, module_name):
                self._option_store.save()
                msg = f"Removed custom option '{option_to_remove}' from {param_name}"
                print(msg)
                self.configSaved.emit(msg)
                return True
            return False
        except Exception as e:
            error_msg = f"Error removing custom option: {e}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    def _get_current_value_from_file(self, module_name, param_name):
        """Helper to read the current value of a parameter from the MATLAB file."""
        try:
            mapper = ModuleParameterMapper()
            file_paths = mapper.get_matlab_file(module_name)
            
            if isinstance(file_paths, str):
                file_paths = [file_paths]
            elif not file_paths:
                return None
                
            parser = MatlabParameterParser()
            
            for rel_path in file_paths:
                # Handle both forward and backslashes in paths
                rel_path = rel_path.replace('/', os.sep).replace('\\', os.sep)
                abs_path = os.path.join(self._project_root, rel_path)
                
                if not os.path.exists(abs_path):
                    continue
                    
                params = parser.parse_file(abs_path)
                if param_name in params:
                    info = params[param_name]
                    # Only return string values for now
                    if info.get('type') == 'string':
                        return str(info.get('value', ''))
            return None
        except Exception as e:
            print(f"Error reading current value for {param_name}: {e}")
            return None

    def _save_trial_time_window(self, prestim, poststim):
        """Special handler for saving trial time window (prestim/poststim)."""
        try:
            script_path = self._get_preprocess_data_script_path()
            if not script_path:
                return False
                
            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Update prestim
            # cfg.trialdef.prestim = -2.0;
            pattern_pre = r'(cfg\.trialdef\.prestim\s*=\s*)([0-9\.\-]+)(;.*)'
            if re.search(pattern_pre, content):
                content = re.sub(pattern_pre, f"\\g<1>{prestim}\\g<3>", content)
            else:
                print("Warning: cfg.trialdef.prestim not found")
                
            # Update poststim
            # cfg.trialdef.poststim = 2.0;
            pattern_post = r'(cfg\.trialdef\.poststim\s*=\s*)([0-9\.\-]+)(;.*)'
            if re.search(pattern_post, content):
                content = re.sub(pattern_post, f"\\g<1>{poststim}\\g<3>", content)
            else:
                print("Warning: cfg.trialdef.poststim not found")
                
            with open(script_path, 'w', encoding='utf-8') as file:
                file.write(content)
                
            print(f"Updated trial time window: {prestim} to {poststim}")
            return True
        except Exception as e:
            print(f"Error saving trial time window: {e}")
            return False

    @pyqtSlot(str, "QVariant", bool, str, result=bool)
    def saveInputPropertyToMatlab(self, matlab_property, value, is_numeric, module_name=""):
        """Persist an input box value as a MATLAB assignment."""
        try:
            normalized_property = (matlab_property or "").strip()
            if not normalized_property:
                return False

            if not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"

            # Prevent saving of internal variables like ft_paths
            if normalized_property == "cfg.ft_paths":
                return False

            if is_numeric:
                formatted_value = str(value)
            else:
                formatted_value = f"'{value}'"

            return self._save_property_generic(normalized_property, formatted_value, module_name)
        except Exception as e:
            error_msg = f"Error saving input property {matlab_property}: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    @pyqtSlot(str, bool, str, result=bool)
    def saveCheckboxPropertyToMatlab(self, matlab_property, is_checked, module_name=""):
        """Persist a checkbox state as a MATLAB assignment ('yes'/'no')."""
        try:
            normalized_property = (matlab_property or "").strip()
            if not normalized_property:
                return False

            if not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"

            # Prevent saving of internal variables like ft_paths
            if normalized_property == "cfg.ft_paths":
                return False

            # Special handling for demean - when set to 'no', comment out both demean and baselinewindow
            if normalized_property == "cfg.demean" and module_name == "Preprocessing":
                return self._save_demean_with_baseline(is_checked, module_name)

            formatted_value = "'yes'" if is_checked else "'no'"

            return self._save_property_generic(normalized_property, formatted_value, module_name)
        except Exception as e:
            error_msg = f"Error saving checkbox property {matlab_property}: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False
    
    def _save_demean_with_baseline(self, is_checked, module_name):
        """Special handler for demean parameter - comments/uncomments both demean and baselinewindow."""
        try:
            preprocess_path = self._get_preprocess_data_script_path()
            if not preprocess_path:
                print("Could not find preprocess_data.m script path")
                return False
            
            with open(preprocess_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            modified = False
            
            if is_checked:
                # When demean is 'yes', uncomment both lines
                changed1, content = self._uncomment_matlab_assignment(content, "cfg.demean")
                changed2, content = self._uncomment_matlab_assignment(content, "cfg.baselinewindow")
                modified = changed1 or changed2
                
                # Also set the value to 'yes'
                replaced, content = self._replace_or_insert_matlab_assignment(
                    content, "cfg.demean", "'yes'")
                modified = modified or replaced
                
                # Remove any duplicate uncommented baselinewindow lines (keep only the first one)
                content = self._remove_duplicate_assignments(content, "cfg.baselinewindow")
            else:
                # When demean is 'no', comment out both lines AND remove any uncommented duplicates
                changed1, content = self._comment_matlab_assignment(content, "cfg.demean")
                changed2, content = self._comment_matlab_assignment(content, "cfg.baselinewindow")
                
                # Also remove any uncommented baselinewindow lines that might have been added
                removed, content = self._remove_matlab_assignment(content, "cfg.baselinewindow")
                
                modified = changed1 or changed2 or removed
            
            if modified:
                with open(preprocess_path, 'w', encoding='utf-8') as file:
                    file.write(content)
                print(f"Successfully saved demean={'yes' if is_checked else 'no'} with baselinewindow")
                self.configSaved.emit(f"Demean and baselinewindow updated")
                return True
            else:
                print("No changes made to demean/baselinewindow")
                return True
                
        except Exception as e:
            error_msg = f"Error saving demean with baseline: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False
    
    def _remove_duplicate_assignments(self, content: str, property_name: str):
        """Remove duplicate assignments of a property, keeping only the first one."""
        pattern = rf"(?m)^\s*{re.escape(property_name)}\s*=.*(?:\n|$)"
        matches = list(re.finditer(pattern, content))
        
        if len(matches) <= 1:
            return content
        
        # Keep the first match, remove all others
        for match in reversed(matches[1:]):
            content = content[:match.start()] + content[match.end():]
        
        return content

    def _save_property_generic(self, normalized_property, formatted_value, module_name):
        """Generic helper to save a property to the correct script based on module."""
        target_scripts = []
        
        if module_name == "Preprocessing":
            preprocess_path = self._get_preprocess_data_script_path()
            if preprocess_path:
                target_scripts.append(("preprocess_data.m", preprocess_path))
        elif module_name == "Spectral Analysis":
            spectral_path = self._get_spectral_script_path()
            if spectral_path:
                target_scripts.append(("spectralanalysis.m", spectral_path))
        elif module_name == "Time-Frequency Analysis":
            timefreq_path = self._get_timefreq_script_path()
            if timefreq_path:
                target_scripts.append(("timefreqanalysis.m", timefreq_path))
        elif module_name == "ERP Analysis":
            decomp_path = self._get_timelock_script_path()
            if decomp_path:
                target_scripts.append(("timelock_func.m", decomp_path))
        else:
            print(f"Warning: Unknown module {module_name} for property {normalized_property}")
            return False

        if not target_scripts:
            print(f"No script targets available for {normalized_property}.")
            return False

        success_count = 0
        messages = []

        for display_name, script_path in target_scripts:
            try:
                with open(script_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                replaced, new_content = self._replace_or_insert_matlab_assignment(
                    content, normalized_property, formatted_value)

                if new_content == content:
                    success_count += 1
                    continue

                with open(script_path, 'w', encoding='utf-8') as file:
                    file.write(new_content)

                success_count += 1
                status = "Updated" if replaced else "Inserted"
                success_msg = f"{status} {normalized_property} = {formatted_value} in {display_name}"
                print(success_msg)
                messages.append(success_msg)
            except Exception as inner_error:
                print(f"Error updating {display_name}: {inner_error}")

        if messages:
            self.configSaved.emit("; ".join(messages))
            
        return success_count > 0

    @pyqtSlot(str, float, float, str, str, result=bool)
    def saveRangeSliderPropertyToMatlab(self, matlab_property, first_value, second_value, unit, module_name=""):
        """Persist a range slider selection as a MATLAB numeric array assignment."""
        try:
            normalized_property = (matlab_property or "").strip()
            if not normalized_property:
                return False

            if not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"

            # Prevent saving of internal variables like ft_paths
            if normalized_property == "cfg.ft_paths":
                return False

            # Special handling for trial_time_window
            if normalized_property == "cfg.trial_time_window":
                if module_name == "Preprocessing":
                    return self._save_trial_time_window(first_value, second_value)
                else:
                    return False

            formatted_value = self._format_matlab_numeric_range(first_value, second_value)
            unit_suffix = f" {unit}" if unit else ""

            target_scripts = []
            
            # Strict module-based targeting
            if module_name == "Preprocessing":
                preprocess_path = self._get_preprocess_data_script_path()
                if preprocess_path:
                    target_scripts.append(("preprocess_data.m", preprocess_path))
            elif module_name == "Spectral Analysis":
                spectral_path = self._get_spectral_script_path()
                if spectral_path:
                    target_scripts.append(("spectralanalysis.m", spectral_path))
            elif module_name == "Time-Frequency Analysis":
                timefreq_path = self._get_timefreq_script_path()
                if timefreq_path:
                    target_scripts.append(("timefreqanalysis.m", timefreq_path))
            elif module_name == "ERP Analysis":
                decomp_path = self._get_timelock_script_path()
                if decomp_path:
                    target_scripts.append(("timelock_func.m", decomp_path))
            else:
                # Fallback for backward compatibility or unknown modules
                # Only use property-based inference if module_name is not provided
                if not module_name:
                    if normalized_property in ["cfg.output", "cfg.method", "cfg.taper", "cfg.pad", "cfg.foi"]:
                        spectral_path = self._get_spectral_script_path()
                        if spectral_path:
                            target_scripts.append(("spectralanalysis.m", spectral_path))
                    elif normalized_property in ["cfg.toi", "cfg.width", "cfg.baselinetype", "cfg.parameter"]:
                        timefreq_path = self._get_timefreq_script_path()
                        if timefreq_path:
                            target_scripts.append(("timefreqanalysis.m", timefreq_path))
                    elif normalized_property == "cfg.latency":
                        decomp_path = self._get_timelock_script_path()
                        if decomp_path:
                            target_scripts.append(("timelock_func.m", decomp_path))
                    else:
                        # DANGEROUS FALLBACK REMOVED: Do not default to preprocess_data.m
                        print(f"Warning: No target script found for {normalized_property} (Module: {module_name})")
                else:
                    print(f"Warning: Unknown module {module_name} for property {normalized_property}")

            if not target_scripts:
                error_msg = f"No script targets available for {normalized_property}."
                print(error_msg)
                # Suppress UI error message for missing targets to avoid annoyance
                # self.configSaved.emit(error_msg)
                return False

            messages = []
            any_changes = False
            success_count = 0

            for display_name, script_path in target_scripts:
                try:
                    with open(script_path, 'r', encoding='utf-8') as file:
                        content = file.read()

                    replaced, new_content = self._replace_or_insert_matlab_assignment(
                        content, normalized_property, formatted_value)

                    if new_content == content:
                        info_msg = f"No changes required for {normalized_property} in {display_name}"
                        print(info_msg)
                        # messages.append(info_msg)
                        success_count += 1
                        continue

                    with open(script_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

                    any_changes = True
                    success_count += 1
                    status = "Updated" if replaced else "Inserted"
                    success_msg = f"{status} {normalized_property} = {formatted_value}{unit_suffix} in {display_name}"
                    print(success_msg)
                    messages.append(success_msg)
                except Exception as inner_error:
                    error_msg = f"Error updating {display_name} for {normalized_property}: {str(inner_error)}"
                    print(error_msg)
                    messages.append(error_msg)

            if not messages:
                if success_count > 0:
                    return True
                messages.append(f"No script updates performed for {normalized_property}.")

            summary = "; ".join(messages)
            self.configSaved.emit(summary)
            return success_count > 0

        except Exception as e:
            error_msg = f"Error saving range slider {matlab_property}: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    @pyqtSlot(str, float, float, float, str, str, result=bool)
    def saveStepRangeSliderPropertyToMatlab(self, matlab_property, first_value, step_value, second_value, unit, module_name=""):
        """Persist a step range slider selection as a MATLAB colon notation assignment (start:step:end)."""
        try:
            normalized_property = (matlab_property or "").strip()
            if not normalized_property:
                return False

            if not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"

            # Always use colon format for step range sliders
            formatted_value = self._format_matlab_colon_range(first_value, step_value, second_value)
            unit_suffix = f" {unit}" if unit else ""

            target_scripts = []
            
            # Strict module-based targeting
            if module_name == "Spectral Analysis":
                spectral_path = self._get_spectral_script_path()
                if spectral_path:
                    target_scripts.append(("spectralanalysis.m", spectral_path))
            elif module_name == "Time-Frequency Analysis":
                timefreq_path = self._get_timefreq_script_path()
                if timefreq_path:
                    target_scripts.append(("timefreqanalysis.m", timefreq_path))
            elif module_name == "Channel-Wise Coherence Analysis":
                channelwise_path = self._get_channelwise_script_path()
                if channelwise_path:
                    target_scripts.append(("channelwise.m", channelwise_path))
            elif module_name == "Inter-Trial Coherence Analysis":
                intertrial_path = self._get_intertrial_script_path()
                if intertrial_path:
                    target_scripts.append(("intertrialcoherenceanalysis.m", intertrial_path))
            elif module_name == "ERP Analysis":
                erp_path = self._get_timelock_script_path()
                if erp_path:
                    target_scripts.append(("timelock_func.m", erp_path))
            else:
                # Fallback: try to infer from property name
                if normalized_property in ["cfg.foi", "cfg.toi"]:
                    # Could be any frequency analysis - add all potential targets
                    spectral_path = self._get_spectral_script_path()
                    if spectral_path:
                        target_scripts.append(("spectralanalysis.m", spectral_path))
                    timefreq_path = self._get_timefreq_script_path()
                    if timefreq_path:
                        target_scripts.append(("timefreqanalysis.m", timefreq_path))
                    channelwise_path = self._get_channelwise_script_path()
                    if channelwise_path:
                        target_scripts.append(("channelwise.m", channelwise_path))
                    intertrial_path = self._get_intertrial_script_path()
                    if intertrial_path:
                        target_scripts.append(("intertrialcoherenceanalysis.m", intertrial_path))

            if not target_scripts:
                error_msg = f"No script targets available for {normalized_property}."
                print(error_msg)
                return False

            messages = []
            success_count = 0

            for display_name, script_path in target_scripts:
                try:
                    with open(script_path, 'r', encoding='utf-8') as file:
                        content = file.read()

                    # Check if the property already exists in this file
                    property_pattern = rf"(?m)^\s*{re.escape(normalized_property)}\s*="
                    property_exists = re.search(property_pattern, content) is not None

                    # Only proceed if: 1) property exists, OR 2) module_name was explicitly provided
                    if not property_exists and not module_name:
                        # Skip this file - don't insert into files where property doesn't exist
                        # unless we have explicit module context
                        print(f"Skipping {display_name}: {normalized_property} not found and no module context")
                        continue

                    replaced, new_content = self._replace_or_insert_matlab_assignment(
                        content, normalized_property, formatted_value)

                    if new_content == content:
                        info_msg = f"No changes required for {normalized_property} in {display_name}"
                        print(info_msg)
                        success_count += 1
                        continue

                    with open(script_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

                    success_count += 1
                    status = "Updated" if replaced else "Inserted"
                    success_msg = f"{status} {normalized_property} = {formatted_value}{unit_suffix} in {display_name}"
                    print(success_msg)
                    messages.append(success_msg)
                except Exception as inner_error:
                    error_msg = f"Error updating {display_name} for {normalized_property}: {str(inner_error)}"
                    print(error_msg)
                    messages.append(error_msg)

            if not messages:
                if success_count > 0:
                    return True
                messages.append(f"No script updates performed for {normalized_property}.")

            summary = "; ".join(messages)
            self.configSaved.emit(summary)
            return success_count > 0

        except Exception as e:
            error_msg = f"Error saving step range slider {matlab_property}: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    @pyqtSlot(str, float, float, float, float, str, result=bool)
    def saveTriSliderPropertyToMatlab(self, matlab_property, first_value, second_value, third_value, step_value, unit):
        """Persist a tri-slider selection as a MATLAB numeric array assignment."""
        try:
            normalized_property = (matlab_property or "").strip()
            if not normalized_property:
                return False

            if not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"

            # Determine format based on property type
            if self._should_use_colon_format(normalized_property):
                formatted_value = self._format_matlab_colon_range(first_value, step_value, third_value)
            else:
                formatted_value = self._format_matlab_tri_range(first_value, second_value, third_value)

            unit_suffix = f" {unit}" if unit else ""

            target_scripts = []
            preprocess_path = self._get_preprocess_data_script_path()
            if preprocess_path:
                target_scripts.append(("preprocess_data.m", preprocess_path))
            else:
                print("preprocess_data.m not found; cannot persist tri-slider property.")

            if not target_scripts:
                error_msg = f"No script targets available for {normalized_property}."
                print(error_msg)
                # Suppress UI error message for missing targets to avoid annoyance
                # self.configSaved.emit(error_msg)
                return False

            messages = []
            any_changes = False
            success_count = 0

            for display_name, script_path in target_scripts:
                try:
                    with open(script_path, 'r', encoding='utf-8') as file:
                        content = file.read()

                    replaced, new_content = self._replace_or_insert_matlab_assignment(
                        content, normalized_property, formatted_value)

                    if new_content == content:
                        info_msg = f"No changes required for {normalized_property} in {display_name}"
                        print(info_msg)
                        # messages.append(info_msg)
                        success_count += 1
                        continue

                    with open(script_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

                    any_changes = True
                    success_count += 1
                    status = "Updated" if replaced else "Inserted"
                    success_msg = f"{status} {normalized_property} = {formatted_value}{unit_suffix} in {display_name}"
                    print(success_msg)
                    messages.append(success_msg)
                except Exception as inner_error:
                    error_msg = f"Error updating {display_name} for {normalized_property}: {str(inner_error)}"
                    print(error_msg)
                    messages.append(error_msg)

            if not messages:
                if success_count > 0:
                    return True
                messages.append(f"No script updates performed for {normalized_property}.")

            summary = "; ".join(messages)
            self.configSaved.emit(summary)
            return success_count > 0

        except Exception as e:
            error_msg = f"Error saving tri-slider {matlab_property}: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    @pyqtSlot(str, result=bool)
    def removeMatlabProperty(self, matlab_property):
        """Remove a MATLAB assignment line for the given property from relevant scripts."""
        try:
            normalized_property = (matlab_property or "").strip()
            if not normalized_property:
                return False

            if not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"

            target_scripts = []
            if normalized_property == "cfg.latency":
                decomp_path = self._get_timelock_script_path()
                if decomp_path:
                    target_scripts.append(("timelock_func.m", decomp_path))
            else:
                preprocess_path = self._get_preprocess_data_script_path()
                if preprocess_path:
                    target_scripts.append(("preprocess_data.m", preprocess_path))

            if not target_scripts:
                error_msg = f"No script targets available to remove {normalized_property}."
                print(error_msg)
                # Suppress UI error message for missing targets to avoid annoyance
                # self.configSaved.emit(error_msg)
                return False

            messages = []
            removed_any = False

            for display_name, script_path in target_scripts:
                try:
                    with open(script_path, 'r', encoding='utf-8') as file:
                        content = file.read()

                    removed, new_content = self._remove_matlab_assignment(content, normalized_property)

                    if not removed:
                        info_msg = f"No assignment found for {normalized_property} in {display_name}"
                        print(info_msg)
                        messages.append(info_msg)
                        continue

                    with open(script_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

                    removed_any = True
                    success_msg = f"Removed {normalized_property} assignment from {display_name}"
                    print(success_msg)
                    messages.append(success_msg)
                except Exception as inner_error:
                    error_msg = f"Error removing {normalized_property} from {display_name}: {str(inner_error)}"
                    print(error_msg)
                    messages.append(error_msg)

            summary = "; ".join(messages) if messages else f"No updates performed for {normalized_property}."
            self.configSaved.emit(summary)
            return removed_any

        except Exception as e:
            error_msg = f"Error removing {matlab_property}: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            return False

    @pyqtSlot(list)
    def updateSelectedChannels(self, selected_channels):
        """Update the accepted_channels in preprocessing.m and preprocess_data.m with the selected channels"""
        try:
            # Format the channels as a MATLAB cell array
            if selected_channels:
                channels_str = "', '".join(selected_channels)
                matlab_channels = f"{{'{channels_str}'}}"
            else:
                matlab_channels = "{}"

            # 1. Update preprocessing.m (accepted_channels = ...)
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing", "matlab", "preprocessing.m")
            if os.path.exists(script_path):
                with open(script_path, 'r') as file:
                    content = file.read()
                
                # Replace the accepted_channels line
                channels_pattern = r'accepted_channels\s*=\s*\{[^}]*\};'
                channels_replacement = f'accepted_channels = {matlab_channels};'
                content = re.sub(channels_pattern, channels_replacement, content)
                
                with open(script_path, 'w') as file:
                    file.write(content)
            
            print(f"Updated channels in preprocessing.m: {selected_channels}")
            
        except Exception as e:
            error_msg = f"Error updating channels: {str(e)}"
            print(error_msg)
    
    @pyqtSlot(float, float, str, str, list, list, bool, float, float, bool, float, float, str)
    def runAndSaveConfiguration(self, prestim_value, poststim_value, trialfun_value, eventtype_value, selected_channels, eventvalue_list, demean_enabled, baseline_start, baseline_end, dftfilter_enabled, dftfreq_start, dftfreq_end, data_path):
        """Save configuration and then run preprocessing.m with the specified data path"""
        try:
            # First save the configuration using the existing method
            self.saveConfiguration(prestim_value, poststim_value, trialfun_value, eventtype_value, selected_channels, eventvalue_list, demean_enabled, baseline_start, baseline_end, dftfilter_enabled, dftfreq_start, dftfreq_end)
            
            # Update the accepted_channels in preprocessing.m
            self.updateSelectedChannels(selected_channels)

            # Update the data directory in preprocessing.m
            self.updateDataDirectory(data_path)
            
            # Execute the preprocessing.m script
            self.executePreprocessing()
            
        except Exception as e:
            error_msg = f"Error in run and save configuration: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
    
    @pyqtSlot()
    def executePreprocessing(self):
        """Execute preprocessing.m script in background thread"""
        try:
            print("Starting MATLAB execution of preprocessing.m...")
            
            # Check if another MATLAB process is already running
            if self._worker_thread and self._worker_thread.isRunning():
                self.configSaved.emit("MATLAB processing is already running. Please wait for it to complete.")
                return
            
            # Use the path to your MATLAB installation
            matlab_path = r"C:\Program Files\MATLAB\R2023a\bin\matlab.exe"
            
            # Path to the preprocessing directory
            preprocessing_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing")
            matlab_scripts_dir = os.path.join(preprocessing_dir, "matlab")
            
            # Emit a status message that processing has started
            self.configSaved.emit("Configuration saved! Starting MATLAB processing...\nProcessing data files in background.\nThe application will remain responsive during processing.")
            
            # Create and start worker thread
            self._worker_thread = MatlabWorkerThread(matlab_path, matlab_scripts_dir, show_console=True)
            self._worker_thread.finished.connect(self._onMatlabFinished)
            self._worker_thread.start()
            
            print("MATLAB processing started in background thread")
                
        except Exception as e:
            error_msg = f"Error starting MATLAB processing: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
    
    def _onMatlabFinished(self, result):
        """Handle completion of MATLAB processing"""
        try:
            print(f"MATLAB execution completed with return code: {result['returncode']}")
            if result['stdout']:
                print(f"STDOUT: {result['stdout']}")
            if result['stderr']:
                print(f"STDERR: {result['stderr']}")
            
            if result['returncode'] == 0:
                # Try to get the RAM contents after processing
                try:
                    # Extract number of files processed from MATLAB output
                    output_lines = result['stdout'].split('\n')
                    num_files = 0
                    for line in output_lines:
                        if 'files processed and stored in workspace variable "data"' in line:
                            # Extract the number from the line
                            import re
                            match = re.search(r'(\d+) files processed', line)
                            if match:
                                num_files = int(match.group(1))
                                break
                    
                    success_msg = f"MATLAB processing completed successfully!\n\nProcessed {num_files} files and saved as 'data_ICA.mat'.\nOriginal files remain unchanged.\n\nMATLAB Output:\n{result['stdout']}"
                except Exception as e:
                    success_msg = f"MATLAB processing completed successfully!\n\nFiles processed and saved as 'data_ICA.mat'.\nOriginal files remain unchanged.\n\nMATLAB Output:\n{result['stdout']}"
                
                self.configSaved.emit(success_msg)
                # Emit signal to refresh file explorer after successful processing
                self.fileExplorerRefresh.emit()
                # Emit signal that processing is finished
                self.processingFinished.emit()
            else:
                if result['stderr'] == 'Process timed out after 10 minutes':
                    timeout_msg = "MATLAB processing timed out (10 minutes). The script may still be running in the background.\nCheck the data folder for any completed files."
                    self.configSaved.emit(timeout_msg)
                else:
                    error_msg = f"MATLAB processing failed with return code {result['returncode']}\n\nError:\n{result['stderr']}\n\nOutput:\n{result['stdout']}"
                    self.configSaved.emit(error_msg)
                # Emit processing finished even on failure
                self.processingFinished.emit()
                    
        except Exception as e:
            error_msg = f"Error handling MATLAB completion: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
            # Ensure processing finished signal is always emitted
            self.processingFinished.emit()
    
    @pyqtSlot(str)
    def browseICAComponents(self, data_path):
        """Launch MATLAB ICA component browser using the browse_ICA.m script"""
        try:
            print("Starting MATLAB ICA component browser...")
            
            # Use the path to your MATLAB installation
            matlab_path = r"C:\Program Files\MATLAB\R2023a\bin\matlab.exe"
            
            # Get the preprocessing directory (where browse_ICA.m should be)
            preprocessing_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing")
            
            # Create the MATLAB command to run the ICA browser
            matlab_command = f"""
            cd('{data_path.replace(chr(92), '/')}');
            addpath('{preprocessing_dir.replace(chr(92), '/')}');
            if exist('data_ICA.mat', 'file')
                load('data_ICA.mat');
                if exist('data_ICApplied', 'var')
                    data_ICA = data_ICApplied;
                    set(groot, 'DefaultFigureColormap', jet);
                    for i = 1:length(data_ICA)
                        cfg = [];
                        cfg.layout = 'easycapM11.lay';
                        cfg.viewmode = 'component';
                        fprintf('Showing components for subject %d\\n', i);
                        ft_databrowser(cfg, data_ICA(i));
                        pause;
                    end
                    fprintf('ICA component browsing completed.\\n');
                else
                    fprintf('Error: data_ICApplied variable not found in data_ICA.mat\\n');
                end
            else
                fprintf('Error: data_ICA.mat file not found. Please run preprocessing first.\\n');
            end
            """
            
            print(f"Running MATLAB ICA browser command...")
            print(f"Data path: {data_path}")
            print(f"Preprocessing dir: {preprocessing_dir}")
            
            # Execute MATLAB command in a new process (non-blocking)
            import threading
            def run_matlab_browser():
                try:
                    result = subprocess.run([
                        matlab_path, 
                        "-batch", matlab_command
                    ], capture_output=True, text=True, cwd=data_path, timeout=300)
                    
                    print(f"MATLAB ICA browser completed with return code: {result.returncode}")
                    print(f"STDOUT: {result.stdout}")
                    if result.stderr:
                        print(f"STDERR: {result.stderr}")
                        
                    if result.returncode == 0:
                        success_msg = f"ICA component browser completed successfully!\n\nMATLAB Output:\n{result.stdout}"
                    else:
                        success_msg = f"ICA browser finished with some issues.\n\nOutput:\n{result.stdout}\nErrors:\n{result.stderr}"
                    
                    self.configSaved.emit(success_msg)
                    
                except subprocess.TimeoutExpired:
                    timeout_msg = "ICA browser timed out (5 minutes). The browser may still be running in MATLAB."
                    print(timeout_msg)
                    self.configSaved.emit(timeout_msg)
                except Exception as e:
                    error_msg = f"Error running ICA browser: {str(e)}"
                    print(error_msg)
                    self.configSaved.emit(error_msg)
            
            # Start the browser in a separate thread so it doesn't block the UI
            browser_thread = threading.Thread(target=run_matlab_browser)
            browser_thread.daemon = True
            browser_thread.start()
            
            # Immediate feedback to user
            self.configSaved.emit("Launching ICA component browser in MATLAB...\nThis may take a moment to start.\nEach subject will display in a separate window.\nPress any key in MATLAB to proceed between subjects.")
            
        except Exception as e:
            error_msg = f"Error launching ICA browser: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)
    
    @pyqtSlot()
    def executeMatlabScript(self):
        """Execute MATLAB script and emit the output"""
        output = self.execute_matlab_script('helloworld.m')
        if output:
            self._output = output
        else:
            self._output = "MATLAB execution failed or timed out"
        self.outputChanged.emit(self._output)
    
    def execute_matlab_script(self, script_path):
        """Execute MATLAB script and return the output"""
        try:
            print(f"Executing MATLAB script: {script_path}")
            
            # Use your specific MATLAB installation path
            matlab_path = r"C:\Program Files\MATLAB\R2023a\bin\matlab.exe"
            
            # Create the full path to the script
            script_full_path = os.path.abspath(script_path)
            
            # Run MATLAB with a more direct approach
            # Using -batch and -sd to set the startup directory
            cmd = [
                matlab_path, 
                '-batch', 
                f"cd('{os.path.dirname(script_full_path)}'); {os.path.basename(script_path)[:-2]}"  # Remove .m extension
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True, 
                text=True, 
                timeout=20,
                cwd=os.path.dirname(script_full_path),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            print(f"Return code: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            
            if result.returncode == 0:
                # Process the output
                output = result.stdout.strip()
                if output:
                    # Remove MATLAB licensing and startup info
                    lines = output.split('\n')
                    clean_lines = []
                    for line in lines:
                        line = line.strip()
                        if line and not any(skip in line.lower() for skip in [
                            'matlab', 'copyright', 'license', 'mathworks', 'version', 'release'
                        ]):
                            clean_lines.append(line)
                    
                    final_output = '\n'.join(clean_lines) if clean_lines else "Script executed successfully"
                    return f"MATLAB Output:\n{final_output}"
                else:
                    return "MATLAB Output:\nScript executed successfully (no output)"
            else:
                error_output = result.stderr.strip() if result.stderr.strip() else "Unknown error"
                return f"MATLAB Error:\n{error_output}"
                
        except subprocess.TimeoutExpired:
            return "MATLAB execution timed out (>20 seconds)"
        except FileNotFoundError:
            return f"MATLAB not found at: {matlab_path}\nPlease verify the path is correct."
        except Exception as e:
            return f"Error executing MATLAB script: {str(e)}"
    
    @pyqtSlot(str)
    def runMatlabScript(self, command):
        """Execute a MATLAB command string asynchronously and emit result via signal"""
        # Start a thread to run the script
        thread = threading.Thread(target=self._run_script_thread, args=(command,))
        thread.daemon = True
        thread.start()
    
    def _run_script_thread(self, command):
        """Run the script in a thread and emit the result"""
        try:
            result = self.runMatlabScriptInteractive(command, False)
            self.scriptFinished.emit(result)
        except Exception as e:
            self.scriptFinished.emit(f"Error executing MATLAB script: {str(e)}")
    
    @pyqtSlot(str, bool, result=str)
    def runMatlabScriptInteractive(self, command, interactive=False):
        """Execute a MATLAB command string and return the output. If interactive=True, opens MATLAB GUI."""
        try:
            print(f"Executing MATLAB command: {command}")
            print(f"Interactive mode: {interactive}")
            
            # Use your specific MATLAB installation path
            matlab_path = r"C:\Program Files\MATLAB\R2023a\bin\matlab.exe"
            
            # Get project root and matlab function paths
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            matlab_analysis_path = os.path.join(project_root, "features", "analysis", "matlab")
            matlab_preprocessing_path = os.path.join(project_root, "features", "preprocessing", "matlab")
            
            # Build MATLAB path command to add function directories (including all subdirectories)
            # Use genpath to recursively add all subdirectories
            path_cmd = f"addpath(genpath('{matlab_analysis_path}')); addpath(genpath('{matlab_preprocessing_path}')); "
            
            # Combine path setup with the user's command
            full_command = path_cmd + command
            
            if interactive:
                # Run MATLAB in interactive mode (opens GUI)
                cmd = [
                    matlab_path, 
                    '-r', 
                    full_command
                ]
                print(f"Running interactive command: {' '.join(cmd)}")
                
                # For interactive mode, we don't capture output since MATLAB GUI will show it
                result = subprocess.run(
                    cmd,
                    cwd=project_root,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    return "MATLAB opened successfully in interactive mode. Check the MATLAB console for output."
                else:
                    return f"MATLAB interactive mode failed with return code {result.returncode}"
            else:
                # Run MATLAB in batch mode
                cmd = [
                    matlab_path, 
                    '-batch', 
                    full_command
                ]
                
                print(f"Running batch command: {' '.join(cmd)}")
                print(f"Working directory: {project_root}")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True, 
                    text=True, 
                    timeout=120,  # 2 minute timeout for analysis operations
                    cwd=project_root,  # Set working directory to project root
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                print(f"Return code: {result.returncode}")
                print(f"STDOUT length: {len(result.stdout)}")
                print(f"STDERR length: {len(result.stderr)}")
                
                if result.returncode == 0:
                    # Process the output
                    output = result.stdout.strip()
                    if output:
                        # Remove MATLAB licensing and startup info
                        lines = output.split('\n')
                        clean_lines = []
                        for line in lines:
                            line = line.strip()
                            if line and not any(skip in line.lower() for skip in [
                                'matlab', 'copyright', 'license', 'mathworks', 'version', 'release'
                            ]):
                                clean_lines.append(line)
                        
                        final_output = '\n'.join(clean_lines) if clean_lines else "Command executed successfully"
                        return f"MATLAB Output:\n{final_output}"
                    else:
                        return "MATLAB Output:\nCommand executed successfully (no output)"
                else:
                    error_output = result.stderr.strip()
                    return f"MATLAB Error (return code {result.returncode}):\n{error_output}"
                    
        except subprocess.TimeoutExpired:
            return "MATLAB execution timed out (>120 seconds)"
        except FileNotFoundError:
            return f"MATLAB not found at: {matlab_path}\nPlease verify the path is correct."
        except Exception as e:
            return f"Error executing MATLAB command: {str(e)}"

    @pyqtSlot(str, result=list)
    def listMatDatasets(self, mat_path):
        """Return a list of dataset names from the 'data' struct in a .mat file."""
        try:
            if not mat_path or not os.path.exists(mat_path):
                return []
            # Try scipy first for v7 and earlier
            try:
                mat = scipy.io.loadmat(mat_path, struct_as_record=False, squeeze_me=True)
                if 'data' in mat:
                    d = mat['data']
                    names = []
                    # Assume d is an array of structs
                    for elem in d:
                        try:
                            cfg = elem['cfg']
                            ds = cfg['dataset']
                            # Handle array case
                            if hasattr(ds, '__len__') and len(ds) > 0:
                                ds = ds.flat[0] if hasattr(ds, 'flat') else ds[0]
                            if isinstance(ds, str):
                                name = os.path.splitext(os.path.basename(ds))[0]
                                names.append(name)
                            else:
                                names.append(str(ds))
                        except Exception:
                            continue
                    return list(set(names))
            except Exception:
                # Fallback to h5py for v7.3
                import h5py
                with h5py.File(mat_path, 'r') as f:
                    if 'data' in f:
                        d = f['data']
                        names = []
                        if isinstance(d, h5py.Dataset):
                            if d.dtype.names and 'cfg' in d.dtype.names:
                                data = d[:]
                                for elem in data:
                                    cfg = elem['cfg']
                                    if 'dataset' in cfg.dtype.names:
                                        ds = cfg['dataset']
                                        if isinstance(ds, bytes):
                                            ds = ds.decode('utf-8')
                                        if isinstance(ds, str):
                                            name = os.path.splitext(os.path.basename(ds))[0]
                                            names.append(name)
                                        else:
                                            names.append(str(ds))
                        elif isinstance(d, h5py.Group):
                            if 'cfg' in d:
                                cfg = d['cfg']
                                if isinstance(cfg, h5py.Dataset):
                                    if cfg.dtype == object:
                                        refs = cfg[:].flatten()
                                        for ref in refs:
                                            cfg_group = d.file[ref]
                                            if 'dataset' in cfg_group:
                                                ds = cfg_group['dataset']
                                                ds_value = ds[()]
                                                import numpy as np
                                                if isinstance(ds_value, np.ndarray) and ds_value.dtype.kind in 'ui':
                                                    byte_array = bytes(ds_value.flatten())
                                                    ds_str = byte_array.decode('utf-8').replace('\x00', '')
                                                    name = os.path.splitext(os.path.basename(ds_str))[0]
                                                    names.append(name)
                                                elif isinstance(ds_value, bytes):
                                                    ds_value = ds_value.decode('utf-8')
                                                    name = os.path.splitext(os.path.basename(ds_value))[0]
                                                    names.append(name)
                                                elif isinstance(ds_value, str):
                                                    name = os.path.splitext(os.path.basename(ds_value))[0]
                                                    names.append(name)
                                                else:
                                                    names.append(str(ds_value))
                                elif isinstance(cfg, h5py.Group):
                                    for key in sorted(cfg.keys()):
                                        if key.isdigit():
                                            elem = cfg[key]
                                            if isinstance(elem, h5py.Group) and 'dataset' in elem:
                                                ds = elem['dataset']
                                                ds_value = ds[()]
                                                import numpy as np
                                                if isinstance(ds_value, np.ndarray) and ds_value.dtype.kind in 'ui':
                                                    byte_array = bytes(ds_value.flatten())
                                                    ds_str = byte_array.decode('utf-8').replace('\x00', '')
                                                    name = os.path.splitext(os.path.basename(ds_str))[0]
                                                    names.append(name)
                                                elif isinstance(ds_value, bytes):
                                                    ds_value = ds_value.decode('utf-8')
                                                    name = os.path.splitext(os.path.basename(ds_value))[0]
                                                    names.append(name)
                                                elif isinstance(ds_value, str):
                                                    name = os.path.splitext(os.path.basename(ds_value))[0]
                                                    names.append(name)
                                                else:
                                                    names.append(str(ds_value))
                        return list(set(names))
        except Exception:
            return []
    
    @pyqtSlot(result=list)
    def getCurrentChannels(self):
        """Read the current selected channels from preprocessing.m"""
        try:
            # Use preprocessing.m as the source of truth for channels
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing", "matlab", "preprocessing.m")
            
            if not os.path.exists(script_path):
                print("preprocessing.m not found")
                return ['F4', 'Fz', 'C3', 'Pz', 'P3', 'O1', 'Oz', 'O2', 'P4', 'Cz', 'C4']
            
            with open(script_path, 'r') as file:
                content = file.read()
            
            # Look for accepted_channels (preprocessing.m)
            pattern = r'accepted_channels\s*=\s*\{([^}]*)\};'
            match = re.search(pattern, content)
            
            if match:
                channels_str = match.group(1)
                
                # More robust parsing for MATLAB cell array
                # Find all quoted strings in the cell array
                channel_matches = re.findall(r"'([^']*)'", channels_str)
                channels = [ch for ch in channel_matches if ch.strip()]
                
                return channels
            else:
                print("No accepted_channels pattern found in preprocessing.m, using defaults")
                return ['F4', 'Fz', 'C3', 'Pz', 'P3', 'O1', 'Oz', 'O2', 'P4', 'Cz', 'C4']
        except Exception as e:
            print(f"Error reading current channels: {str(e)}")
            return ['F4', 'Fz', 'C3', 'Pz', 'P3', 'O1', 'Oz', 'O2', 'P4', 'Cz', 'C4']

    @pyqtSlot(list)
    def saveChannelsToScript(self, selected_channels):
        """Save the selected channels to preprocessing.m"""
        try:
            script_path = resource_path("preprocessing/preprocessing.m")
            with open(script_path, 'r') as file:
                content = file.read()
            
            # Format channels as MATLAB cell array
            if selected_channels:
                channels_str = "'" + "', '".join(selected_channels) + "'"
            else:
                channels_str = ""
            
            new_line = f"accepted_channels = {{{channels_str}}};"
            
            # Replace the accepted_channels line
            pattern = r'accepted_channels\s*=\s*\{[^}]*\};'
            if re.search(pattern, content):
                content = re.sub(pattern, new_line, content)
            else:
                # If pattern not found, we might need to add it
                print("Warning: accepted_channels line not found in preprocessing.m")
                return False
            
            with open(script_path, 'w') as file:
                file.write(content)
            
            print(f"Updated channels in preprocessing.m: {selected_channels}")
            return True
            
        except Exception as e:
            print(f"Error saving channels to script: {str(e)}")
            return False
    
    @pyqtSlot(str)
    def addCustomTrialfunOption(self, new_option):
        """Add a new custom trialfun option to the QML file directly"""
        success = False
        try:
            qml_file_path = self._preprocessing_qml_path

            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Find the customModel property line
            pattern = r'property var customModel: (\[.*?\])'
            match = re.search(pattern, content)

            if match:
                current_array_str = match.group(1)

                # Parse the current array (simple parsing for quoted strings)
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except Exception:
                    # Fallback parsing if ast fails
                    current_array = ["ft_trialfun_general", "alternative"]

                # Add the new option if it's not already there
                if new_option not in current_array:
                    current_array.append(new_option)

                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'

                    # Replace in the content
                    new_content = re.sub(pattern, f'property var customModel: {new_array_str}', content)

                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

                    print(f"Added '{new_option}' to QML customModel")
                    success = True

        except Exception as e:
            print(f"Error adding custom trialfun option to QML: {str(e)}")
        finally:
            self._update_dropdown_state_in_qml("trialfunDropdown", "default")

        return success
    
    @pyqtSlot(str, int)
    def saveTrialfunSelection(self, selected_option, selected_index):
        """Save the selected trialfun option and index to the QML file"""
        success = False
        try:
            qml_file_path = self._preprocessing_qml_path

            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Update the currentIndex in the QML file
            index_pattern = r'currentIndex: \d+'
            new_content = re.sub(index_pattern, f'currentIndex: {selected_index}', content)

            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            print(f"Saved trialfun selection: '{selected_option}' at index {selected_index}")
            success = True

        except Exception as e:
            print(f"Error saving trialfun selection to QML: {str(e)}")
        finally:
            self._update_dropdown_state_in_qml("trialfunDropdown", "default")

        return success
    
    @pyqtSlot(str)
    def addCustomEventtypeOption(self, new_option):
        """Add a new custom eventtype option to the QML file directly"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the eventtype customModel property line
            pattern = r'property var eventtypeCustomModel: (\[.*?\])'
            match = re.search(pattern, content)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array (simple parsing for quoted strings)
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback parsing if ast fails
                    current_array = ["Stimulus", "alternative"]
                
                # Add the new option if it's not already there
                if new_option not in current_array:
                    current_array.append(new_option)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'property var eventtypeCustomModel: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Added '{new_option}' to QML eventtypeCustomModel")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error adding custom eventtype option to QML: {str(e)}")
            return False
    
    @pyqtSlot(str, int)
    def saveEventtypeSelection(self, selected_option, selected_index):
        """Save the selected eventtype option and index to the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update the eventtype currentIndex in the QML file (need to be more specific)
            # Look for the eventtypeComboBox currentIndex specifically
            eventtype_pattern = r'(id: eventtypeComboBox[\s\S]*?currentIndex: )\d+'
            match = re.search(eventtype_pattern, content)
            
            if match:
                new_content = re.sub(eventtype_pattern, f'{match.group(1)}{selected_index}', content)
                
                # Write back to file
                with open(qml_file_path, 'w', encoding='utf-8') as file:
                    file.write(new_content)
                
                print(f"Saved eventtype selection: '{selected_option}' at index {selected_index}")
                return True
            else:
                print("Could not find eventtypeComboBox currentIndex pattern")
                return False
            
        except Exception as e:
            print(f"Error saving eventtype selection to QML: {str(e)}")
            return False

    @pyqtSlot(str)
    def launchMatlabICABrowser(self, mat_file_path):
        """Launch MATLAB ft_databrowser for ICA component viewing"""
        try:
            print(f"Launching MATLAB ICA browser for: {mat_file_path}")
            
            # Get the directory containing the .mat file
            data_dir = os.path.dirname(mat_file_path)
            mat_filename = os.path.basename(mat_file_path)
            
            # Debug: Check what's actually in the file
            try:
                import scipy.io as sio
                print(f"Checking contents of: {mat_file_path}")
                mat_data = sio.loadmat(mat_file_path)
                print(f"All variables in file: {list(mat_data.keys())}")
                
                # Look for any variable that might be ICA data (excluding metadata)
                data_vars = [k for k in mat_data.keys() if not k.startswith('__')]
                print(f"Data variables found: {data_vars}")
                
                if not data_vars:
                    print("No data variables found in file")
                    self.configSaved.emit("Error: No data variables found in the .mat file")
                    return
                    
            except Exception as e:
                error_message = str(e)
                print(f"Primary loader failed: {error_message}")
                if "Please use HDF reader" in error_message or "matlab v7.3" in error_message.lower():
                    try:
                        import h5py
                        print("Falling back to h5py for v7.3 file inspection...")
                        with h5py.File(mat_file_path, 'r') as h5_file:
                            data_vars = list(h5_file.keys())
                            print(f"HDF5 datasets in file: {data_vars}")
                        if not data_vars:
                            self.configSaved.emit("Error: No datasets found in the v7.3 .mat file")
                            return
                    except ImportError:
                        msg = (
                            "Unable to read MATLAB v7.3 file because h5py is not installed. "
                            "Please install h5py to browse ICA files saved in v7.3 format."
                        )
                        print(msg)
                        self.configSaved.emit(msg)
                        return
                    except Exception as h5_error:
                        msg = f"Error reading v7.3 .mat file with h5py: {h5_error}"
                        print(msg)
                        self.configSaved.emit(msg)
                        return
                else:
                    self.configSaved.emit(f"Error reading .mat file: {error_message}")
                    return
            
            # Get paths
            preprocessing_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features", "preprocessing")
            matlab_scripts_dir = os.path.join(preprocessing_dir, "matlab")
            matlab_path = r"C:\Program Files\MATLAB\R2023a\bin\matlab.exe"
            
            # Check if MATLAB exists
            if not os.path.exists(matlab_path):
                error_msg = "MATLAB not found at expected location. Please install MATLAB and try again."
                print(error_msg)
                self.configSaved.emit(error_msg)
                return
            
            # Execute MATLAB command in a new thread (non-blocking)
            import threading
            def run_matlab_ica_browser():
                try:
                    # Use -r flag with desktop mode for GUI interaction
                    matlab_commands = f"""
addpath('{self.getCurrentFieldtripPath().replace(chr(92), '/')}');
ft_defaults;
addpath('{preprocessing_dir.replace(chr(92), '/')}');
addpath(genpath('{matlab_scripts_dir.replace(chr(92), '/')}'));
browse_ICA('{mat_file_path.replace(chr(92), '/')}');
"""
                    
                    print(f"Launching MATLAB with ICA browser...")
                    print(f"MATLAB commands:\\n{matlab_commands}")
                    
                    result = subprocess.run([
                        matlab_path, 
                        "-desktop",
                        "-r", matlab_commands
                    ], timeout=None)  # No timeout for GUI interaction
                    
                    print(f"MATLAB completed with return code: {result.returncode}")
                    
                    if result.returncode == 0:
                        success_msg = "MATLAB ICA browser session completed successfully!"
                    else:
                        success_msg = f"MATLAB session ended with return code: {result.returncode}"
                    
                    self.configSaved.emit(success_msg)
                    
                except subprocess.TimeoutExpired:
                    timeout_msg = "ICA browser session is still running in MATLAB."
                    print(timeout_msg)
                    self.configSaved.emit(timeout_msg)
                except Exception as e:
                    error_msg = f"Error running ICA browser: {str(e)}"
                    print(error_msg)
                    self.configSaved.emit(error_msg)
            
            # Start the browser in a separate thread
            browser_thread = threading.Thread(target=run_matlab_ica_browser)
            browser_thread.daemon = True  # Thread will close when main program closes
            browser_thread.start()
            
            # Immediate feedback to user
            self.configSaved.emit("Launching MATLAB desktop with ICA browser... \n\nA MATLAB window will open shortly. If you don't see it, check your taskbar or use Alt+Tab to find the MATLAB window.")
            
        except Exception as e:
            error_msg = f"Error launching MATLAB ICA browser: {str(e)}"
            print(error_msg)
            self.configSaved.emit(error_msg)

    @pyqtSlot(str)
    def addCustomTrialfunOptionToAllItems(self, new_option):
        """Add a new custom trialfun option to the trialfun dropdown's allItems array"""
        success = False
        try:
            qml_file_path = self._preprocessing_qml_path

            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Find the trialfun allItems array (look for the pattern with ft_trialfun_general)
            pattern = r'allItems: (\["ft_trialfun_general".*?\])'
            match = re.search(pattern, content, re.DOTALL)

            if match:
                current_array_str = match.group(1)

                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items

                # Add the new option if it's not already there
                if new_option not in current_array:
                    current_array.append(new_option)

                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'

                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)

                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

                    print(f"Added '{new_option}' to trialfun allItems")
                    success = True

        except Exception as e:
            print(f"Error adding custom trialfun option to allItems: {str(e)}")
        finally:
            self._update_dropdown_state_in_qml("trialfunDropdown", "default")

        return success

    @pyqtSlot(str)
    def addCustomEventtypeOptionToAllItems(self, new_option):
        """Add a new custom eventtype option to the eventtype dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the eventtype allItems array (look for the pattern with Stimulus)
            pattern = r'allItems: (\["Stimulus".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Add the new option if it's not already there
                if new_option not in current_array:
                    current_array.append(new_option)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Added '{new_option}' to eventtype allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error adding custom eventtype option to allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def addCustomEventvalueOptionToAllItems(self, new_option):
        """Add a new custom eventvalue option to the eventvalue dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the eventvalue allItems array (look for the pattern with S200)
            pattern = r'allItems: (\["S200".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Add the new option if it's not already there
                if new_option not in current_array:
                    current_array.append(new_option)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Added '{new_option}' to eventvalue allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error adding custom eventvalue option to allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def addCustomChannelOptionToAllItems(self, new_option):
        """Add a new custom channel option to the channel dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the channel allItems array (look for the pattern with Fp1)
            pattern = r'allItems: (\["Fp1".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Add the new option if it's not already there
                if new_option not in current_array:
                    current_array.append(new_option)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Added '{new_option}' to channel allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error adding custom channel option to allItems: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateBaselineSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the baseline slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: baselineSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: baselineSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: baselineSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: baselineSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated baseline slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating baseline slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updatePrestimPoststimSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the prestim/poststim slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: prestimPoststimSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: prestimPoststimSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: prestimPoststimSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: prestimPoststimSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated prestim/poststim slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating prestim/poststim slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateErpRangeSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the ERP range slider values in the analysis processing QML file."""
        try:
            qml_file_path = self._analysis_processing_qml_path
            if not os.path.exists(qml_file_path):
                print("processing_page.qml not found; cannot persist ERP slider edits.")
                return False

            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            def format_val(value):
                try:
                    numeric = float(value)
                    if abs(numeric - round(numeric)) < 1e-9:
                        return str(int(round(numeric)))
                    formatted = f"{numeric:.6f}".rstrip('0').rstrip('.')
                    return formatted if formatted else "0"
                except (ValueError, TypeError):
                    return str(value)

            from_str = format_val(from_val)
            to_str = format_val(to_val)
            first_str = format_val(first_val)
            second_str = format_val(second_val)

            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?from:\s*)(-?[\d\.]+)',
                r'\g<1>' + from_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?to:\s*)(-?[\d\.]+)',
                r'\g<1>' + to_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?firstValue:\s*)(-?[\d\.]+)',
                r'\g<1>' + first_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?secondValue:\s*)(-?[\d\.]+)',
                r'\g<1>' + second_str,
                content,
                count=1,
                flags=re.DOTALL,
            )

            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)

            print(
                "Updated ERP range slider values: from=", from_str,
                ", to=", to_str,
                ", firstValue=", first_str,
                ", secondValue=", second_str,
                sep=""
            )
            return True

        except Exception as e:
            print(f"Error updating ERP range slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateDftfreqSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the DFT frequency slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: dftfreqSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: dftfreqSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: dftfreqSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: dftfreqSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated DFT frequency slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating DFT frequency slider values: {str(e)}")
            return False

    def _get_custom_range_slider_block_positions(self, content: str):
        pattern = re.compile(r'(\n\s*RangeSliderTemplate\s*\{\s*id\s*:\s*(customRangeSlider\d+)[\s\S]*?\n\s*\})')
        positions = {}
        for match in pattern.finditer(content):
            block_id = match.group(2)
            positions[block_id] = (match.start(1), match.end(1))
        return positions

    def _build_custom_range_slider_snippet(
        self,
        range_slider_id: str,
        label: str,
        matlab_property: str,
        from_val: float,
        to_val: float,
        first_value: float,
        second_value: float,
        step_size: float,
        unit: str,
    ) -> str:
        label = label.strip() or range_slider_id
        matlab_property = matlab_property.strip()
        if matlab_property and not matlab_property.startswith("cfg."):
            matlab_property = f"cfg.{matlab_property}"

        escaped_label = self._escape_qml_string(label)
        escaped_property = self._escape_qml_string(matlab_property)
        escaped_unit = self._escape_qml_string(unit)

        lines = [
            "",
            "            RangeSliderTemplate {",
            f"                id: {range_slider_id}",
            f"                property string persistentId: \"{range_slider_id}\"",
            f"                property string customLabel: \"{escaped_label}\"",
            "                property bool persistenceConnected: false",
            f"                label: \"{escaped_label}\"",
            f"                matlabProperty: \"{escaped_property}\"",
            f"                from: {from_val}",
            f"                to: {to_val}",
            f"                firstValue: {first_value}",
            f"                secondValue: {second_value}",
            f"                stepSize: {step_size}",
            f"                unit: \"{escaped_unit}\"",
            '                sliderState: "default"',
            '                sliderId: ""',
            '                matlabPropertyDraft: ""',
            '                anchors.left: parent.left',
            "            }\n",
        ]

        return "\n".join(lines)

    def _insert_custom_range_slider_snippet(self, content: str, snippet: str):
        start_marker = "id: customDropdownContainer"
        start_index = content.find(start_marker)
        if start_index == -1:
            print("Custom dropdown container not found for range slider insertion.")
            return content, False

        # Find the opening brace of the container
        open_brace_index = content.rfind('{', 0, start_index)
        if open_brace_index == -1:
            print("Container opening brace not found for range slider insertion.")
            return content, False

        # Find where to insert - look for the closing brace of the container
        depth = 0
        insert_index = -1
        for idx in range(open_brace_index, len(content)):
            char = content[idx]
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    insert_index = idx
                    break

        if insert_index == -1:
            print("Container closing brace not found for range slider insertion.")
            return content, False

        # Insert the snippet before the closing brace
        new_content = content[:insert_index] + snippet + content[insert_index:]
        return new_content, True

    def _replace_custom_range_slider_block(self, content: str, range_slider_id: str, new_snippet: str):
        positions = self._get_custom_range_slider_block_positions(content)
        if range_slider_id not in positions:
            return content, False

        start, end = positions[range_slider_id]
        new_content = content[:start] + new_snippet + content[end:]
        return new_content, True

    def _next_custom_range_slider_index(self, existing_ids):
        max_index = -1
        for id_str in existing_ids:
            match = re.match(r'customRangeSlider(\d+)', id_str)
            if match:
                index = int(match.group(1))
                max_index = max(max_index, index)
        return max_index + 1 if max_index >= 0 else 1

    @pyqtSlot(str, str, float, float, float, float, float, str, result=str)
    def saveCustomRangeSlider(self, label, matlab_property, from_val, to_val, first_value, second_value, step_size, unit):
        """Persist a newly created custom range slider to preprocessing_page.qml and return its assigned id."""
        try:
            if not os.path.exists(self._preprocessing_qml_path):
                print("Preprocessing QML file not found when saving custom range slider.")
                return ""

            with open(self._preprocessing_qml_path, 'r', encoding='utf-8') as file:
                content = file.read()

            positions = self._get_custom_range_slider_block_positions(content)

            normalized_property = (matlab_property or "").strip()
            if normalized_property and not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"
            escaped_property = f'"{self._escape_qml_string(normalized_property)}"'

            # If a range slider with the same matlab property exists, update it instead of creating duplicate
            for existing_id, (start, end) in positions.items():
                block_text = content[start:end]
                if f'matlabProperty: {escaped_property}' in block_text:
                    snippet = self._build_custom_range_slider_snippet(
                        existing_id,
                        label,
                        normalized_property,
                        from_val,
                        to_val,
                        first_value,
                        second_value,
                        step_size,
                        unit,
                    )
                    new_content, replaced = self._replace_custom_range_slider_block(content, existing_id, snippet)
                    if replaced:
                        with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                            file.write(new_content)
                        print(f"Updated existing custom range slider '{existing_id}' with new settings.")
                    return existing_id

            next_index = self._next_custom_range_slider_index(positions.keys()) or 1
            range_slider_id = f"customRangeSlider{next_index}"

            snippet = self._build_custom_range_slider_snippet(
                range_slider_id,
                label,
                normalized_property,
                from_val,
                to_val,
                first_value,
                second_value,
                step_size,
                unit,
            )

            new_content, inserted = self._insert_custom_range_slider_snippet(content, snippet)
            if not inserted:
                return ""

            with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            print(f"Saved new custom range slider '{range_slider_id}' to QML file.")
            return range_slider_id

        except Exception as e:
            print(f"Error saving custom range slider: {str(e)}")
            return ""

    @pyqtSlot(str, str, str, float, float, float, float, float, str, result=bool)
    def updateCustomRangeSlider(self, range_slider_id, label, matlab_property, from_val, to_val, first_value, second_value, step_size, unit):
        """Update an existing custom range slider definition in preprocessing_page.qml."""
        try:
            if not os.path.exists(self._preprocessing_qml_path):
                print("Preprocessing QML file not found when updating custom range slider.")
                return False

            with open(self._preprocessing_qml_path, 'r', encoding='utf-8') as file:
                content = file.read()

            snippet = self._build_custom_range_slider_snippet(
                range_slider_id,
                label,
                matlab_property,
                from_val,
                to_val,
                first_value,
                second_value,
                step_size,
                unit,
            )

            new_content, replaced = self._replace_custom_range_slider_block(content, range_slider_id, snippet)
            if not replaced:
                print(f"Custom range slider '{range_slider_id}' not found for update; attempting to append new block.")
                new_content, inserted = self._insert_custom_range_slider_snippet(content, snippet)
                if not inserted:
                    return False

            with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            print(f"Updated custom range slider '{range_slider_id}' in QML file.")
            return True

        except Exception as e:
            print(f"Error updating custom range slider: {str(e)}")
            return False

    @pyqtSlot(str, result=bool)
    def removeCustomRangeSlider(self, range_slider_id):
        """Remove a custom range slider definition from preprocessing_page.qml."""
        try:
            if not os.path.exists(self._preprocessing_qml_path):
                print("Preprocessing QML file not found when removing custom range slider.")
                return False

            with open(self._preprocessing_qml_path, 'r', encoding='utf-8') as file:
                content = file.read()

            positions = self._get_custom_range_slider_block_positions(content)
            if range_slider_id not in positions:
                print(f"Custom range slider '{range_slider_id}' not found for removal.")
                return False

            start, end = positions[range_slider_id]
            new_content = content[:start] + content[end:]
            
            with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            print(f"Removed custom range slider '{range_slider_id}' from QML file.")
            return True

        except Exception as e:
            print(f"Error removing custom range slider: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomTrialfunOptionFromAllItems(self, itemToDelete):
        """Remove a custom trialfun option from the trialfun dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the trialfun allItems array (look for the pattern with ft_trialfun_general)
            pattern = r'allItems: (\["ft_trialfun_general".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from trialfun allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom trialfun option from allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomEventtypeOptionFromAllItems(self, itemToDelete):
        """Remove a custom eventtype option from the eventtype dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the eventtype allItems array (look for the pattern with Stimulus)
            pattern = r'allItems: (\["Stimulus".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from eventtype allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom eventtype option from allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomEventvalueOptionFromAllItems(self, itemToDelete):
        """Remove a custom eventvalue option from the eventvalue dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the eventvalue allItems array (look for the pattern with S200)
            pattern = r'allItems: (\["S200".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from eventvalue allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom eventvalue option from allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomChannelOptionFromAllItems(self, itemToDelete):
        """Remove a custom channel option from the channel dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the channel allItems array (look for the pattern with Fp1)
            pattern = r'allItems: (\["Fp1".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from channel allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom channel option from allItems: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateBaselineSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the baseline slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: baselineSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: baselineSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: baselineSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: baselineSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated baseline slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating baseline slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updatePrestimPoststimSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the prestim/poststim slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: prestimPoststimSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: prestimPoststimSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: prestimPoststimSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: prestimPoststimSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated prestim/poststim slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating prestim/poststim slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateErpRangeSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the ERP range slider values in the analysis processing QML file."""
        try:
            qml_file_path = self._analysis_processing_qml_path
            if not os.path.exists(qml_file_path):
                print("processing_page.qml not found; cannot persist ERP slider edits.")
                return False

            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            def format_val(value):
                try:
                    numeric = float(value)
                    if abs(numeric - round(numeric)) < 1e-9:
                        return str(int(round(numeric)))
                    formatted = f"{numeric:.6f}".rstrip('0').rstrip('.')
                    return formatted if formatted else "0"
                except (ValueError, TypeError):
                    return str(value)

            from_str = format_val(from_val)
            to_str = format_val(to_val)
            first_str = format_val(first_val)
            second_str = format_val(second_val)

            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?from:\s*)(-?[\d\.]+)',
                r'\g<1>' + from_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?to:\s*)(-?[\d\.]+)',
                r'\g<1>' + to_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?firstValue:\s*)(-?[\d\.]+)',
                r'\g<1>' + first_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?secondValue:\s*)(-?[\d\.]+)',
                r'\g<1>' + second_str,
                content,
                count=1,
                flags=re.DOTALL,
            )

            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)

            print(
                "Updated ERP range slider values: from=", from_str,
                ", to=", to_str,
                ", firstValue=", first_str,
                ", secondValue=", second_str,
                sep=""
            )
            return True

        except Exception as e:
            print(f"Error updating ERP range slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateDftfreqSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the DFT frequency slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: dftfreqSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: dftfreqSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: dftfreqSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: dftfreqSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated DFT frequency slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating DFT frequency slider values: {str(e)}")
            return False

    def _get_custom_range_slider_block_positions(self, content: str):
        pattern = re.compile(r'(\n\s*RangeSliderTemplate\s*\{\s*id\s*:\s*(customRangeSlider\d+)[\s\S]*?\n\s*\})')
        positions = {}
        for match in pattern.finditer(content):
            block_id = match.group(2)
            positions[block_id] = (match.start(1), match.end(1))
        return positions

    def _build_custom_range_slider_snippet(
        self,
        range_slider_id: str,
        label: str,
        matlab_property: str,
        from_val: float,
        to_val: float,
        first_value: float,
        second_value: float,
        step_size: float,
        unit: str,
    ) -> str:
        label = label.strip() or range_slider_id
        matlab_property = matlab_property.strip()
        if matlab_property and not matlab_property.startswith("cfg."):
            matlab_property = f"cfg.{matlab_property}"

        escaped_label = self._escape_qml_string(label)
        escaped_property = self._escape_qml_string(matlab_property)
        escaped_unit = self._escape_qml_string(unit)

        lines = [
            "",
            "            RangeSliderTemplate {",
            f"                id: {range_slider_id}",
            f"                property string persistentId: \"{range_slider_id}\"",
            f"                property string customLabel: \"{escaped_label}\"",
            "                property bool persistenceConnected: false",
            f"                label: \"{escaped_label}\"",
            f"                matlabProperty: \"{escaped_property}\"",
            f"                from: {from_val}",
            f"                to: {to_val}",
            f"                firstValue: {first_value}",
            f"                secondValue: {second_value}",
            f"                stepSize: {step_size}",
            f"                unit: \"{escaped_unit}\"",
            '                sliderState: "default"',
            '                sliderId: ""',
            '                matlabPropertyDraft: ""',
            '                anchors.left: parent.left',
            "            }\n",
        ]

        return "\n".join(lines)

    def _insert_custom_range_slider_snippet(self, content: str, snippet: str):
        start_marker = "id: customDropdownContainer"
        start_index = content.find(start_marker)
        if start_index == -1:
            print("Custom dropdown container not found for range slider insertion.")
            return content, False

        # Find the opening brace of the container
        open_brace_index = content.rfind('{', 0, start_index)
        if open_brace_index == -1:
            print("Container opening brace not found for range slider insertion.")
            return content, False

        # Find where to insert - look for the closing brace of the container
        depth = 0
        insert_index = -1
        for idx in range(open_brace_index, len(content)):
            char = content[idx]
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    insert_index = idx
                    break

        if insert_index == -1:
            print("Container closing brace not found for range slider insertion.")
            return content, False

        # Insert the snippet before the closing brace
        new_content = content[:insert_index] + snippet + content[insert_index:]
        return new_content, True

    def _replace_custom_range_slider_block(self, content: str, range_slider_id: str, new_snippet: str):
        positions = self._get_custom_range_slider_block_positions(content)
        if range_slider_id not in positions:
            return content, False

        start, end = positions[range_slider_id]
        new_content = content[:start] + new_snippet + content[end:]
        return new_content, True

    def _next_custom_range_slider_index(self, existing_ids):
        max_index = -1
        for id_str in existing_ids:
            match = re.match(r'customRangeSlider(\d+)', id_str)
            if match:
                index = int(match.group(1))
                max_index = max(max_index, index)
        return max_index + 1 if max_index >= 0 else 1

    @pyqtSlot(str, str, float, float, float, float, float, str, result=str)
    def saveCustomRangeSlider(self, label, matlab_property, from_val, to_val, first_value, second_value, step_size, unit):
        """Persist a newly created custom range slider to preprocessing_page.qml and return its assigned id."""
        try:
            if not os.path.exists(self._preprocessing_qml_path):
                print("Preprocessing QML file not found when saving custom range slider.")
                return ""

            with open(self._preprocessing_qml_path, 'r', encoding='utf-8') as file:
                content = file.read()

            positions = self._get_custom_range_slider_block_positions(content)

            normalized_property = (matlab_property or "").strip()
            if normalized_property and not normalized_property.startswith("cfg."):
                normalized_property = f"cfg.{normalized_property}"
            escaped_property = f'"{self._escape_qml_string(normalized_property)}"'

            # If a range slider with the same matlab property exists, update it instead of creating duplicate
            for existing_id, (start, end) in positions.items():
                block_text = content[start:end]
                if f'matlabProperty: {escaped_property}' in block_text:
                    snippet = self._build_custom_range_slider_snippet(
                        existing_id,
                        label,
                        normalized_property,
                        from_val,
                        to_val,
                        first_value,
                        second_value,
                        step_size,
                        unit,
                    )
                    new_content, replaced = self._replace_custom_range_slider_block(content, existing_id, snippet)
                    if replaced:
                        with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                            file.write(new_content)
                        print(f"Updated existing custom range slider '{existing_id}' with new settings.")
                    return existing_id

            next_index = self._next_custom_range_slider_index(positions.keys()) or 1
            range_slider_id = f"customRangeSlider{next_index}"

            snippet = self._build_custom_range_slider_snippet(
                range_slider_id,
                label,
                normalized_property,
                from_val,
                to_val,
                first_value,
                second_value,
                step_size,
                unit,
            )

            new_content, inserted = self._insert_custom_range_slider_snippet(content, snippet)
            if not inserted:
                return ""

            with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            print(f"Saved new custom range slider '{range_slider_id}' to QML file.")
            return range_slider_id

        except Exception as e:
            print(f"Error saving custom range slider: {str(e)}")
            return ""

    @pyqtSlot(str, str, str, float, float, float, float, float, str, result=bool)
    def updateCustomRangeSlider(self, range_slider_id, label, matlab_property, from_val, to_val, first_value, second_value, step_size, unit):
        """Update an existing custom range slider definition in preprocessing_page.qml."""
        try:
            if not os.path.exists(self._preprocessing_qml_path):
                print("Preprocessing QML file not found when updating custom range slider.")
                return False

            with open(self._preprocessing_qml_path, 'r', encoding='utf-8') as file:
                content = file.read()

            snippet = self._build_custom_range_slider_snippet(
                range_slider_id,
                label,
                matlab_property,
                from_val,
                to_val,
                first_value,
                second_value,
                step_size,
                unit,
            )

            new_content, replaced = self._replace_custom_range_slider_block(content, range_slider_id, snippet)
            if not replaced:
                print(f"Custom range slider '{range_slider_id}' not found for update; attempting to append new block.")
                new_content, inserted = self._insert_custom_range_slider_snippet(content, snippet)
                if not inserted:
                    return False

            with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            print(f"Updated custom range slider '{range_slider_id}' in QML file.")
            return True

        except Exception as e:
            print(f"Error updating custom range slider: {str(e)}")
            return False

    @pyqtSlot(str, result=bool)
    def removeCustomRangeSlider(self, range_slider_id):
        """Remove a custom range slider definition from preprocessing_page.qml."""
        try:
            if not os.path.exists(self._preprocessing_qml_path):
                print("Preprocessing QML file not found when removing custom range slider.")
                return False

            with open(self._preprocessing_qml_path, 'r', encoding='utf-8') as file:
                content = file.read()

            positions = self._get_custom_range_slider_block_positions(content)
            if range_slider_id not in positions:
                print(f"Custom range slider '{range_slider_id}' not found for removal.")
                return False

            start, end = positions[range_slider_id]
            new_content = content[:start] + content[end:]
            
            with open(self._preprocessing_qml_path, 'w', encoding='utf-8') as file:
                file.write(new_content)

            print(f"Removed custom range slider '{range_slider_id}' from QML file.")
            return True

        except Exception as e:
            print(f"Error removing custom range slider: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomTrialfunOptionFromAllItems(self, itemToDelete):
        """Remove a custom trialfun option from the trialfun dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the trialfun allItems array (look for the pattern with ft_trialfun_general)
            pattern = r'allItems: (\["ft_trialfun_general".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from trialfun allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom trialfun option from allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomEventtypeOptionFromAllItems(self, itemToDelete):
        """Remove a custom eventtype option from the eventtype dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the eventtype allItems array (look for the pattern with Stimulus)
            pattern = r'allItems: (\["Stimulus".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from eventtype allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom eventtype option from allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomEventvalueOptionFromAllItems(self, itemToDelete):
        """Remove a custom eventvalue option from the eventvalue dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the eventvalue allItems array (look for the pattern with S200)
            pattern = r'allItems: (\["S200".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from eventvalue allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom eventvalue option from allItems: {str(e)}")
            return False

    @pyqtSlot(str)
    def deleteCustomChannelOptionFromAllItems(self, itemToDelete):
        """Remove a custom channel option from the channel dropdown's allItems array"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find the channel allItems array (look for the pattern with Fp1)
            pattern = r'allItems: (\["Fp1".*?\])'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                current_array_str = match.group(1)
                
                # Parse the current array
                import ast
                try:
                    current_array = ast.literal_eval(current_array_str)
                except:
                    # Fallback: extract items between quotes
                    items = re.findall(r'"([^"]*)"', current_array_str)
                    current_array = items
                
                # Remove the item if it exists
                if itemToDelete in current_array:
                    current_array.remove(itemToDelete)
                    
                    # Create the new array string
                    new_array_str = '["' + '", "'.join(current_array) + '"]'
                    
                    # Replace in the content
                    new_content = re.sub(pattern, f'allItems: {new_array_str}', content)
                    
                    # Write back to file
                    with open(qml_file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    
                    print(f"Removed '{itemToDelete}' from channel allItems")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error removing custom channel option from allItems: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateBaselineSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the baseline slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: baselineSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: baselineSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: baselineSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: baselineSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated baseline slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating baseline slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updatePrestimPoststimSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the prestim/poststim slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: prestimPoststimSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: prestimPoststimSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: prestimPoststimSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: prestimPoststimSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated prestim/poststim slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating prestim/poststim slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateErpRangeSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the ERP range slider values in the analysis processing QML file."""
        try:
            qml_file_path = self._analysis_processing_qml_path
            if not os.path.exists(qml_file_path):
                print("processing_page.qml not found; cannot persist ERP slider edits.")
                return False

            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            def format_val(value):
                try:
                    numeric = float(value)
                    if abs(numeric - round(numeric)) < 1e-9:
                        return str(int(round(numeric)))
                    formatted = f"{numeric:.6f}".rstrip('0').rstrip('.')
                    return formatted if formatted else "0"
                except (ValueError, TypeError):
                    return str(value)

            from_str = format_val(from_val)
            to_str = format_val(to_val)
            first_str = format_val(first_val)
            second_str = format_val(second_val)

            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?from:\s*)(-?[\d\.]+)',
                r'\g<1>' + from_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?to:\s*)(-?[\d\.]+)',
                r'\g<1>' + to_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?firstValue:\s*)(-?[\d\.]+)',
                r'\g<1>' + first_str,
                content,
                count=1,
                flags=re.DOTALL,
            )
            content = re.sub(
                r'(id:\s*erpRangeSlider[\s\S]*?secondValue:\s*)(-?[\d\.]+)',
                r'\g<1>' + second_str,
                content,
                count=1,
                flags=re.DOTALL,
            )

            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)

            print(
                "Updated ERP range slider values: from=", from_str,
                ", to=", to_str,
                ", firstValue=", first_str,
                ", secondValue=", second_str,
                sep=""
            )
            return True

        except Exception as e:
            print(f"Error updating ERP range slider values: {str(e)}")
            return False

    @pyqtSlot(float, float, float, float)
    def updateDftfreqSliderValues(self, from_val, to_val, first_val, second_val):
        """Update the DFT frequency slider values in the QML file"""
        try:
            qml_file_path = self._preprocessing_qml_path
            
            # Read the current QML file
            with open(qml_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Update from value
            content = re.sub(r'(id: dftfreqSlider.*?from:) [\d\.\-]+', f'\\1 {from_val}', content, flags=re.DOTALL)
            
            # Update to value
            content = re.sub(r'(id: dftfreqSlider.*?to:) [\d\.\-]+', f'\\1 {to_val}', content, flags=re.DOTALL)
            
            # Update firstValue
            content = re.sub(r'(id: dftfreqSlider.*?firstValue:) [\d\.\-]+', f'\\1 {first_val}', content, flags=re.DOTALL)
            
            # Update secondValue
            content = re.sub(r'(id: dftfreqSlider.*?secondValue:) [\d\.\-]+', f'\\1 {second_val}', content, flags=re.DOTALL)
            
            # Write back to file
            with open(qml_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Updated DFT frequency slider values: from={from_val}, to={to_val}, firstValue={first_val}, secondValue={second_val}")
            return True
            
        except Exception as e:
            print(f"Error updating DFT frequency slider values: {str(e)}")
            return False

    def _get_custom_range_slider_block_positions(self, content: str):
        pattern = re.compile(r'(\n\s*RangeSliderTemplate\s*\{\s*id\s*:\s*(customRangeSlider\d+)[\s\S]*?\n\s*\})')
        positions = {}
        for match in pattern.finditer(content):
            block_id = match.group(2)
            positions[block_id] = (match.start(1), match.end(1))
        return positions

    def _build_custom_range_slider_snippet(
        self,
        range_slider_id: str,
        label: str,
        matlab_property: str,
        from_val: float,
        to_val: float,
        first_value: float,
        second_value: float,
        step_size: float,
        unit: str,
    ) -> str:
        label = label.strip() or range_slider_id
        matlab_property = matlab_property.strip()
        if matlab_property and not matlab_property.startswith("cfg."):
            matlab_property = f"cfg.{matlab_property}"

        escaped_label = self._escape_qml_string(label)
        escaped_property = self._escape_qml_string(matlab_property)
        escaped_unit = self._escape_qml_string(unit)

        lines = [
            "",
            "            RangeSliderTemplate {",
            f"                id: {range_slider_id}",
            f"                property string persistentId: \"{range_slider_id}\"",
            f"                property string customLabel: \"{escaped_label}\"",
            "                property bool persistenceConnected: false",
            f"                label: \"{escaped_label}\"",
            f"                matlabProperty: \"{escaped_property}\"",
            f"                from: {from_val}",
            f"                to: {to_val}",
            f"                firstValue: {first_value}",
            f"                secondValue: {second_value}",
            f"                stepSize: {step_size}",
            f"                unit: \"{escaped_unit}\"",
            '                sliderState: "default"',
            '                sliderId: ""',
            '                matlabPropertyDraft: ""',
            '                anchors.left: parent.left',
            "            }\n",
        ]

        return "\n".join(lines)

    def _insert_custom_range_slider_snippet(self, content: str, snippet: str):
        start_marker = "id: customDropdownContainer"
        start_index = content.find(start_marker)
        if start_index == -1:
            print("Custom dropdown container not found for range slider insertion.")
            return content, False

        # Find the opening brace of the container
        open_brace_index = content.rfind('{', 0, start_index)
        if open_brace_index == -1:
            print("Container opening brace not found for range slider insertion.")
            return content, False

        # Find where to insert - look for the closing brace of the container
        depth = 0
        insert_index = -1
        for idx in range(open_brace_index, len(content)):
            char = content[idx]
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    insert_index = idx
                    break

        if insert_index == -1:
            print("Container closing brace not found for range slider insertion.")
            return content, False

        # Insert the snippet before the closing brace
        new_content = content[:insert_index] + snippet + content[insert_index:]
        return new_content, True

    def _replace_custom_range_slider_block(self, content: str, range_slider_id: str, new_snippet: str):
        positions = self._get_custom_range_slider_block_positions(content)
        if range_slider_id not in positions:
            return content, False

        start, end = positions[range_slider_id]
        new_content = content[:start] + new_snippet + content[end:]
        return new_content, True

    def _next_custom_range_slider_index(self, existing_ids):
        max_index = -1
        for id_str in existing_ids:
            match = re.match(r'customRangeSlider(\d+)', id_str)
            if match:
                index = int(match.group(1))
                max_index = max(max_index, index)
        return max_index + 1 if max_index >= 0 else 1


    @pyqtSlot(str, result=str)
    def getModuleParameters(self, module_name):
        """Get dynamic parameters for a module as JSON string."""
        try:
            parser = MatlabParameterParser()
            mapper = ModuleParameterMapper()
            option_store = DropdownOptionStore()

            matlab_files = mapper.get_matlab_file(module_name)
            if not matlab_files:
                print(f"No MATLAB file found for module: {module_name}")
                return "{}"

            # Convert relative path to absolute path
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            parameters = {}
            
            # Handle both single file string and list of files
            if isinstance(matlab_files, str):
                matlab_files = [matlab_files]
                
            for matlab_file in matlab_files:
                matlab_file_path = os.path.join(project_root, matlab_file)
                file_params = parser.parse_file(matlab_file_path)
                parameters.update(file_params)

            # Update range limits in option store based on current values
            changes_made = False
            for param_name, param_info in parameters.items():
                if param_info.get('type') == 'range':
                    current_from = param_info.get('from', 0)
                    current_to = param_info.get('to', 1)
                    
                    # Logic: Expand range to be at least [value-1, value+1]
                    # If from == to (e.g. [4 4]), we need to ensure min < max for the slider to work
                    desired_min = current_from - 1.0
                    desired_max = current_to + 1.0
                    
                    if current_from == current_to:
                        desired_min = current_from - 1.0
                        desired_max = current_from + 1.0

                    if option_store.update_range_limits(param_name, desired_min, desired_max, module_name):
                        changes_made = True
            
            if changes_made:
                option_store.save()

            ui_components = {}
            for param_name, param_info in parameters.items():
                option_entry = option_store.get_option_entry(param_name, module_name)
                ui_components[param_name] = create_ui_component(param_name, param_info, option_entry)



            return json.dumps(ui_components)
        except Exception as e:
            print(f"Error getting module parameters: {e}")
            return "{}"

    @pyqtSlot(list)
    def saveLabels(self, labels_list):
        """Save the list of labels to labels.py in the core folder"""
        try:
            labels_file_path = os.path.join(os.path.dirname(__file__), '..', 'features', 'classification', 'python', 'core', 'labels.py')
            with open(labels_file_path, 'w', encoding='utf-8') as f:
                f.write('labels = [\n')
                for label in labels_list:
                    f.write(f'    "{label}",\n')
                f.write(']\n')
            print(f"Labels saved to {labels_file_path}")
        except Exception as e:
            print(f"Error saving labels: {e}")

    @pyqtSlot(result=list)
    def loadLabels(self):
        """Load the list of labels from labels.py in the core folder"""
        try:
            labels_file_path = os.path.join(os.path.dirname(__file__), '..', 'features', 'classification', 'python', 'core', 'labels.py')
            if os.path.exists(labels_file_path):
                with open(labels_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Simple parsing: assume it's labels = ["a", "b", ...]
                import ast
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.List):
                        return [elt.s for elt in node.elts if isinstance(elt, ast.Str)]
            return []
        except Exception as e:
            print(f"Error loading labels: {e}")
            return []

    @pyqtSlot(str, str, result=str)
    def loadAndTransformData(self, analysis_type, target_model):
        """
        Load and transform data from the current data directory for classification.
        Uses PreprocessBridge with the dynamically updated data path.
        Returns JSON string with shape info or error message.
        """
        try:
            if not hasattr(self, '_preprocess_bridge'):
                return json.dumps({"error": "PreprocessBridge not initialized"})
            
            # Call the bridge's load_and_transform (uses current data_path set via set_data_path)
            transformed_data = self._preprocess_bridge.load_and_transform(analysis_type, target_model)
            
            return json.dumps({
                "success": True,
                "shape": list(transformed_data.shape),
                "dtype": str(transformed_data.dtype)
            })
        except FileNotFoundError as e:
            return json.dumps({"error": f"File not found: {str(e)}"})
        except KeyError as e:
            return json.dumps({"error": f"Invalid analysis type or missing data: {str(e)}"})
        except Exception as e:
            return json.dumps({"error": f"Error loading data: {str(e)}"})
