import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15

Item {
    id: moduleTemplate
    width: parent.width
    height: rectangle.height + 4 + (expanded ? contentContainer.height + 2 : 0)
    z: 1000

    property string displayText: "Analysis Module"
    property bool expanded: false
    property string currentFolder: ""
    property var folderContents: []
    property string errorMessage: ""
    property string moduleName: ""  // Name used to find corresponding MATLAB file
    property bool editModeEnabled: false  // Track edit mode state
    property string outputFileName: ""  // Output file to check for (e.g., "erp_output.mat")
    property string visualizerFunction: ""  // MATLAB visualizer function name (e.g., "erp_visualizer")
    signal buttonClicked()
    signal visualizeClicked()  // New signal for visualize button
    default property alias expandedContent: contentContainer.data

    // Dynamic parameters loaded from MATLAB file
    property var dynamicParameters: ({})

    // Property to track if output file exists
    property bool outputFileExists: false

    // Check for output file whenever folder contents or outputFileName changes
    onFolderContentsChanged: checkOutputFile()
    onOutputFileNameChanged: checkOutputFile()
    onCurrentFolderChanged: checkOutputFile()

    function checkOutputFile() {
        if (!outputFileName || !currentFolder || folderContents.length === 0) {
            outputFileExists = false
            return
        }
        
        var found = false
        for (var i = 0; i < folderContents.length; i++) {
            var rawEntry = folderContents[i]
            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
            if (sanitizedEntry.toLowerCase() === outputFileName.toLowerCase()) {
                found = true
                break
            }
        }
        
        outputFileExists = found
        console.log("Output file check for", outputFileName, ":", found)
    }

    // Load parameters when module name is set
    onModuleNameChanged: {
        if (moduleName && moduleName !== "") {
            loadDynamicParameters()
        }
    }

    function loadDynamicParameters() {
        if (!moduleName) return;
        
        // Use the Python backend to parse parameters, ensuring consistency with Preprocessing page
        var jsonStr = matlabExecutor.getModuleParameters(moduleName);
        try {
            var params = JSON.parse(jsonStr);
            dynamicParameters = params;
            console.log("Parsed parameters for " + moduleName + ":", Object.keys(dynamicParameters).length);
        } catch (e) {
            console.error("Failed to parse dynamic parameters for " + moduleName + ":", e);
            dynamicParameters = {};
        }
    }

    // Function to validate if target file exists in folder
    function validateTargetFile() {
        var targetFileName = "data_ICApplied_clean.mat"
        
        if (!currentFolder) {
            errorMessage = "No folder selected"
            return false
        }
        
        var foundCleanMat = false
        for (var i = 0; i < folderContents.length; i++) {
            var rawEntry = folderContents[i]
            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
            if (sanitizedEntry.toLowerCase() === targetFileName.toLowerCase()) {
                foundCleanMat = true
                break
            }
        }
        
        if (!foundCleanMat) {
            errorMessage = "data_ICApplied_clean.mat not found in the selected folder"
            return false
        }
        
        errorMessage = ""
        return true
    }

    Rectangle {
        id: rectangle
        width: parent.width - 10
        height: text.implicitHeight + 10
        anchors.top: parent.top
        anchors.topMargin: 2
        anchors.horizontalCenter: parent.horizontalCenter
        color: "#f0f0f0"
        border.color: "#ccc"
        border.width: 1
        radius: 3

        MouseArea {
            anchors.fill: parent
            onClicked: expanded = !expanded
        }

        Text {
            id: text
            text: displayText
            font.pixelSize: 24
            color: "#333"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
        }

        Text {
            id: arrow
            text: "▼"
            font.pixelSize: 12
            color: "#666"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.rightMargin: 10
        }
    }

    Column {
        id: contentContainer
        visible: expanded
        width: parent.width - 10
        anchors.top: rectangle.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 1
        spacing: 10

        Rectangle {
            width: parent.width
            height: parametersColumn.implicitHeight + 20
            color: "#e0e0e0"
            border.color: "#ccc"
            border.width: 1
            radius: 3

            Column {
                id: parametersColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                anchors.topMargin: 10
                spacing: 10

                // Dynamic parameters loaded from MATLAB file
                Repeater {
                    model: Object.keys(dynamicParameters)
                    delegate: DynamicParameterLoader {
                        width: parametersColumn.width
                        parameterName: modelData
                        parameterConfig: dynamicParameters[modelData]
                        editModeEnabled: moduleTemplate.editModeEnabled
                        moduleName: moduleTemplate.moduleName

                        onParameterChanged: function(paramName, value) {
                            console.log("Parameter changed:", paramName, "=", value);
                            // TODO: Save parameter to MATLAB
                        }
                    }
                }

                // Error text display - common for all modules
                Text {
                    id: errorText
                    text: ""
                    color: "red"
                    visible: text !== ""
                    font.pixelSize: 12
                    width: parent.width
                }
            }
        }
    }

    // Visualize Button - anchored above Feature Extract button
    Rectangle {
        id: visualizeButton
        visible: expanded && outputFileExists
        width: 150
        height: 40
        color: "white"
        border.color: "#2196f3"
        border.width: 1
        radius: 5
        
        anchors.right: contentContainer.right
        anchors.bottom: moduleButton.top
        anchors.margins: 10
        
        z: 1000

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            
            onClicked: {
                moduleTemplate.visualizeClicked()
            }
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1  // Keep inside the border
            color: parent.parent.pressed ? "#e3f2fd" : (parent.parent.containsMouse ? "#dcdbdbff" : "transparent")
            radius: 4
            z: -1  // Place behind the text
        }

        Text {
            text: "Visualize"
            color: "#2196f3"
            font.pixelSize: 14
            anchors.centerIn: parent
        }
    }

    // Floating Action Button - anchored to contentContainer bottom right
    Rectangle {
        id: moduleButton
        visible: expanded
        width: 150
        height: 40
        color: "#2196f3"
        radius: 5
        
        anchors.right: contentContainer.right
        anchors.bottom: contentContainer.bottom
        anchors.margins: 10
        
        z: 1000

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            
            Rectangle {
                anchors.fill: parent
                color: parent.pressed ? "#1565c0" : (parent.containsMouse ? "#2196f3" : "transparent")
                radius: 5
            }

            Text {
                text: "Feature Extract"
                color: "white"
                font.pixelSize: 14
                anchors.centerIn: parent
            }
            
            onClicked: {
                moduleTemplate.buttonClicked()
            }
        }
    }
}
