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
                    currentFolder: processingPageRoot.currentFolder
                    folderContents: processingPageRoot.folderContents

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
                }

                ModuleTemplate {
                    id: interTrialModule
                    displayText: "Inter-Trial Coherence Analysis"
                    moduleName: "Inter-Trial Coherence Analysis"
                }

                ModuleTemplate {
                    id: channelWiseModule
                    displayText: "Channel-Wise Coherence Analysis"
                    moduleName: "Channel-Wise Coherence Analysis"
                }

                ModuleTemplate {
                    id: spectralModule
                    displayText: "Spectral Analysis"
                    moduleName: "Spectral Analysis"
                }
            }
        }
    }
}
