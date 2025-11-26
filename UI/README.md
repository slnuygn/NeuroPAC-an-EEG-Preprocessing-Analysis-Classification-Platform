# User Interface (`ui`)

This directory contains the main QML files that define the graphical user interface (GUI) of the NeuroPAC application. It handles the application's main window, navigation menus, and the integration of various feature modules.

## Overview

The UI is built using **Qt Quick (QML)**, providing a modern, fluid, and responsive interface. It serves as the container for the application's features (like Preprocessing) and manages global states, such as MATLAB output and file paths.

## Key Components

### 1. Main Application Window

- **File:** `main.qml`
- **Description:** The entry point for the UI. It defines the `ApplicationWindow` and orchestrates the overall layout.
  - **Title:** "NeuroPAC: Preprocessing and Analysis Console"
  - **Integrations:**
    - Imports custom Python types: `MatlabExecutor` and `FileBrowser`.
    - Connects to backend signals to display MATLAB output and save status messages.
    - Manages global properties like `fieldtripPath` and `matlabOutput`.
  - **Logic:** Contains JavaScript functions for handling channel selection logic (toggling, checking selection state).

### 2. Top Navigation Menu

- **File:** `TopMenu.qml`
- **Description:** A reusable component that implements the application's top menu bar.
  - **Structure:**
    - **File Menu:** Options for file operations and MATLAB configuration (e.g., setting FieldTrip path).
    - **Edit Menu:** Tools for editing and customizing the interface (e.g., "Edit Mode", adding new UI elements like dropdowns or sliders).
  - **Signals:** Emits signals (e.g., `fieldtripDialogRequested`, `editModeToggled`) to communicate user actions to the main window or other components.

## Structure

```
ui/
├── main.qml        # Main application window and logic
├── TopMenu.qml     # Top navigation bar component
└── README.md       # This documentation file
```

## Integration with Features

The `ui` folder acts as the shell. Specific feature UIs (like the Preprocessing page) are imported from their respective directories (e.g., `features/preprocessing/ui/`) and instantiated within `main.qml` or loaded dynamically.

## Usage

These files are loaded by the Python backend (`src/main.py`) using the `QQmlApplicationEngine`. They rely on the registered Python types to function correctly.
