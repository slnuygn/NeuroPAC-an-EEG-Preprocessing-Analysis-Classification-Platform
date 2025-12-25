import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import "../../preprocessing/qml"

Item {
    id: classifierTemplate
    width: parent.width
    height: rectangle.height + 4 + (expanded ? expandedRect.height + 2 : 0)
    z: 1000 

    property string displayText: "Classifier Module"
    property bool expanded: false
    property alias errorText: errorTextItem.text
    default property alias expandedContent: contentContainer.data
    property string classifierName: ""  // e.g., "EEGNet", "EEG-Inception", "Riemannian"
    property var configParameters: ({})  // Store parsed config parameters
    property var availableAnalyses: []  // Store available analyses
    property string selectedAnalysis: ""  // Store selected analysis
    
    signal classifyClicked(string classifierName, string analysisName)

    // Load configuration when classifier name is set
    onClassifierNameChanged: {
        if (classifierName && classifierName !== "") {
            loadAvailableAnalyses()
            configParameters = {}  // Clear parameters until analysis is selected
        }
    }

    function loadConfigurationForAnalysis(analysisName) {
        if (!classifierName || !analysisName) return;
        
        try {
            var jsonStr = classificationController.getParamsForAnalysis(classifierName, analysisName);
            var params = JSON.parse(jsonStr);
            configParameters = params;
            console.log("Loaded config for " + classifierName + " - " + analysisName + ":", Object.keys(configParameters).length, "parameters");
        } catch (e) {
            console.error("Failed to parse config for " + classifierName + " - " + analysisName + ":", e);
            configParameters = {};
        }
    }

    function loadAvailableAnalyses() {
        if (!classifierName) return;
        
        try {
            var jsonStr = classificationController.getAvailableAnalyses(classifierName);
            var analyses = JSON.parse(jsonStr);
            availableAnalyses = analyses;
            console.log("Available analyses for " + classifierName + ":", availableAnalyses);
        } catch (e) {
            console.error("Failed to load available analyses for " + classifierName + ":", e);
            availableAnalyses = [];
        }
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
            anchors.fill: parent
            anchors.margins: 10
            anchors.bottomMargin: 50
            spacing: 10

            // Analysis Selection Dropdown
            DropdownTemplate {
                width: contentContainer.width / 3
                label: "Select Analysis"
                matlabProperty: "analysis"
                model: availableAnalyses
                currentIndex: -1  // Start with no selection
                showCheckboxes: false  // Hide checkboxes for analysis dropdown
                
                onSelectionChanged: function(value, index) {
                    selectedAnalysis = value
                    console.log("Selected analysis:", selectedAnalysis)
                    loadConfigurationForAnalysis(selectedAnalysis)
                }
            }

            // Dynamic parameters from config files
            Repeater {
                model: Object.keys(configParameters)
                delegate: InputBoxTemplate {
                    width: contentContainer.width / 3
                    label: modelData
                    matlabProperty: modelData
                    text: {
                        var value = configParameters[modelData];
                        if (typeof value === "object") {
                            return JSON.stringify(value);
                        }
                        return String(value);
                    }
                    isNumeric: typeof configParameters[modelData] === "number"
                    placeholderText: "Enter " + modelData
                    
                    onValueChanged: function(newValue) {
                        // Update the config parameter when value changes
                        try {
                            // Try to parse as number first if it was originally numeric
                            if (isNumeric) {
                                configParameters[modelData] = parseFloat(newValue);
                            } else {
                                // Try to parse as JSON for objects/arrays
                                try {
                                    configParameters[modelData] = JSON.parse(newValue);
                                } catch (e) {
                                    // If not valid JSON, treat as string
                                    configParameters[modelData] = newValue;
                                }
                            }
                            console.log("Updated " + modelData + " to:", configParameters[modelData]);
                        } catch (e) {
                            console.error("Error updating parameter:", e);
                        }
                    }
                }
            }
        }


        Column {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 10
            spacing: 5
            width: parent.width - 20

            Text {
                id: errorTextItem
                text: ""
                color: "red"
                visible: text !== ""
                font.pixelSize: 12
                anchors.right: parent.right
            }

            // Floating Action Button - anchored to contentContainer bottom right
            Rectangle {
                id: classifyButton
                width: 150
                height: 40
                color: "#2196f3"
                radius: 5
                
                anchors.right: parent.right
                
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
                        text: "Classify"
                        color: "white"
                        font.pixelSize: 14
                        anchors.centerIn: parent
                    }
                    
                    onClicked: {
                        if (selectedAnalysis === "") {
                            errorTextItem.text = "Please select an analysis type first"
                            return
                        }
                        errorTextItem.text = ""
                        classifierTemplate.classifyClicked(classifierName, selectedAnalysis)
                    }
                }
            }
        }
    }
}
