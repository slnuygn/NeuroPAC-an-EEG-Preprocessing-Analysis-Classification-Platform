import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
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
    property bool isLoadingLabels: false
    
    // Signals for parent communication
    signal refreshRequested()
    signal folderChanged(string folder)
    signal contentsChanged(var contents)
    signal fieldtripPathRequested()
    signal dataDirectoryUpdateRequested(string path)
    
    // Signal to refresh folder contents from external source
    signal externalRefreshRequested()
    
    // Signals for file operations (existing)
    signal fileLeftClicked(string fileName, string displayName)
    signal fileMatClicked(string fileName, string fullPath, string displayName)
    signal fileRightClicked(string cleanFilename, string fullPath, bool isMatFile, real mouseX, real mouseY)
    signal fieldtripPathUpdateRequested(string path)
    
    // Model for the label window contents (can be set externally for global persistence)
    property var labelListModel: internalLabelListModel
    ListModel {
        id: internalLabelListModel
    }
    
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
    
    // Populate label window when the file browser reports a data.mat click
    Connections {
        target: fileBrowserUI
        function onFileMatClicked(fileName, fullPath, displayName) {
            labelListModel.clear()
            parent.loadingStateChanged(true)

            // Normalize path separators
            var fp = fullPath.replace(/\\/g, '/')

            // Use Python method to get dataset names
            try {
                var datasetNames = matlabExecutor.listMatDatasets(fp)
                parent.loadingStateChanged(false)
                if (datasetNames && datasetNames.length > 0) {
                    // Load existing labels
                    var existingLabels = matlabExecutor.loadLabels()
                    for (var i = 0; i < datasetNames.length; ++i) {
                        var label = (i < existingLabels.length) ? existingLabels[i] : ""
                        labelListModel.append({"text": datasetNames[i], "label": label})
                    }
                } else {
                    labelListModel.append({"text": displayName || fileName, "label": ""})
                }
            } catch (e) {
                parent.loadingStateChanged(false)
                console.log('Error calling matlabExecutor.listMatDatasets:', e)
                labelListModel.append({"text": displayName || fileName, "label": ""})
            }
        }
    }
    
    // Function to refresh folder contents
    function refreshFolderContents() {
        if (fileBrowser) {
            fileBrowser.refreshCurrentFolder()
        }
        refreshRequested()
    }
    
    // Function to trigger refresh from external source (e.g., after classification)
    function refreshFromExternal() {
        refreshFolderContents()
    }
    
    // Function to save labels to Python
    function saveLabels() {
        var labels = []
        for (var i = 0; i < labelListModel.count; ++i) {
            labels.push(labelListModel.get(i).label)
        }
        if (typeof matlabExecutor !== "undefined" && matlabExecutor) {
            matlabExecutor.saveLabels(labels)
        }
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

            // Drive Files
            Column {
                id: driveColumn
                width: parent.width
                spacing: 2

                // computed responsive section height (split remaining space)
                property real computedSectionHeight: {
                    var total = parent ? parent.height : 0
                    var hLabel = fileExplorerLabel ? fileExplorerLabel.implicitHeight : 0
                    var hSubLabel = (typeof label !== 'undefined') ? label.implicitHeight : 0
                    var used = hLabel + hSubLabel + spacing*2 + 12
                    var avail = total - used
                    var base = avail > 80 ? avail/2 : Math.max(80, avail/2)
                    return base * 0.95
                }

                Text {
                    id: fileExplorerLabel
                    text: "File Explorer"
                    font.bold: true
                    color: "#495057"
                    font.pixelSize: 12
                }

                // small spacer between explorer rectangle and label
                Item { height: 8 }

                // Label section (placed under the file explorer)
                Rectangle {
                    width: parent.width
                    height: driveColumn.computedSectionHeight
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
                                                            // If it's the special data.mat we want to open in the classification UI, emit dedicated signal
                                                            var fullPath = fileBrowserUI.currentFolder + "/" + cleanFilename
                                                            if (cleanFilename.toLowerCase() === 'data.mat') {
                                                                fileBrowserUI.fileMatClicked(cleanFilename, fullPath, modelData)
                                                            } else {
                                                                console.log("Not an ICA file:", cleanFilename)
                                                            }
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


            Item { height: 10 }  // Spacer to push the label section down

            // Label section (placed under the file explorer)
            Column {
                width: parent.width
                spacing: 2

                Text {
                    id: label
                    text: "Label Your Data"
                    font.bold: true
                    color: "#495057"
                    font.pixelSize: 12
                    anchors.left: parent.left
                }

                Rectangle {
                    width: parent.width
                    height: driveColumn.computedSectionHeight
                    color: "white"
                    border.color: "#ccc"
                    border.width: 1
                    radius: 3

                    ScrollView {
                                    anchors.fill: parent
                                    clip: true
                                    topPadding: 5

                                    Column {
                                        id: labelContentColumn
                                        width: parent.width
                                        spacing: 4
                                        
                                        Repeater {
                                            model: labelListModel
                                            delegate: Rectangle {
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.leftMargin: 2
                                                anchors.rightMargin: 2
                                                height: 24
                                                color: (index % 2 === 0) ? "white" : "#e2f6ffff"

                                                RowLayout {
                                                    anchors.fill: parent
                                                    spacing: 20

                                                    Text {
                                                        text: (index+1) + ": " + model.text
                                                        font.pixelSize: 12
                                                        elide: Text.ElideRight
                                                        width: 150
                                                        Layout.alignment: Qt.AlignVCenter
                                                    }

                                                    Item {
                                                        Layout.fillWidth: true
                                                    }

                                                    TextField {
                                                        id: inputBox
                                                        width: 40
                                                        placeholderText: "Enter label"
                                                        horizontalAlignment: Text.AlignLeft
                                                        color: "black"
                                                        placeholderTextColor: "white"
                                                        background: Rectangle {
                                                            color: "white"
                                                            radius: 2
                                                            border.color: "#ccc"
                                                            border.width: 1
                                                        }
                                                        Component.onCompleted: text = model.label
                                                        onTextChanged: {
                                                            labelListModel.setProperty(index, "label", text)
                                                        }
                                                        onAccepted: {
                                                            saveLabels()
                                                        }
                                                        Layout.alignment: Qt.AlignVCenter
                                                    }
                                                }
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

}

