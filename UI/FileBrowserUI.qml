import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Dialogs
import FileBrowser 1.0

Item {
    id: fileBrowserUI
    anchors.left: parent.left
    anchors.top: parent.top
    width: parent.width * 0.2  // Slightly wider
    height: parent.height
    
    // Properties exposed to parent
    property var folderContents: []
    property string currentFolder: ""
    property alias folderDialog: folderDialog
    property alias fieldtripDialog: fieldtripDialog
    
    // Signals for parent communication
    signal refreshRequested()
    signal folderChanged(string folder)
    signal contentsChanged(var contents)
    signal fieldtripPathRequested()
    signal dataDirectoryUpdateRequested(string path)
    
    // Signal for file left-click
    signal fileLeftClicked(string fileName, string displayName)
    
    // Signal for file right-click (for context menu)
    signal fileRightClicked(string cleanFilename, string fullPath, bool isMatFile, real mouseX, real mouseY)
    signal fieldtripPathUpdateRequested(string path)
    
    // Connect to the fileBrowser backend signals
    Connections {
        target: fileBrowser
        function onFolderContentsChanged(contents) {
            fileBrowserUI.folderContents = contents
            fileBrowserUI.contentsChanged(contents)
        }
        function onCurrentFolderChanged(folder) {
            fileBrowserUI.currentFolder = folder
            fileBrowserUI.folderChanged(folder)
        }
    }
    
    // Function to refresh folder contents
    function refreshFolderContents() {
        if (fileBrowser) {
            fileBrowser.refreshCurrentFolder()
        }
        refreshRequested()
    }
    
    // File Dialog for folder selection
    FolderDialog {
        id: folderDialog
        title: "Select Folder"
        currentFolder: fileBrowser ? "file:///" + fileBrowser.getDesktopPath() : "file:///C:/Users"
        
        onAccepted: {
            if (fileBrowser) {
                fileBrowser.loadFolder(selectedFolder.toString())
                // Signal to parent to also update the MATLAB script with the selected folder
                dataDirectoryUpdateRequested(selectedFolder.toString())
            }
        }
    }
    
    // FieldTrip Path Dialog
    FolderDialog {
        id: fieldtripDialog
        title: "Select FieldTrip Installation Folder"
        currentFolder: "file:///C:/Program Files/MATLAB"
        
        onAccepted: {
            fieldtripPathUpdateRequested(selectedFolder.toString())
        }
    }
    
    // File Explorer View Content (Directly in Item)
    Rectangle {
        id: fileExplorerRect
        anchors.fill: parent
        color: "#f8f9fa"
        border.color: "#dee2e6"
        border.width: 2
        radius: 5

        Column {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 5

            // Folder icon and current folder display in same row
            Item {
                width: parent.width
                height: 30

                // Current Folder Display
                Text {
                    anchors.left: parent.left
                    anchors.right: buttonGroup.left
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    
                    text: fileBrowserUI.currentFolder ? "Folder: " + fileBrowserUI.currentFolder : "No folder selected"
                    font.pixelSize: 12
                    color: "#666"
                    elide: Text.ElideRight
                }

                // Button group with tighter spacing
                Row {
                    id: buttonGroup
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2 // Very tight spacing between buttons
                    
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
                            fileBrowserUI.refreshFolderContents()
                        }
                    }

                    // Folder Icon Button (positioned at the right)
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
                            folderDialog.open()
                        }
                    }
                }
            }

            // Drive Files (full height)
            Item {
                width: parent.width
                height: parent.height - 30  // Full height minus header row

                Text {
                    id: fileExplorerLabel
                    text: "File Explorer"
                    font.bold: true
                    color: "#495057"
                    font.pixelSize: 12
                    
                }

                Rectangle {
                    width: parent.width
                    height: parent.height - 15  // Account for text height
                    y: fileExplorerLabel.height + 2  // Position 2px below text
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
                            model: fileBrowserUI.folderContents
                            
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
                                            if (mouse.button === Qt.RightButton) {
                                                // Emit signal for right-click context menu
                                                var cleanFilename = modelData.replace(/^[^\w]+/, '')  // Remove leading emojis/symbols
                                                var fullPath = fileBrowserUI.currentFolder + "/" + cleanFilename
                                                var isMatFile = cleanFilename.toLowerCase().endsWith('.mat')
                                                
                                                // Emit signal with file info and mouse coordinates
                                                fileBrowserUI.fileRightClicked(cleanFilename, fullPath, isMatFile, mouse.x, mouse.y)
                                            } else if (mouse.button === Qt.LeftButton) {
                                                // Emit signal for left-click
                                                var cleanFilename = modelData.replace(/^[^\w]+/, '')  // Remove leading emojis/symbols
                                                fileBrowserUI.fileLeftClicked(cleanFilename, modelData)

                                                // Handle .mat file clicks (ICA detection)
                                                if (cleanFilename.toLowerCase().endsWith('.mat')) {
                                                    // Check if it's an ICA file by looking for ICA indicators in filename
                                                    var isICAFile = cleanFilename.toLowerCase().includes('ica') || 
                                                                   cleanFilename.toLowerCase().includes('comp') ||
                                                                   cleanFilename.toLowerCase().includes('component')
                                                    
                                                    if (isICAFile) {
                                                        console.log("ICA file detected:", cleanFilename)
                                                        var fullPath = fileBrowserUI.currentFolder + "/" + cleanFilename
                                                        
                                                        // Call browse_ICA function through MATLAB executor
                                                        if (typeof matlabExecutor !== "undefined" && matlabExecutor) {
                                                            matlabExecutor.launchMatlabICABrowser(fullPath)
                                                        }
                                                    } else {
                                                        console.log("Not an ICA file:", cleanFilename)
                                                    }
                                                } else {
                                                    console.log("Not a .mat file:", cleanFilename)
                                                }
                                            }
                                        }
                                    }
                                    
                                    Text {
                                        id: iconText
                                        anchors.right: parent.right
                                        anchors.rightMargin: 5
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.endsWith('.mat') ? 
                                            (modelData.includes('ICA') || modelData.includes('ica') ? "🧠" : "📊") : ""
                                        font.pixelSize: 8
                                        visible: modelData.endsWith('.mat') && fileMouseArea.containsMouse
                                    }

                                    Text {
                                        anchors.left: parent.left
                                        anchors.leftMargin: 5
                                        anchors.right: iconText.visible ? iconText.left : parent.right
                                        anchors.rightMargin: 5
                                        anchors.verticalCenter: parent.verticalCenter
                                        
                                        text: modelData
                                        font.pixelSize: 12
                                        color: modelData.endsWith('.mat') ? 
                                            (modelData.includes('ICA') || modelData.includes('ica') ? "#4caf50" : "#007bff") : "#333"
                                        font.underline: modelData.endsWith('.mat') && fileMouseArea.containsMouse
                                        elide: Text.ElideRight
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
    
    // File Menu Items Component
    Component {
        id: fileMenuItems
        
        Column {
            // Change FieldTrip path
            Rectangle {
                width: parent.width
                height: 35
                color: changeFieldtripMouseArea.containsMouse ? "#f8f9fa" : "white"

                Row {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 10
                    spacing: 10

                    Text {
                        text: "Change FieldTrip path..."
                        font.pixelSize: 12
                        color: "#333"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: changeFieldtripMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: function(mouse) {
                        fieldtripDialog.open()
                        fieldtripPathRequested()
                    }
                }
            }

            // Change data path
            Rectangle {
                width: parent.width
                height: 35
                color: changeDataPathMouseArea.containsMouse ? "#f8f9fa" : "white"

                Row {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 10
                    spacing: 10

                    Text {
                        text: "Change data path..."
                        font.pixelSize: 12
                        color: "#333"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: changeDataPathMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: function(mouse) {
                        folderDialog.open()
                    }
                }
            }
        }
    }
    
    // Function to get file menu items
    function getFileMenuItems() {
        return fileMenuItems
    }
    
    // Function to create file explorer view (Deprecated, but kept for compatibility if needed)
    function createFileExplorerView(parent, x, y, width, height) {
        console.warn("createFileExplorerView is deprecated. Use FileBrowserUI component directly.")
        return null
    }
}