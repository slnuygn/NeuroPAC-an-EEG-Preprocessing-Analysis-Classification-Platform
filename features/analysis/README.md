# Analysis Feature

This directory contains the implementation of the Analysis feature for the Capstone project. It provides tools for performing various neurophysiological analyses on preprocessed data, including ERP, Spectral, Time-Frequency, and Connectivity analysis.

## Directory Structure

```
features/analysis/
├── matlab/                 # MATLAB scripts for analysis logic
│   ├── connectivity/       # Connectivity analysis scripts
│   │   ├── channelwise/    # Channel-wise connectivity
│   │   └── intertrial/     # Inter-trial coherence analysis
│   ├── ERP/                # Event-Related Potential analysis
│   ├── spectral/           # Spectral power analysis
│   └── timefrequency/      # Time-frequency analysis
├── qml/                    # QML files for the User Interface
│   ├── processing_page.qml # Main analysis page UI
│   ├── ModuleTemplate.qml  # Reusable module component
│   └── DynamicParameterLoader.qml # Dynamic parameter loading component
└── README.md               # This file
```

## Key Components

### MATLAB Analysis Modules

The core analysis logic is implemented in MATLAB using the FieldTrip toolbox.

- **ERP Analysis** (`matlab/ERP/`)

  - `timelock_func.m`: Performs timelock analysis on decomposed ICA data (`data_ICApplied_clean_decomposed.mat`).
  - `extract_erp_data.m`: Helper function to extract average ERP data for specific conditions (e.g., 'target', 'standard', 'novelty').

- **Spectral Analysis** (`matlab/spectral/`)

  - `spectralanalysis.m`: Computes the power spectrum of task data using Fourier transform (`mtmfft`).
  - `visualize_spectra.m`: Visualizes the power spectrum for different conditions.

- **Time-Frequency Analysis** (`matlab/timefrequency/`)

  - `timefreqanalysis.m`: Performs time-frequency analysis using wavelets (`wavelet` method).
  - `visualize_timefreq_condition.m`: Visualizes Time-Frequency Representations (TFR) for different conditions.

- **Connectivity Analysis** (`matlab/connectivity/`)
  - `intertrialcoherenceanalysis.m`: Computes Inter-Trial Phase Coherence (ITPC) and Inter-Trial Linear Coherence (ITLC).
  - `channelwise.m`: Placeholder for channel-wise coherence analysis.

### User Interface (QML)

The UI is built with Qt Quick/QML and integrates with the MATLAB backend.

- **`processing_page.qml`**: The main entry point for the analysis feature. It features a file explorer for selecting data and hosts the various analysis modules.
- **`ModuleTemplate.qml`**: A generic container for analysis modules. It supports expanding/collapsing and dynamic parameter loading.
- **`DynamicParameterLoader.qml`**: Dynamically renders UI controls (sliders, dropdowns) for analysis parameters based on configuration.

## Usage

1.  **Data Selection**: Use the file explorer in the `Processing Page` to select the preprocessed data file (typically `data_ICApplied_clean_decomposed.mat`).
2.  **Module Configuration**: Expand the desired analysis module (e.g., ERP, Spectral).
3.  **Parameter Tuning**: Adjust parameters using the dynamic controls (if available).
4.  **Execution**: Run the analysis. The system uses the `MatlabExecutor` to run the corresponding MATLAB scripts.
