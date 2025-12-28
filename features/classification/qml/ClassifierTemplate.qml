import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
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
    property bool classifyExecuted: false  // Track if classify has been executed
    property var classifyLogs: []  // Store logs from classify operations
    property var currentFolderContents: []  // Track files in current directory
    property string currentFolderPath: ""  // Track current folder path
    property bool weightsFileExists: false  // Track if weights file exists for current classifier/analysis
    property var subjectListModel: null  // Optional: subjects/patients list from FileBrowser labels
    
    signal classifyClicked(string classifierName, string analysisName)
    signal testClassifierClicked(string classifierName, string analysisName, string weightsPath)
    
    // Function to check if weights file exists for current classifier and analysis
    function checkWeightsFileExists() {
        if (!classifierName || !selectedAnalysis || !currentFolderContents) {
            weightsFileExists = false
            return
        }
        
        // Convert analysis display name to key (e.g., "ERP Analysis" -> "erp")
        var analysisKey = ""
        try {
            analysisKey = classificationController.getAnalysisKey(selectedAnalysis)
        } catch (e) {
            analysisKey = ""
        }
        if (!analysisKey || analysisKey.length === 0) {
            // Fallback to a sanitized version if mapping is unavailable
            analysisKey = selectedAnalysis.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_\-]/g, '')
        }

        // Build expected filename pattern: ClassifierName_<key>_weights_best.keras
        var expectedFileName = (classifierName + "_" + analysisKey + "_weights_best.keras").toLowerCase()
        
        for (var i = 0; i < currentFolderContents.length; i++) {
            var fileName = currentFolderContents[i]
            // Remove any leading emoji/symbols for comparison
            var cleanFileName = fileName.replace(/^[^\w]+/, '').toLowerCase()
            
            if (cleanFileName === expectedFileName) {
                weightsFileExists = true
                console.log("Weights file found:", fileName)
                return
            }
        }
        weightsFileExists = false
    }

    // Try to auto-select an analysis based on weights in the folder
    function tryAutoSelectAnalysisFromWeights() {
        if (!classifierName || !currentFolderContents || !availableAnalyses || availableAnalyses.length === 0) return
        // If user already selected an analysis, don't override
        if (selectedAnalysis && selectedAnalysis.length > 0) return

        for (var a = 0; a < availableAnalyses.length; a++) {
            var display = availableAnalyses[a]
            var key = ""
            try {
                key = classificationController.getAnalysisKey(display)
            } catch (e) {
                key = ""
            }
            if (!key || key.length === 0) continue

            var expected = (classifierName + "_" + key + "_weights_best.h5").toLowerCase()
            for (var i = 0; i < currentFolderContents.length; i++) {
                var fileName = currentFolderContents[i]
                var cleanFileName = fileName.replace(/^[^\w]+/, '').toLowerCase()
                if (cleanFileName === expected) {
                    selectedAnalysis = display
                    console.log("Auto-selected analysis based on weights:", selectedAnalysis)
                    loadConfigurationForAnalysis(selectedAnalysis)
                    expanded = true
                    checkWeightsFileExists()
                    return
                }
            }
        }
    }
    
    // Function to get the full path of the weights file
    function getWeightsFilePath() {
        if (!currentFolderPath) return ""
        
        // Convert analysis display name to key (e.g., "ERP Analysis" -> "erp")
        var analysisKey = ""
        try {
            analysisKey = classificationController.getAnalysisKey(selectedAnalysis)
        } catch (e) {
            analysisKey = ""
        }
        if (!analysisKey || analysisKey.length === 0) {
            // Fallback to a sanitized version if mapping is unavailable
            analysisKey = selectedAnalysis.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_\-]/g, '')
        }
        
        var expectedFileName = classifierName + "_" + analysisKey + "_weights_best.keras"
        return currentFolderPath + "/" + expectedFileName
    }
    
    // Re-check weights when folder contents change
    onCurrentFolderContentsChanged: {
        checkWeightsFileExists()
    }
    onSelectedAnalysisChanged: checkWeightsFileExists()

    // Load configuration when classifier name is set
    onClassifierNameChanged: {
        if (classifierName && classifierName !== "") {
            loadAvailableAnalyses()
            configParameters = {}  // Clear parameters until analysis is selected
        }
        // Also re-check for weights file when classifier changes
        checkWeightsFileExists()
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

    // Connection to capture logs from classification controller
    Connections {
        target: classificationController
        function onLogReceived(message) {
            if (classifyExecuted) {
                var timestamp = "[" + new Date().toLocaleTimeString() + "] ";
                classifyLogs.push(timestamp + message);
                // Trigger console update
                classifyLogs = classifyLogs.slice();  // Force array update
            }
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

            // Test Classifier Button - Only visible when weights file exists
            Rectangle {
                id: testClassifierButton
                visible: weightsFileExists && selectedAnalysis !== ""
                enabled: weightsFileExists && selectedAnalysis !== ""
                width: 150
                height: 40
                color: "white"
                border.color: "#2196f3"
                border.width: 1
                radius: 5
                
                anchors.right: parent.right
                
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: parent.parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: parent.parent.enabled
                    
                    onClicked: {
                        if (!testClassifierButton.enabled) return
                        
                        var weightsPath = getWeightsFilePath()
                        console.log("Testing classifier with weights:", weightsPath)
                        
                        // Add log entry
                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Testing classifier...")
                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Weights file: " + weightsPath)
                        classifyLogs = classifyLogs.slice()  // Force array update
                        
                        // Open the test classifier window
                        testClassifierWindow.classifierName = classifierName
                        testClassifierWindow.selectedAnalysis = selectedAnalysis
                        testClassifierWindow.weightsPath = weightsPath
                        testClassifierWindow.show()
                        testClassifierWindow.raise()
                        
                        classifierTemplate.testClassifierClicked(classifierName, selectedAnalysis, weightsPath)
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 1
                    color: testClassifierButton.enabled ? 
                           (parent.parent.pressed ? "#e3f2fd" : (parent.parent.containsMouse ? "#dcdbdbff" : "transparent")) : 
                           "transparent"
                    radius: 4
                    z: -1
                }

                Text {
                    text: "Test Classifier"
                    color: testClassifierButton.enabled ? "#2196f3" : "#cccccc"
                    font.pixelSize: 14
                    anchors.centerIn: parent
                }
            }

            // Open Console Button
            Rectangle {
                id: openConsoleButton
                visible: classifyExecuted  // Only visible after classify is executed
                width: 150
                height: 40
                color: "white"
                border.color: "#2196f3"
                border.width: 1
                radius: 5
                
                anchors.right: parent.right
                
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    
                    onClicked: {
                        consoleWindow.show()
                        consoleWindow.raise()
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
                    text: "Open Console"
                    color: "#2196f3"
                    font.pixelSize: 14
                    anchors.centerIn: parent
                }
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
                        
                        // Clear previous logs and mark as executed
                        classifyLogs = []
                        classifyExecuted = true
                        
                        // Add initial log
                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Starting classification...")
                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Classifier: " + classifierName)
                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Analysis: " + selectedAnalysis)
                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Parameters: " + JSON.stringify(configParameters))
                        
                        classifierTemplate.classifyClicked(classifierName, selectedAnalysis)
                        
                        // Add completion log (you can update this based on actual results)
                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Classification request sent")
                    }
                }
            }
        }
    }
    
    // Update console text when logs change and auto-scroll
    onClassifyLogsChanged: {
        if (consoleText) {
            consoleText.text = classifyLogs.join("\n")
            // Defer scrolling so layout/contentHeight is updated
            Qt.callLater(function() {
                if (consoleScrollView && consoleScrollView.ScrollBar.vertical) {
                    consoleScrollView.ScrollBar.vertical.position = 1.0 - consoleScrollView.ScrollBar.vertical.size
                }
            })
        }
    }

    // Console Window
    Window {
        id: consoleWindow
        title: "Classification Console - " + classifierName
        width: 600
        height: 400
        minimumWidth: 400
        minimumHeight: 300

        Rectangle {
            anchors.fill: parent
            color: "#1e1e1e"

            ScrollView {
                id: consoleScrollView
                anchors.fill: parent
                anchors.margins: 10
                clip: true

                ScrollBar.horizontal: ScrollBar {
                    policy: ScrollBar.AlwaysOff
                }

                Text {
                    id: consoleText
                    text: classifyLogs.join("\n")
                    color: "#d4d4d4"
                    font.family: "Consolas, Monaco, monospace"
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignTop
                    width: consoleScrollView.availableWidth
                }
            }
        }
    }

    // Test Classifier Window
    Window {
        id: testClassifierWindow
        title: "Test Classifier - " + classifierName + " - " + selectedAnalysis
        width: 800
        height: 600
        minimumWidth: 600
        minimumHeight: 400

        property string classifierName: ""
        property string selectedAnalysis: ""
        property string weightsPath: ""
        property var testResults: null  // Store parsed test results
        property bool testRunning: false
        property var testLogs: []

        // Connection to receive test results
        Connections {
            target: classificationController
            function onTestResults(jsonResults) {
                try {
                    testClassifierWindow.testResults = JSON.parse(jsonResults)
                    testClassifierWindow.testRunning = false
                    console.log("Test results received:", jsonResults)
                } catch (e) {
                    console.error("Failed to parse test results:", e)
                    testClassifierWindow.testRunning = false
                }
            }
            function onLogReceived(message) {
                if (testClassifierWindow.testRunning) {
                    testClassifierWindow.testLogs.push("[" + new Date().toLocaleTimeString() + "] " + message)
                    testClassifierWindow.testLogs = testClassifierWindow.testLogs.slice()  // Force update
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            color: "#f0f0f0"

            Column {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 15

                Text {
                    text: "Classifier: " + testClassifierWindow.classifierName + "  |  Analysis: " + testClassifierWindow.selectedAnalysis
                    font.pixelSize: 18
                    font.bold: true
                    color: "#333"
                    wrapMode: Text.Wrap
                    width: parent.width - 40
                }

                Text {
                    text: "Weights: " + testClassifierWindow.weightsPath
                    font.pixelSize: 14
                    color: "#777"
                    wrapMode: Text.WrapAnywhere
                    width: parent.width - 40
                }

                // Test button
                Rectangle {
                    width: 150
                    height: 40
                    color: testClassifierWindow.testRunning ? "#ccc" : "#2196f3"
                    radius: 5
                    enabled: !testClassifierWindow.testRunning

                    MouseArea {
                        anchors.fill: parent
                        enabled: !testClassifierWindow.testRunning
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor

                        onClicked: {
                            testClassifierWindow.testRunning = true
                            testClassifierWindow.testResults = null
                            testClassifierWindow.testLogs = []
                            classificationController.testClassifier(
                                testClassifierWindow.classifierName,
                                testClassifierWindow.selectedAnalysis,
                                testClassifierWindow.weightsPath
                            )
                        }
                    }

                    Text {
                        text: testClassifierWindow.testRunning ? "Testing..." : "Run Test"
                        color: "white"
                        font.pixelSize: 14
                        anchors.centerIn: parent
                    }
                }

                // Results display
                Rectangle {
                    visible: testClassifierWindow.testResults !== null
                    width: parent.width - 40
                    height: resultsContent.implicitHeight + 20
                    color: "white"
                    border.color: "#2196f3"
                    border.width: 2
                    radius: 5

                    Column {
                        id: resultsContent
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10

                        Text {
                            text: "Test Results"
                            font.pixelSize: 18
                            font.bold: true
                            color: "#2196f3"
                        }

                        Text {
                            visible: testClassifierWindow.testResults !== null
                            text: "Test Accuracy: " + (testClassifierWindow.testResults ? (testClassifierWindow.testResults.test_accuracy * 100).toFixed(2) + "%" : "N/A")
                            font.pixelSize: 16
                            font.bold: true
                            color: "#333"
                        }

                        Text {
                            visible: testClassifierWindow.testResults !== null && testClassifierWindow.testResults.test_loss !== undefined
                            text: "Test Loss: " + (testClassifierWindow.testResults ? testClassifierWindow.testResults.test_loss.toFixed(4) : "N/A")
                            font.pixelSize: 14
                            color: "#555"
                        }

                        Text {
                            visible: testClassifierWindow.testResults !== null
                            text: "Test Samples: " + (testClassifierWindow.testResults ? testClassifierWindow.testResults.num_test_samples : "N/A")
                            font.pixelSize: 14
                            color: "#555"
                        }

                        Text {
                            visible: testClassifierWindow.testResults !== null
                            text: "Test Subjects: " + (testClassifierWindow.testResults ? testClassifierWindow.testResults.num_test_subjects : "N/A")
                            font.pixelSize: 14
                            color: "#555"
                        }

                        // Labels list
                        Text {
                            visible: testClassifierWindow.testResults && testClassifierWindow.testResults.class_accuracies
                            text: {
                                if (!(testClassifierWindow.testResults && testClassifierWindow.testResults.class_accuracies)) return "Labels: N/A"
                                var keys = Object.keys(testClassifierWindow.testResults.class_accuracies)
                                var labels = keys.map(function(k) {
                                    var parts = k.split("-")
                                    if (parts.length === 2) {
                                        return parts[1] + " " + parts[0]
                                    }
                                    return k
                                })
                                return "Labels: " + labels.join(", ")
                            }
                            font.pixelSize: 13
                            color: "#555"
                            wrapMode: Text.Wrap
                            width: parent.width - 10
                        }

                        // Group distribution
                        Text {
                            visible: testClassifierWindow.testResults && testClassifierWindow.testResults.group_counts
                            text: "Group Counts:" + (testClassifierWindow.testResults && testClassifierWindow.testResults.group_counts ? "" : " N/A")
                            font.pixelSize: 14
                            font.bold: true
                            color: "#333"
                        }

                        Column {
                            visible: testClassifierWindow.testResults && testClassifierWindow.testResults.group_counts
                            spacing: 4
                            Repeater {
                                model: testClassifierWindow.testResults && testClassifierWindow.testResults.group_counts ? Object.keys(testClassifierWindow.testResults.group_counts) : []
                                delegate: Text {
                                    text: "  " + modelData + ": " + testClassifierWindow.testResults.group_counts[modelData]
                                    font.pixelSize: 13
                                    color: "#555"
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width
                            height: 1
                            color: "#ddd"
                        }

                        Text {
                            text: "Per-Class Accuracy:"
                            font.pixelSize: 14
                            font.bold: true
                            color: "#333"
                        }

                        Column {
                            spacing: 5
                            Repeater {
                                model: testClassifierWindow.testResults ? Object.keys(testClassifierWindow.testResults.class_accuracies) : []
                                delegate: Text {
                                    text: "  " + modelData + ": " + (testClassifierWindow.testResults.class_accuracies[modelData] * 100).toFixed(2) + "%"
                                    font.pixelSize: 13
                                    color: "#555"
                                }
                            }
                        }
                    }
                }

                // Console output anchored to bottom
                Rectangle {
                    visible: testClassifierWindow.testLogs.length > 0
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#1e1e1e"
                    radius: 5

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 10
                        clip: true

                        Text {
                            text: testClassifierWindow.testLogs.join("\n")
                            color: "#d4d4d4"
                            font.family: "Consolas, Monaco, monospace"
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                            width: parent.width
                        }
                    }
                }
            }
        }
    }
}
