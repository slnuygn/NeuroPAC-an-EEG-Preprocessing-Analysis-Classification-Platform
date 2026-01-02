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
    property string resultsFolder: ""  // Store path to results folder after classification
    
    // Classification class selection properties
    property var availableClasses: []  // Store available classes/labels for selected analysis
    property var selectedClasses: ({})  // Store selected classes as {className: true/false}
    property bool classifyMenuExpanded: false  // Track if classify dropdown is expanded
    
    // Time window properties
    property real timeWindowStart: -0.2
    property real timeWindowEnd: 1.0
    property real timeWindowMin: -1.0  // Dynamic minimum based on analysis
    property real timeWindowMax: 2.0   // Dynamic maximum based on analysis
    property var analysisTimeSelections: ({})  // Per-classifier + analysis selected ranges
    property bool timeWindowProgrammaticUpdate: false  // Skip persistence while we sync from disk
    
    // Format: [defaultStart, defaultEnd, minBound, maxBound]
    property var analysisTimeRanges: ({
        "ERP Analysis": [-0.2, 1.0, -1.0, 2.0],
        "Spectral Analysis": [0, 1.0, -0.5, 3.0],
        "Time-Frequency Analysis": [-0.2, 1.0, -2.0, 2.0],
        "Intertrial Coherence Analysis": [-0.2, 1.0, -1.0, 2.0],
        "Channel-Wise Connectivity Analysis": [0, 1.0, -0.5, 3.0]
    })

    Component.onCompleted: loadPersistedTimeSelections()

    function loadPersistedTimeSelections() {
        try {
            var saved = classificationController.loadTimeWindowSelections()
            if (saved && saved.length > 0) {
                var parsed = JSON.parse(saved)
                if (parsed && typeof parsed === "object") {
                    analysisTimeSelections = parsed
                }
            }
        } catch (e) {
            console.error("Failed to load time window selections:", e)
        }
    }

    function getSavedRangeFor(analysisName) {
        var cleanName = analysisName ? analysisName.trim() : ""
        var key = classifierName + "::" + cleanName
        if (analysisTimeSelections && analysisTimeSelections.hasOwnProperty(key)) {
            return analysisTimeSelections[key]
        }
        // Try trimmed key
        var trimmedKey = key.trim()
        if (analysisTimeSelections && analysisTimeSelections.hasOwnProperty(trimmedKey)) {
            return analysisTimeSelections[trimmedKey]
        }
        // Try raw analysisName without classifier prefix
        if (analysisTimeSelections && analysisTimeSelections.hasOwnProperty(cleanName)) {
            return analysisTimeSelections[cleanName]
        }
        // Last resort: case/whitespace-insensitive scan of all keys
        if (analysisTimeSelections) {
            var target = (classifierName + "::" + cleanName).toLowerCase().replace(/\s+/g, " ").trim()
            var ks = Object.keys(analysisTimeSelections)
            for (var i = 0; i < ks.length; i++) {
                var candidate = ks[i]
                var normalized = candidate.toLowerCase().replace(/\s+/g, " ").trim()
                if (normalized === target) {
                    return analysisTimeSelections[candidate]
                }
                // Also allow matching just analysis name
                var parts = normalized.split("::")
                if (parts.length === 2) {
                    var anaOnly = parts[1]
                    if (anaOnly === cleanName.toLowerCase().replace(/\s+/g, " ").trim()) {
                        return analysisTimeSelections[candidate]
                    }
                }
            }
        }
        return null
    }

    function normalizeKey(cls, ana) {
        var c = cls ? cls.toString() : ""
        var a = ana ? ana.toString() : ""
        return (c + "::" + a)
            .toLowerCase()
            .replace(/[_\s]+/g, " ")
            .trim()
    }

    function findExistingKeyFor(cls, ana) {
        if (!analysisTimeSelections) return null
        var target = normalizeKey(cls, ana)
        var ks = Object.keys(analysisTimeSelections)
        for (var i = 0; i < ks.length; i++) {
            var candidate = ks[i]
            var norm = candidate.toLowerCase().replace(/[_\s]+/g, " ").trim()
            if (norm === target) {
                return candidate
            }
        }
        return null
    }

    function applyTimeWindowRange(start, end) {
        // Update slider values without persisting back to disk
        timeWindowProgrammaticUpdate = true
        timeWindowStart = Number(start)
        timeWindowEnd = Number(end)
        if (timeWindowSlider) {
            timeWindowSlider.firstValue = timeWindowStart
            timeWindowSlider.secondValue = timeWindowEnd
        }
        Qt.callLater(function() { timeWindowProgrammaticUpdate = false })
    }

    function savePersistedTimeSelections() {
        try {
            classificationController.saveTimeWindowSelections(JSON.stringify(analysisTimeSelections))
        } catch (e) {
            console.error("Failed to save time window selections:", e)
        }
    }
    
    signal classifyClicked(string classifierName, string analysisName, var selectedClasses, var configParams)
    signal testClassifierClicked(string classifierName, string analysisName, string weightsPath)
    signal classificationComplete(string resultsFolder)  // Emitted when classification finishes
    
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

        // Build expected filename pattern: ClassifierName_<key>_*_weights_best.keras
        // The * can match group names (e.g., gPD_CTL) or nothing for backward compatibility
        var patternStart = (classifierName + "_" + analysisKey).toLowerCase()
        var patternEnd = "_weights_best.keras".toLowerCase()
        
        for (var i = 0; i < currentFolderContents.length; i++) {
            var fileName = currentFolderContents[i]
            // Remove any leading emoji/symbols for comparison
            var cleanFileName = fileName.replace(/^[^\w]+/, '').toLowerCase()
            
            // Check if filename matches the pattern: classifier_analysis[_ggroups]_weights_best.keras
            if (cleanFileName.startsWith(patternStart) && cleanFileName.endsWith(patternEnd)) {
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

            var patternStart = (classifierName + "_" + key).toLowerCase()
            var patternEnd = "_weights_best.keras".toLowerCase()
            for (var i = 0; i < currentFolderContents.length; i++) {
                var fileName = currentFolderContents[i]
                var cleanFileName = fileName.replace(/^[^\w]+/, '').toLowerCase()
                if (cleanFileName.startsWith(patternStart) && cleanFileName.endsWith(patternEnd)) {
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
        if (!currentFolderPath || !currentFolderContents) return ""
        
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
        
        // Find the weights file that matches the pattern: classifier_analysis[_ggroups]_weights_best.keras
        var patternStart = (classifierName + "_" + analysisKey).toLowerCase()
        var patternEnd = "_weights_best.keras".toLowerCase()
        
        for (var i = 0; i < currentFolderContents.length; i++) {
            var fileName = currentFolderContents[i]
            var cleanFileName = fileName.replace(/^[^\w]+/, '').toLowerCase()
            
            if (cleanFileName.startsWith(patternStart) && cleanFileName.endsWith(patternEnd)) {
                return currentFolderPath + "/" + fileName
            }
        }
        return ""
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
        
        // Reload persisted time selections to get latest values from JSON file
        loadPersistedTimeSelections();
        
        // Load available classes for this analysis
        loadAvailableClasses();
        
        try {
            var jsonStr = classificationController.getParamsForAnalysis(classifierName, analysisName);
            var params = JSON.parse(jsonStr);
            configParameters = params;
            
            // Set time window using saved selection per classifier+analysis; fallback to defaults
            var cleanName = analysisName ? analysisName.trim() : "";
            var defaultRange = analysisTimeRanges[cleanName] || [-0.2, 1.0, -1.0, 2.0];
            var existingKey = findExistingKeyFor(classifierName, cleanName)
            var timeKey = existingKey ? existingKey : (classifierName + "::" + cleanName);
            var savedRange = getSavedRangeFor(cleanName);

            timeWindowMin = defaultRange[2];
            timeWindowMax = defaultRange[3];

            if (savedRange && savedRange.length === 2) {
                applyTimeWindowRange(savedRange[0], savedRange[1]);
                analysisTimeSelections[timeKey] = [Number(savedRange[0]), Number(savedRange[1])];
                console.log("Loaded persisted time window for " + timeKey + ": [" + timeWindowStart + ", " + timeWindowEnd + "]");
            } else {
                applyTimeWindowRange(defaultRange[0], defaultRange[1]);
                analysisTimeSelections[timeKey] = [Number(defaultRange[0]), Number(defaultRange[1])];
                console.log("No persisted time window for " + timeKey + ", using defaults (not persisted) : [" + timeWindowStart + ", " + timeWindowEnd + "]");
            }
            
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

    function loadAvailableClasses() {
        if (!classifierName || !selectedAnalysis) {
            availableClasses = [];
            selectedClasses = ({});
            return;
        }
        
        try {
            // Check if the function exists before calling
            if (typeof classificationController.getClassesForAnalysis === 'function') {
                var jsonStr = classificationController.getClassesForAnalysis(classifierName, selectedAnalysis);
                var classes = JSON.parse(jsonStr);
                availableClasses = classes;
                
                // Initialize selectedClasses with all classes selected by default
                var selected = ({});
                for (var i = 0; i < classes.length; i++) {
                    selected[classes[i]] = true;
                }
                selectedClasses = selected;
                console.log("Available classes for " + selectedAnalysis + ":", availableClasses);
            } else {
                // Function doesn't exist yet, use empty array
                console.log("getClassesForAnalysis not available yet, skipping class loading");
                availableClasses = [];
                selectedClasses = ({});
            }
        } catch (e) {
            console.error("Failed to load available classes for " + selectedAnalysis + ":", e);
            availableClasses = [];
            selectedClasses = ({});
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

            // Time Window Range Slider - visible when analysis is selected
            RangeSliderTemplate {
                id: timeWindowSlider
                visible: selectedAnalysis !== ""
                width: contentContainer.width / 3
                label: "Time Window"
                matlabProperty: "cfg.time_window"
                from: timeWindowMin
                to: timeWindowMax
                firstValue: timeWindowStart
                secondValue: timeWindowEnd
                stepSize: 0.01
                unit: "s"
                enabled: true
                backgroundColor: "#ffffff"
                
                // Force slider to sync when it becomes visible
                onVisibleChanged: {
                    if (visible) {
                        applyTimeWindowRange(timeWindowStart, timeWindowEnd)
                    }
                }
                
                onRangeChanged: function(firstVal, secondVal) {
                    timeWindowStart = firstVal
                    timeWindowEnd = secondVal
                    if (timeWindowProgrammaticUpdate) {
                        return
                    }
                    if (selectedAnalysis && selectedAnalysis !== "") {
                        var existing = findExistingKeyFor(classifierName, selectedAnalysis)
                        var timeKey = existing ? existing : (classifierName + "::" + selectedAnalysis)
                        analysisTimeSelections[timeKey] = [firstVal, secondVal]
                        savePersistedTimeSelections()
                    }
                    console.log("Time window changed:", firstVal, "to", secondVal)
                }
                
                onBoundsChanged: function(minVal, maxVal) {
                    timeWindowMin = minVal
                    timeWindowMax = maxVal
                    console.log("Time window bounds changed:", minVal, "to", maxVal)
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
                        try {
                            if (isNumeric) {
                                // Check if original value was an integer
                                var originalValue = configParameters[modelData];
                                if (Number.isInteger(originalValue)) {
                                    configParameters[modelData] = parseInt(newValue);
                                } else {
                                    configParameters[modelData] = parseFloat(newValue);
                                }
                            } else {
                                try {
                                    configParameters[modelData] = JSON.parse(newValue);
                                } catch (e) {
                                    configParameters[modelData] = newValue;
                                }
                            }
                            console.log("Updated " + modelData + " to:", configParameters[modelData]);
                            
                            // Save configuration immediately to JSON file
                            if (classifierName && selectedAnalysis) {
                                var saved = classificationController.saveConfiguration(classifierName, selectedAnalysis, configParameters);
                                if (saved) {
                                    console.log("Configuration saved to file");
                                } else {
                                    console.error("Failed to save configuration");
                                }
                            }
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

            // Test Classifier Button disabled per request
            Rectangle {
                id: testClassifierButton
                visible: false
                enabled: false
                width: 0
                height: 0
                color: "transparent"
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

            // Floating Action Buttons - anchored to contentContainer bottom right
            Row {
                anchors.right: parent.right
                spacing: 5

                // Select Time Range Button
                Rectangle {
                    id: selectTimeRangeButton
                    width: 150
                    height: 40
                    visible: selectedAnalysis !== ""
                    color: "#2196f3"
                    radius: 5

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
                            text: "Select Time Range"
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
                            expanded = true

                            // Kick off MATLAB time range selection for this classifier/analysis
                            if (typeof matlabExecutor !== "undefined" && matlabExecutor) {
                                var folderPath = currentFolderPath || ""
                                var startMsg = "[" + new Date().toLocaleTimeString() + "] Applying time window for " + selectedAnalysis + "..."
                                classifyLogs.push(startMsg)
                                classifyLogs = classifyLogs.slice()
                                matlabExecutor.runSelectTimeRange(classifierName, selectedAnalysis, folderPath)
                            } else {
                                classifyLogs.push("[" + new Date().toLocaleTimeString() + "] matlabExecutor not available; cannot apply time window.")
                                classifyLogs = classifyLogs.slice()
                            }
                        }
                    }
                }

                // Classify Button - Dropdown with Class Selection
                Item {
                    id: classifyButtonContainer
                    width: 150
                    height: 40
                    
                    // Dropdown popup menu
                    Rectangle {
                        id: classifyDropdownMenu
                        visible: classifyMenuExpanded
                        width: 250
                        height: classifyMenuContent.implicitHeight + 20
                        color: "white"
                        border.color: "#e0e0e0"
                        border.width: 1
                        radius: 5
                        z: 1001
                        
                        anchors.bottom: classifyButton.top
                        anchors.bottomMargin: 5
                        anchors.right: classifyButton.right
                        
                        Column {
                            id: classifyMenuContent
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 2
                            
                            Text {
                                text: "Select Classes to Classify:"
                                font.pixelSize: 12
                                font.bold: true
                                color: "#333"
                            }
                            
                            Repeater {
                                model: availableClasses
                                delegate: Rectangle {
                                    width: parent.width
                                    height: 25
                                    color: "transparent"
                                    
                                    Row {
                                        anchors.fill: parent
                                        anchors.leftMargin: 5
                                        spacing: 8
                                            
                                            // Custom checkbox
                                            Rectangle {
                                                id: customCheckbox
                                                width: 15
                                                height: 15
                                                anchors.verticalCenter: parent.verticalCenter
                                                border.color: "#666"
                                                border.width: 1
                                                color: (selectedClasses[modelData] !== undefined ? selectedClasses[modelData] : true) ? "#2196f3" : "white"
                                                
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "✓"
                                                    color: "white"
                                                    font.pixelSize: 10
                                                    visible: selectedClasses[modelData] !== undefined ? selectedClasses[modelData] : true
                                                }
                                                
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    
                                                    onClicked: {
                                                        var currentState = selectedClasses[modelData] !== undefined ? selectedClasses[modelData] : true
                                                        var updated = {}
                                                        // Copy existing values
                                                        for (var key in selectedClasses) {
                                                            updated[key] = selectedClasses[key]
                                                        }
                                                        // Toggle the clicked item
                                                        updated[modelData] = !currentState
                                                        selectedClasses = updated
                                                        console.log("Toggled " + modelData + " to " + updated[modelData])
                                                    }
                                                }
                                            }
                                            
                                            Text {
                                                text: modelData
                                                font.pixelSize: 13
                                                color: "#333"
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: parent.width - customCheckbox.width - 15
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    
                    // Classify button with two sections
                    Rectangle {
                        id: classifyButton
                        width: 150
                        height: 40
                        color: "transparent"
                        radius: 5
                        anchors.bottom: parent.bottom
                        anchors.right: parent.right
                        
                        Row {
                            anchors.fill: parent
                            spacing: 0
                            
                            // Left section - Classify text
                            Rectangle {
                                id: classifySection
                                width: parent.width - 40
                                height: parent.height
                                color: "#2196f3"
                                radius: 5
                                
                                Rectangle {
                                    anchors.right: parent.right
                                    width: 5
                                    height: parent.height
                                    color: "#2196f3"
                                }
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Classify"
                                    color: "white"
                                    font.pixelSize: 14
                                }
                                
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    
                                    onPressed: classifySection.color = "#1565c0"
                                    onReleased: classifySection.color = "#2196f3"
                                    onEntered: classifySection.color = "#1976d2"
                                    onExited: classifySection.color = "#2196f3"
                                    
                                    onClicked: {
                                        if (selectedAnalysis === "") {
                                            errorTextItem.text = "Please select an analysis type first"
                                            return
                                        }
                                        
                                        errorTextItem.text = ""
                                        
                                        // Get selected classes
                                        var selectedList = []
                                        for (var cls in selectedClasses) {
                                            if (selectedClasses[cls]) {
                                                selectedList.push(cls)
                                            }
                                        }
                                        
                                        if (selectedList.length === 0) {
                                            errorTextItem.text = "Please select at least one class"
                                            return
                                        }
                                        
                                        // Close the menu if open
                                        classifyMenuExpanded = false
                                        
                                        // Clear previous logs and mark as executed
                                        classifyLogs = []
                                        classifyExecuted = true
                                        
                                        // Add initial log
                                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Starting classification...")
                                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Classifier: " + classifierName)
                                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Analysis: " + selectedAnalysis)
                                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Selected Classes: " + selectedList.join(", "))
                                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Parameters: " + JSON.stringify(configParameters))
                                        
                                        classifierTemplate.classifyClicked(classifierName, selectedAnalysis, selectedList, configParameters)
                                        
                                        // Add completion log
                                        classifyLogs.push("[" + new Date().toLocaleTimeString() + "] Classification request sent")
                                    }
                                }
                            }
                            
                            // Separator line
                            Rectangle {
                                width: 1
                                height: parent.height
                                color: "white"
                                opacity: 0.5
                            }
                            
                            // Right section - Arrow dropdown
                            Rectangle {
                                id: arrowSection
                                width: 39
                                height: parent.height
                                color: "#2196f3"
                                radius: 5
                                
                                Rectangle {
                                    anchors.left: parent.left
                                    width: 5
                                    height: parent.height
                                    color: "#2196f3"
                                }
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: classifyMenuExpanded ? "▼" : "▲"
                                    color: "white"
                                    font.pixelSize: 10
                                }
                                
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    
                                    onPressed: arrowSection.color = "#1565c0"
                                    onReleased: arrowSection.color = "#2196f3"
                                    onEntered: arrowSection.color = "#1976d2"
                                    onExited: arrowSection.color = "#2196f3"
                                    
                                    onClicked: {
                                        classifyMenuExpanded = !classifyMenuExpanded
                                    }
                                }
                            }
                        }
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
        width: 700
        height: 550
        minimumWidth: 500
        minimumHeight: 350

        Rectangle {
            anchors.fill: parent
            color: "#1e1e1e"
            
            Column {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 0
                
                // Results notification banner disabled per request
                Rectangle {
                    id: resultsNotification
                    visible: false
                    width: parent.width
                    height: 0
                    color: "transparent"
                }

                ScrollView {
                    id: consoleScrollView
                    width: parent.width
                    height: parent.height - resultsNotification.height
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
                        padding: 10
                    }
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
        property bool isLoading: false  // Loading samples
        property bool isPredicting: false  // Running prediction
        property var testLogs: []
        property var availableSamples: []  // List of sample objects {index, name, label, group}
        property int selectedSampleIndex: -1  // Index of selected sample in availableSamples
        property var predictionResult: null  // Result from classification

        // Connection to receive loaded samples
        Connections {
            target: classificationController
            function onSamplesLoaded(jsonSamples) {
                if (!testClassifierWindow.visible) return
                
                try {
                    var samples = JSON.parse(jsonSamples)
                    testClassifierWindow.availableSamples = samples
                    testClassifierWindow.isLoading = false
                    testClassifierWindow.selectedSampleIndex = -1
                    testClassifierWindow.predictionResult = null
                    console.log("Samples loaded:", samples.length)
                } catch (e) {
                    console.error("Failed to parse samples:", e)
                    testClassifierWindow.isLoading = false
                }
            }
            
            function onSingleSampleResult(jsonResult) {
                if (!testClassifierWindow.visible) return
                
                try {
                    testClassifierWindow.predictionResult = JSON.parse(jsonResult)
                    testClassifierWindow.isPredicting = false
                    console.log("Prediction result received")
                } catch (e) {
                    console.error("Failed to parse prediction result:", e)
                    testClassifierWindow.isPredicting = false
                }
            }
            
            function onLogReceived(message) {
                if (testClassifierWindow.isLoading || testClassifierWindow.isPredicting) {
                    testClassifierWindow.testLogs.push("[" + new Date().toLocaleTimeString() + "] " + message)
                    testClassifierWindow.testLogs = testClassifierWindow.testLogs.slice()
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            color: "#f0f0f0"

            ScrollView {
                id: testClassifierScrollView
                anchors.fill: parent
                clip: true
                contentWidth: availableWidth
                
                ScrollBar.horizontal: ScrollBar {
                    policy: ScrollBar.AlwaysOff
                }

                Column {
                    width: testClassifierScrollView.availableWidth
                    spacing: 15
                    padding: 20

                    // Header
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

                    // Loading indicator
                    Rectangle {
                        visible: testClassifierWindow.isLoading
                        width: parent.width - 40
                        height: 50
                        color: "white"
                        border.color: "#e0e0e0"
                        border.width: 1
                        radius: 5

                        Row {
                            anchors.centerIn: parent
                            spacing: 10

                            Text {
                                text: "Loading test samples..."
                                font.pixelSize: 14
                                color: "#666"
                            }
                        }
                    }

                    // Sample Selection Section (shown after samples are loaded)
                    Rectangle {
                        visible: testClassifierWindow.availableSamples.length > 0
                        width: parent.width - 40
                        height: selectSampleContent.implicitHeight + 30
                        color: "white"
                        border.color: "#e0e0e0"
                        border.width: 1
                        radius: 5

                        Column {
                            id: selectSampleContent
                            anchors.fill: parent
                            anchors.margins: 15
                            spacing: 10

                            Row {
                                spacing: 10
                                Text {
                                    text: "Select a Test Sample"
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: "#333"
                                }
                                Text {
                                    text: "(" + testClassifierWindow.availableSamples.length + " samples)"
                                    font.pixelSize: 12
                                    color: "#4caf50"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            Text {
                                text: "Choose a sample from the test set to predict. Labels are hidden until prediction."
                                font.pixelSize: 12
                                color: "#666"
                                wrapMode: Text.Wrap
                                width: parent.width - 10
                            }

                            // Dropdown for sample selection (without labels)
                            DropdownTemplate {
                                id: sampleSelectionDropdown
                                width: Math.min(parent.width - 20, 400)
                                label: ""
                                matlabProperty: ""
                                model: {
                                    var names = []
                                    for (var i = 0; i < testClassifierWindow.availableSamples.length; i++) {
                                        var sample = testClassifierWindow.availableSamples[i]
                                        // Show only sample number and name - NO LABEL
                                        names.push((i + 1) + ": " + (sample.name || "Sample " + (i + 1)))
                                    }
                                    return names
                                }
                                currentIndex: testClassifierWindow.selectedSampleIndex >= 0 ? testClassifierWindow.selectedSampleIndex : 0
                                showCheckboxes: false
                                isMultiSelect: false
                                hasAddFeature: false

                                onSelectionChanged: function(value, index) {
                                    testClassifierWindow.selectedSampleIndex = index
                                    testClassifierWindow.predictionResult = null  // Clear previous result
                                    console.log("Selected sample index:", index)
                                }
                            }

                            // Show group info if available (but not the label!)
                            Text {
                                visible: testClassifierWindow.selectedSampleIndex >= 0 && testClassifierWindow.availableSamples[testClassifierWindow.selectedSampleIndex]
                                text: {
                                    if (testClassifierWindow.selectedSampleIndex < 0) return ""
                                    var sample = testClassifierWindow.availableSamples[testClassifierWindow.selectedSampleIndex]
                                    if (!sample) return ""
                                    var info = "Group: " + (sample.group || "Unknown")
                                    return info
                                }
                                font.pixelSize: 11
                                color: "#888"
                            }
                        }
                    }

                    // Predict Button
                    Rectangle {
                        visible: testClassifierWindow.availableSamples.length > 0 && testClassifierWindow.selectedSampleIndex >= 0
                        width: 160
                        height: 44
                        color: testClassifierWindow.isPredicting ? "#ccc" : "#2196f3"
                        radius: 5

                        MouseArea {
                            anchors.fill: parent
                            enabled: !testClassifierWindow.isPredicting && testClassifierWindow.selectedSampleIndex >= 0
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                testClassifierWindow.isPredicting = true
                                testClassifierWindow.predictionResult = null
                                var sampleData = testClassifierWindow.availableSamples[testClassifierWindow.selectedSampleIndex]
                                classificationController.classifySingleSample(
                                    testClassifierWindow.classifierName,
                                    testClassifierWindow.selectedAnalysis,
                                    testClassifierWindow.weightsPath,
                                    sampleData.index  // Use actual sample index from data
                                )
                            }
                        }

                        Text {
                            text: testClassifierWindow.isPredicting ? "Predicting..." : "Predict"
                            color: "white"
                            font.pixelSize: 15
                            font.bold: true
                            anchors.centerIn: parent
                        }
                    }

                    // Prediction Result Display
                    Rectangle {
                        visible: testClassifierWindow.predictionResult !== null
                        width: parent.width - 40
                        height: predictionResultContent.implicitHeight + 30
                        color: testClassifierWindow.predictionResult && testClassifierWindow.predictionResult.is_correct ? "#e8f5e9" : "#ffebee"
                        border.color: testClassifierWindow.predictionResult && testClassifierWindow.predictionResult.is_correct ? "#4caf50" : "#f44336"
                        border.width: 2
                        radius: 5

                        Column {
                            id: predictionResultContent
                            anchors.fill: parent
                            anchors.margins: 15
                            spacing: 12

                            // Header
                            Text {
                                text: "🎯 Prediction Result"
                                font.pixelSize: 16
                                font.bold: true
                                color: "#333"
                            }

                            Rectangle {
                                width: parent.width
                                height: 1
                                color: "#ddd"
                            }

                            // Sample info
                            Text {
                                text: "Sample: " + (testClassifierWindow.predictionResult ? testClassifierWindow.predictionResult.sample_name : "")
                                font.pixelSize: 13
                                color: "#555"
                                wrapMode: Text.Wrap
                                width: parent.width
                            }

                            // Main result - Predicted vs Actual
                            Row {
                                spacing: 30
                                
                                Column {
                                    spacing: 4
                                    Text {
                                        text: "PREDICTED"
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: "#1565c0"
                                    }
                                    Rectangle {
                                        width: 120
                                        height: 40
                                        color: "#e3f2fd"
                                        border.color: "#1565c0"
                                        border.width: 2
                                        radius: 5
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: testClassifierWindow.predictionResult ? testClassifierWindow.predictionResult.predicted_label : ""
                                            font.pixelSize: 18
                                            font.bold: true
                                            color: "#1565c0"
                                        }
                                    }
                                }
                                
                                Text {
                                    text: "→"
                                    font.pixelSize: 28
                                    color: "#999"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                
                                Column {
                                    spacing: 4
                                    Text {
                                        text: "ACTUAL"
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: "#2e7d32"
                                    }
                                    Rectangle {
                                        width: 120
                                        height: 40
                                        color: "#e8f5e9"
                                        border.color: "#2e7d32"
                                        border.width: 2
                                        radius: 5
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: testClassifierWindow.predictionResult ? testClassifierWindow.predictionResult.actual_label : ""
                                            font.pixelSize: 18
                                            font.bold: true
                                            color: "#2e7d32"
                                        }
                                    }
                                }
                            }

                            // Result indicator
                            Rectangle {
                                width: parent.width
                                height: 36
                                color: testClassifierWindow.predictionResult && testClassifierWindow.predictionResult.is_correct ? "#c8e6c9" : "#ffcdd2"
                                radius: 5
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: testClassifierWindow.predictionResult && testClassifierWindow.predictionResult.is_correct ? "✓ CORRECT PREDICTION" : "✗ INCORRECT PREDICTION"
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: testClassifierWindow.predictionResult && testClassifierWindow.predictionResult.is_correct ? "#2e7d32" : "#c62828"
                                }
                            }

                            // Confidence score
                            Text {
                                text: "Confidence: " + (testClassifierWindow.predictionResult ? (testClassifierWindow.predictionResult.confidence * 100).toFixed(1) : "0") + "%"
                                font.pixelSize: 13
                                color: "#555"
                            }

                            // Class probabilities
                            Rectangle {
                                width: parent.width
                                height: 1
                                color: "#ddd"
                            }

                            Text {
                                text: "Class Probabilities:"
                                font.pixelSize: 12
                                font.bold: true
                                color: "#555"
                            }

                            Column {
                                spacing: 6
                                width: parent.width
                                
                                Repeater {
                                    model: testClassifierWindow.predictionResult && testClassifierWindow.predictionResult.probabilities ? Object.keys(testClassifierWindow.predictionResult.probabilities) : []
                                    delegate: Row {
                                        spacing: 10
                                        width: parent.width
                                        
                                        Text {
                                            text: modelData + ":"
                                            font.pixelSize: 12
                                            color: "#555"
                                            width: 80
                                        }
                                        Rectangle {
                                            width: 150
                                            height: 16
                                            color: "#e0e0e0"
                                            radius: 3
                                            
                                            Rectangle {
                                                width: parent.width * (testClassifierWindow.predictionResult.probabilities[modelData] || 0)
                                                height: parent.height
                                                color: modelData === testClassifierWindow.predictionResult.predicted_label ? "#2196f3" : "#90caf9"
                                                radius: 3
                                            }
                                        }
                                        Text {
                                            text: ((testClassifierWindow.predictionResult.probabilities[modelData] || 0) * 100).toFixed(1) + "%"
                                            font.pixelSize: 11
                                            color: "#666"
                                            width: 50
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Console output
                    Rectangle {
                        visible: testClassifierWindow.testLogs.length > 0
                        width: parent.width - 40
                        height: Math.min(240, testClassifierWindow.testLogs.length * 14 + 20)
                        color: "#1e1e1e"
                        radius: 5

                        ScrollView {
                            id: testConsoleScrollView
                            anchors.fill: parent
                            anchors.margins: 10
                            clip: true

                            Text {
                                id: testConsoleText
                                text: testClassifierWindow.testLogs.join("\n")
                                color: "#d4d4d4"
                                font.family: "Consolas, Monaco, monospace"
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                width: testConsoleScrollView.availableWidth
                                
                                onTextChanged: {
                                    // Auto-scroll to bottom when new text is added
                                    Qt.callLater(function() {
                                        if (testConsoleScrollView && testConsoleScrollView.ScrollBar.vertical) {
                                            testConsoleScrollView.ScrollBar.vertical.position = 1.0 - testConsoleScrollView.ScrollBar.vertical.size
                                        }
                                    })
                                }
                            }
                        }
                    }
                }
            }  // End ScrollView
        }
    }
}
