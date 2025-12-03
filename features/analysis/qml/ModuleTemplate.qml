import QtQuick 2.15
import QtQuick.Window 2.15

Item {
    id: moduleTemplate
    width: parent.width
    height: rectangle.height + 4 + (expanded ? expandedRect.height + 2 : 0)
    z: 1000

    property string displayText: "Analysis Module"
    property bool expanded: false
    property string currentFolder: ""
    property var folderContents: []
    property string errorMessage: ""
    property string moduleName: ""  // Name used to find corresponding MATLAB file
    property bool editModeEnabled: false  // Track edit mode state
    signal buttonClicked()
    default property alias expandedContent: contentContainer.data

    // Dynamic parameters loaded from MATLAB file
    property var dynamicParameters: ({})

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

    MouseArea {
        anchors.fill: parent
        onClicked: expanded = !expanded
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

    Rectangle {
        id: expandedRect
        visible: expanded
        width: parent.width - 10
        height: expanded ? Math.max(contentContainer.implicitHeight + 20, 120) : 0
        anchors.top: rectangle.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 1
        color: "#e0e0e0"
        border.color: "#ccc"
        border.width: 1
        radius: 3

        Column {
            id: contentContainer
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            spacing: 10

            // Dynamic parameters loaded from MATLAB file
            Repeater {
                model: Object.keys(dynamicParameters)
                delegate: DynamicParameterLoader {
                    width: contentContainer.width
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

        Item {
            width: parent.width - 20
            height: moduleButton.implicitHeight
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 10

            Button {
                id: moduleButton
                text: "Feature Extract"
                anchors.right: parent.right
                flat: true
                padding: 10
                background: Rectangle {
                    color: "#2196f3"
                    radius: 4
                    anchors.fill: parent
                }

                onClicked: {
                    moduleTemplate.buttonClicked()
                }
            }
        }
    }
}
