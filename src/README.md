# Source Code (`src`)

This directory contains the core application logic and utility scripts that power the EEG Analysis application. It handles the initialization of the PyQt6 application, the integration with MATLAB for data processing, and the dynamic generation of UI components based on MATLAB configurations.

## Overview

The `src` folder serves as the backbone of the application, bridging the frontend (QML) with the backend processing logic (Python and MATLAB). It includes the main entry point, the MATLAB execution engine, and parsers for dynamic parameter handling.

## Key Components

### 1. Application Entry Point

- **File:** `main.py`
- **Description:** This is the main executable script for the application. It performs the following tasks:
  - Initializes the `QApplication` and `QQmlApplicationEngine`.
  - Sets up the environment (e.g., Qt Quick Controls style).
  - Registers custom Python classes (`MatlabExecutor`, `FileBrowser`) as QML types.
  - Loads the main QML interface (`ui/main.qml`).

### 2. MATLAB Integration

- **File:** `matlab_executor.py`
- **Description:** Handles the execution of MATLAB scripts from within the Python application.
  - **`MatlabExecutor` Class:** Provides methods to run MATLAB commands and scripts.
  - **`MatlabWorkerThread` Class:** Runs MATLAB processes in a background thread to prevent freezing the UI during long processing tasks.
  - Manages communication and error reporting between MATLAB and the Python application.

### 3. Parameter Parsing

- **File:** `matlab_parameter_parser.py`
- **Description:** A utility for parsing MATLAB script files to extract configuration parameters.
  - Scans MATLAB code for `cfg` variable assignments (e.g., `cfg.frequency = [1 30]`).
  - Identifies parameter types (ranges, strings, numbers, arrays) using regular expressions.
  - Converts these parameters into a structured Python dictionary format.

### 4. Dynamic UI Loading

- **File:** `dynamic_parameter_loader.py`
- **Description:** Facilitates the dynamic generation of UI controls based on the parsed MATLAB parameters.
  - Uses `MatlabParameterParser` to read configuration needs from backend scripts.
  - Maps these parameters to appropriate UI components (e.g., sliders for ranges, dropdowns for options).
  - Outputs JSON configurations that the QML frontend uses to build the interface on the fly.

## Usage

To start the application, run the `main.py` script from the project root:

```bash
python src/main.py
```

## Dependencies

- **Python 3.x**
- **PyQt6:** For the GUI framework.
- **MATLAB Engine (Optional/Alternative):** The current implementation uses `subprocess` to call the MATLAB executable, but the structure allows for potential integration with the official MATLAB Engine API.
