import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import "."
import "../../preprocessing/qml"
import "../../../ui"

Item {
    id: processingPageRoot
    anchors.fill: parent
    anchors.margins: 10
    
    property bool editModeEnabled: false
    property string currentFolder: ""
    property var folderContents: []
    
    // Global properties for label persistence
    property var globalLabelListModel
    property bool globalIsLoadingLabels
    signal loadingStateChanged(bool loading)
    
    // Signals to communicate with main.qml
    signal openFolderDialog()
    signal refreshFileExplorer()
    
    // Function to set edit mode for all modules
    function setEditMode(enabled) {
        processingPageRoot.editModeEnabled = enabled
        
        // Update all module templates
        if (erpAnalysisModule) erpAnalysisModule.editModeEnabled = enabled
        if (timeFreqModule) timeFreqModule.editModeEnabled = enabled
        if (interTrialModule) interTrialModule.editModeEnabled = enabled
        if (channelWiseModule) channelWiseModule.editModeEnabled = enabled
        if (spectralModule) spectralModule.editModeEnabled = enabled
        
        console.log("Processing page edit mode set to:", enabled)
    }
    
    // File Explorer Rectangle - Left side
    FileBrowserUI {
        id: fileExplorerRect
        anchors.left: parent.left
        anchors.top: parent.top
        width: parent.width * 0.2
        height: parent.height
        
        labelListModel: globalLabelListModel
        isLoadingLabels: globalIsLoadingLabels
    }

    // Right side - Modules Area with Scrolling
    Rectangle {
        anchors.left: fileExplorerRect.right
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 10
        anchors.rightMargin: 5
        color: "transparent"
        
        ScrollView {
            id: scrollArea
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth

            Column {
                width: scrollArea.availableWidth
                spacing: 1

                ModuleTemplate {
                    id: erpAnalysisModule
                    displayText: "ERP Analysis"
                    moduleName: "ERP Analysis"
                    outputFileName: "erp_output.mat"
                    visualizerFunction: "erp_visualizer"
                    currentFolder: processingPageRoot.currentFolder
                    folderContents: processingPageRoot.folderContents

                    onVisualizeClicked: {
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var outputFilePath = normalizedFolder + "/erp_output.mat"
                        var escapedPath = outputFilePath.replace(/'/g, "\\'")
                        // Add MATLAB paths, load the MAT file, then call erp_visualizer with available data.
                        // Use a single set of addpath calls to avoid duplicate/escaped quote issues.
                        var scriptParts = [
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/analysis/matlab'));",
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/preprocessing/matlab'));",
                            "load('" + escapedPath + "');",
                            "if exist('erp_records','var'), erp_visualizer(erp_records);",
                            "elseif exist('ERP_data','var'), erp_visualizer(ERP_data);",
                            "else, error('erp_output.mat missing erp_records/ERP_data'); end"
                        ];
                        var script = scriptParts.join(' ');
                        matlabExecutor.runMatlabScriptInteractive(script, true)
                    }

                    onButtonClicked: {
                        // Check for the decomposed file instead of clean file
                        var targetFileName = "data_ICApplied_clean_decomposed.mat"
                        
                        if (!currentFolder) {
                            erpAnalysisModule.errorMessage = "No folder selected"
                            return
                        }
                        
                        var foundFile = false
                        for (var i = 0; i < folderContents.length; i++) {
                            var rawEntry = folderContents[i]
                            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
                            if (sanitizedEntry.toLowerCase() === targetFileName.toLowerCase()) {
                                foundFile = true
                                break
                            }
                        }
                        
                        if (!foundFile) {
                            erpAnalysisModule.errorMessage = "data_ICApplied_clean_decomposed.mat not found in the selected folder"
                            return
                        }
                        
                        erpAnalysisModule.errorMessage = ""
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var escapedFolder = normalizedFolder.replace(/'/g, "\\'")
                        matlabExecutor.runMatlabScriptInteractive("timelock_func('" + escapedFolder + "')", true)
                    }
                }
                
                ModuleTemplate {
                    id: timeFreqModule
                    displayText: "Time-Frequency Analysis"
                    moduleName: "Time-Frequency Analysis"
                    outputFileName: "timefreq_output.mat"
                    visualizerFunction: "timefreq_visualizer"
                    currentFolder: processingPageRoot.currentFolder
                    folderContents: processingPageRoot.folderContents

                    onVisualizeClicked: {
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var outputFilePath = normalizedFolder + "/timefreq_output.mat"
                        var escapedPath = outputFilePath.replace(/'/g, "\\'")
                        var scriptParts = [
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/analysis/matlab'));",
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/preprocessing/matlab'));",
                            "data = load('" + escapedPath + "');",
                            "if isfield(data,'timefreq_output'), timefreq_visualizer(data.timefreq_output);",
                            "elseif isfield(data,'timefreq_data'), timefreq_visualizer(data.timefreq_data);",
                            "else, error('timefreq_output.mat missing timefreq_output or timefreq_data'); end"
                        ]
                        var script = scriptParts.join(' ')
                        matlabExecutor.runMatlabScriptInteractive(script, true)
                    }

                    onButtonClicked: {
                        // Require decomposed cleaned data before running time-frequency analysis
                        var targetFileName = "data_ICApplied_clean_decomposed.mat"

                        if (!currentFolder) {
                            timeFreqModule.errorMessage = "No folder selected"
                            return
                        }

                        var foundFile = false
                        for (var i = 0; i < folderContents.length; i++) {
                            var rawEntry = folderContents[i]
                            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
                            if (sanitizedEntry.toLowerCase() === targetFileName.toLowerCase()) {
                                foundFile = true
                                break
                            }
                        }

                        if (!foundFile) {
                            timeFreqModule.errorMessage = "data_ICApplied_clean_decomposed.mat not found in the selected folder"
                            return
                        }

                        timeFreqModule.errorMessage = ""
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var escapedFolder = normalizedFolder.replace(/'/g, "\\'")
                        matlabExecutor.runMatlabScriptInteractive("timefreqanalysis('" + escapedFolder + "')", true)
                    }
                }

                ModuleTemplate {
                    id: interTrialModule
                    displayText: "Inter-Trial Coherence Analysis"
                    moduleName: "Inter-Trial Coherence Analysis"
                    outputFileName: "intertrial_coherence_output.mat"
                    visualizerFunction: "intertrial_visualizer"
                    currentFolder: processingPageRoot.currentFolder
                    folderContents: processingPageRoot.folderContents

                    onVisualizeClicked: {
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var outputFilePath = normalizedFolder + "/intertrial_coherence_output.mat"
                        var escapedPath = outputFilePath.replace(/'/g, "\\'")
                        var scriptParts = [
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/analysis/matlab'));",
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/preprocessing/matlab'));",
                            "data = load('" + escapedPath + "');",
                            "if isfield(data,'intertrial_coherence_output'), intertrial_visualizer(data.intertrial_coherence_output);",
                            "elseif isfield(data,'itc_data'), intertrial_visualizer(data.itc_data);",
                            "else, error('intertrial_coherence_output.mat missing intertrial_coherence_output or itc_data'); end"
                        ]
                        var script = scriptParts.join(' ')
                        matlabExecutor.runMatlabScriptInteractive(script, true)
                    }

                    onButtonClicked: {
                        // Require decomposed cleaned data before running inter-trial coherence analysis
                        var targetFileName = "data_ICApplied_clean_decomposed.mat"

                        if (!currentFolder) {
                            interTrialModule.errorMessage = "No folder selected"
                            return
                        }

                        var foundFile = false
                        for (var i = 0; i < folderContents.length; i++) {
                            var rawEntry = folderContents[i]
                            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
                            if (sanitizedEntry.toLowerCase() === targetFileName.toLowerCase()) {
                                foundFile = true
                                break
                            }
                        }

                        if (!foundFile) {
                            interTrialModule.errorMessage = "data_ICApplied_clean_decomposed.mat not found in the selected folder"
                            return
                        }

                        interTrialModule.errorMessage = ""
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var escapedFolder = normalizedFolder.replace(/'/g, "\\'")
                        matlabExecutor.runMatlabScriptInteractive("intertrialcoherenceanalysis('" + escapedFolder + "')", true)
                    }
                }

                ModuleTemplate {
                    id: channelWiseModule
                    displayText: "Channel-Wise Coherence Analysis"
                    moduleName: "Channel-Wise Coherence Analysis"
                    outputFileName: "channelwise_coherence_output.mat"
                    visualizerFunction: "channelwise_visualizer"
                    currentFolder: processingPageRoot.currentFolder
                    folderContents: processingPageRoot.folderContents

                    onVisualizeClicked: {
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var outputFilePath = normalizedFolder + "/channelwise_coherence_output.mat"
                        var escapedPath = outputFilePath.replace(/'/g, "\\'")
                        var scriptParts = [
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/analysis/matlab'));",
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/preprocessing/matlab'));",
                            "data = load('" + escapedPath + "');",
                            "if isfield(data,'channelwise_coherence_output'), channelwise_visualizer(data.channelwise_coherence_output);",
                            "elseif isfield(data,'coherence_data'), channelwise_visualizer(data.coherence_data);",
                            "else, error('channelwise_coherence_output.mat missing channelwise_coherence_output or coherence_data'); end"
                        ]
                        var script = scriptParts.join(' ')
                        matlabExecutor.runMatlabScriptInteractive(script, true)
                    }

                    onButtonClicked: {
                        // Require decomposed cleaned data before running channel-wise coherence analysis
                        var targetFileName = "data_ICApplied_clean_decomposed.mat"

                        if (!currentFolder) {
                            channelWiseModule.errorMessage = "No folder selected"
                            return
                        }

                        var foundFile = false
                        for (var i = 0; i < folderContents.length; i++) {
                            var rawEntry = folderContents[i]
                            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
                            if (sanitizedEntry.toLowerCase() === targetFileName.toLowerCase()) {
                                foundFile = true
                                break
                            }
                        }

                        if (!foundFile) {
                            channelWiseModule.errorMessage = "data_ICApplied_clean_decomposed.mat not found in the selected folder"
                            return
                        }

                        channelWiseModule.errorMessage = ""
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var escapedFolder = normalizedFolder.replace(/'/g, "\\'")
                        matlabExecutor.runMatlabScriptInteractive("channelwise('" + escapedFolder + "')", true)
                    }
                }

                ModuleTemplate {
                    id: spectralModule
                    displayText: "Spectral Analysis"
                    moduleName: "Spectral Analysis"
                    outputFileName: "spectral_output.mat"
                    visualizerFunction: "spectral_visualizer"
                    currentFolder: processingPageRoot.currentFolder
                    folderContents: processingPageRoot.folderContents

                    onVisualizeClicked: {
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var outputFilePath = normalizedFolder + "/spectral_output.mat"
                        var escapedPath = outputFilePath.replace(/'/g, "\\'")
                        var scriptParts = [
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/analysis/matlab'));",
                            "addpath(genpath('C:/Users/mamam/Desktop/Capstone/features/preprocessing/matlab'));",
                            "data = load('" + escapedPath + "');",
                            "if isfield(data,'spectral_output'), spectral_visualizer(data.spectral_output);",
                            "elseif isfield(data,'spectral_data'), spectral_visualizer(data.spectral_data);",
                            "else, error('spectral_output.mat missing spectral_output or spectral_data'); end"
                        ]
                        var script = scriptParts.join(' ')
                        matlabExecutor.runMatlabScriptInteractive(script, true)
                    }

                    onButtonClicked: {
                        // Require decomposed cleaned data before running spectral analysis
                        var targetFileName = "data_ICApplied_clean_decomposed.mat"

                        if (!currentFolder) {
                            spectralModule.errorMessage = "No folder selected"
                            return
                        }

                        var foundFile = false
                        for (var i = 0; i < folderContents.length; i++) {
                            var rawEntry = folderContents[i]
                            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
                            if (sanitizedEntry.toLowerCase() === targetFileName.toLowerCase()) {
                                foundFile = true
                                break
                            }
                        }

                        if (!foundFile) {
                            spectralModule.errorMessage = "data_ICApplied_clean_decomposed.mat not found in the selected folder"
                            return
                        }

                        spectralModule.errorMessage = ""
                        var sanitizedFolder = currentFolder.replace(/^[^\w]+/, '').trim()
                        var basePath = sanitizedFolder.length > 0 ? sanitizedFolder : currentFolder
                        var normalizedFolder = basePath.replace(/\\/g, "/")
                        var escapedFolder = normalizedFolder.replace(/'/g, "\\'")
                        matlabExecutor.runMatlabScriptInteractive("spectralanalysis('" + escapedFolder + "')", true)
                    }
                }
            }
        }
    }
}
