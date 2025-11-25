import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import "."
import "../../preprocessing/ui"

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
    Rectangle {
        id: fileExplorerRect
        anchors.left: parent.left
        anchors.top: parent.top
        width: parent.width * 0.2
        height: parent.height
        color: "#f8f9fa"
        border.color: "#dee2e6"
        border.width: 2
        radius: 5

        Column {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 5

            // Folder icon and current folder display in same row
            Row {
                width: parent.width
                height: 30
                spacing: 10

                // Current Folder Display
                Text {
                    text: processingPageRoot.currentFolder ? "Folder: " + processingPageRoot.currentFolder : "No folder selected"
                    font.pixelSize: 12
                    color: "#666"
                    width: parent.width - 70
                    wrapMode: Text.Wrap
                    anchors.verticalCenter: parent.verticalCenter
                }

                // Spacer to push buttons to the right
                Item {
                    width: parent.width - (parent.children[0].width + 70)
                    height: 1
                }

                // Button group with tighter spacing
                Row {
                    spacing: 2
                    
                    // Refresh Button
                    Button {
                        width: 30
                        height: 30
                        
                        background: Rectangle {
                            color: parent.pressed ? "#dee2e6" : (parent.hovered ? "#f1f3f4" : "transparent")
                            radius: 4
                        }
                        
                        contentItem: Text {
                            text: "🔄"
                            font.pixelSize: 16
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: {
                            processingPageRoot.refreshFileExplorer()
                        }
                    }

                    // Folder Icon Button
                    Button {
                        width: 30
                        height: 30
                        
                        background: Rectangle {
                            color: parent.pressed ? "#dee2e6" : (parent.hovered ? "#f1f3f4" : "transparent")
                            radius: 4
                        }
                        
                        contentItem: Text {
                            text: "📁"
                            font.pixelSize: 16
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: {
                            processingPageRoot.openFolderDialog()
                        }
                    }
                }
            }

            // File Explorer
            Column {
                width: parent.width
                height: parent.height - 30

                Text {
                    text: "File Explorer"
                    font.bold: true
                    color: "#495057"
                    font.pixelSize: 12
                }

                Rectangle {
                    width: parent.width
                    height: parent.height - 20
                    color: "white"
                    border.color: "#ccc"
                    border.width: 1
                    radius: 3

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 5
                        clip: true

                        ListView {
                            id: folderListView
                            anchors.fill: parent
                            model: processingPageRoot.folderContents
                            
                            delegate: Item {
                                width: folderListView.width
                                height: 25

                                Rectangle {
                                    anchors.fill: parent
                                    color: fileMouseArea.containsMouse ? "#e3f2fd" : "transparent"
                                    radius: 3
                                    
                                    MouseArea {
                                        id: fileMouseArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        
                                        onClicked: function(mouse) {
                                            if (mouse.button === Qt.LeftButton) {
                                                var cleanFilename = modelData.replace(/^[^\w]+/, '')
                                                
                                                if (cleanFilename.toLowerCase().endsWith('.mat')) {
                                                    var isICAFile = cleanFilename.toLowerCase().includes('ica') || 
                                                                   cleanFilename.toLowerCase().includes('comp') ||
                                                                   cleanFilename.toLowerCase().includes('component')
                                                    
                                                    if (isICAFile) {
                                                        console.log("ICA file detected:", cleanFilename)
                                                        var fullPath = processingPageRoot.currentFolder + "/" + cleanFilename
                                                        
                                                        if (matlabExecutor) {
                                                            matlabExecutor.launchMatlabICABrowser(fullPath)
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    
                                    Row {
                                        anchors.left: parent.left
                                        anchors.leftMargin: 5
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 5
                                        
                                        Text {
                                            text: modelData
                                            font.pixelSize: 10
                                            color: modelData.endsWith('.mat') ? 
                                                (modelData.includes('ICA') || modelData.includes('ica') ? "#4caf50" : "#007bff") : "#333"
                                            font.underline: modelData.endsWith('.mat') && fileMouseArea.containsMouse
                                        }
                                        
                                        Text {
                                            text: modelData.endsWith('.mat') ? 
                                                (modelData.includes('ICA') || modelData.includes('ica') ? "🧠" : "📊") : ""
                                            font.pixelSize: 8
                                            visible: modelData.endsWith('.mat') && fileMouseArea.containsMouse
                                        }
                                    }
                                }

                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    width: parent.width
                                    height: 1
                                    color: "#eee"
                                }
                            }
                        }
                    }
                }
            }
        }
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
                        if (!validateTargetFile()) {
                            errorText.text = errorMessage
                            return
                        }
                        
                        errorText.text = ""
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
