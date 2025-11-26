# Preprocessing Module

This module provides a comprehensive suite of tools for preprocessing EEG data, specifically designed to work with `.set` files. It leverages the power of the **FieldTrip** MATLAB toolbox for signal processing while offering a user-friendly **QML/Python** interface for configuration and file management.

## Overview

The preprocessing pipeline is designed to clean raw EEG data by applying various filters, performing Independent Component Analysis (ICA) for artifact removal, and preparing the data for subsequent analysis steps like ERP or spectral analysis.

## Key Features

- **Data Loading:** Seamlessly browse and load EEG datasets (`.set` files) from local directories.
- **Signal Processing:**
  - **Filtering:** Apply DFT filters (e.g., line noise removal at 50/60Hz).
  - **Baseline Correction:** Perform de-meaning and baseline correction with customizable windows.
  - **Trial Definition:** Define trials based on stimulus event codes (e.g., Target, Standard, Novelty).
- **Independent Component Analysis (ICA):**
  - Run ICA using the `fastica` method to decompose signals into independent components.
  - Identify and reject artifactual components (e.g., eye blinks, muscle noise).
- **Data Decomposition:** Split processed data into specific conditions (Target, Standard, Novelty) for focused analysis.

## Architecture

The module is built with a hybrid architecture:

### Frontend (QML & Python)

- **User Interface:** Built with QML (`qml/preprocessing_page.qml`), providing an interactive dashboard to set parameters like channel selection, filter frequencies, and baseline windows.
- **File Management:** Python scripts (`python/file_browser.py`) handle file system interactions, allowing users to navigate directories and select datasets.

### Backend (MATLAB)

The core processing logic is implemented in MATLAB, utilizing the FieldTrip toolbox:

- `preprocessing.m`: The main orchestration script for batch processing files.
- `preprocess_data.m`: Defines the specific preprocessing steps (filtering, trial definition).
- `applyICA.m`: Executes the ICA algorithm on the preprocessed data.
- `reject_components.m`: Removes selected artifact components from the data.
- `decompose.m`: Separates the data into distinct experimental conditions.

## File Structure

```
features/preprocessing/
├── matlab/                     # Core processing scripts
│   ├── applyICA.m              # Runs ICA
│   ├── browse_ICA.m            # ICA component browser
│   ├── decompose.m             # Decomposes data into conditions
│   ├── ft_databrowser_modified.m # Modified FieldTrip databrowser
│   ├── preprocess_data.m       # Main preprocessing function
│   ├── preprocessing.m         # Batch processing script
│   └── reject_components.m     # Artifact rejection logic
├── python/                     # Python backend for UI
│   ├── file_browser.py         # File navigation logic
│   └── quick_sync.py           # Synchronization utility
└── qml/                        # User Interface
    ├── DropdownTemplate.qml    # Reusable dropdown component
    ├── FileBrowserUI.qml       # File browser interface
    ├── preprocessing_page.qml  # Main UI page
    ├── RangeSliderTemplate.qml # Reusable range slider
    └── StepRangeSliderTemplate.qml # Reusable step slider
```

## Prerequisites

- **MATLAB:** Required for running the backend processing scripts.
- **FieldTrip Toolbox:** Must be installed and added to the MATLAB path.
- **Python & PyQt6:** Required for the application frontend.

## Usage

1.  **Select Data Directory:** Use the file browser in the UI to locate your `.set` files.
2.  **Configure Parameters:**
    - Select channels to include.
    - Set baseline correction window.
    - Configure DFT filter frequencies.
3.  **Run Preprocessing:** Initiate the pipeline to process the selected files.
4.  **ICA & Artifact Rejection:** (Optional) Run ICA and select components to reject to clean the data.
