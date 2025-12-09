import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Controls.Basic 2.15
import QtQuick.Dialogs
import "."
import "../../../ui"
import "../../analysis/qml"

Item {
    id: preprocessingPageRoot
    anchors.fill: parent
    anchors.margins: 10  // Reduced margins for better space usage
    
    // Properties to communicate with main.qml
    property string currentFolder: ""
    property var folderContents: []
    property string fieldtripPath: ""
    property string saveMessage: ""
    property bool isProcessing: false  // Track processing state
    property bool showICABrowser: false  // Track ICA browser visibility
    property int customDropdownCount: 0
    property int customRangeSliderCount: 0

    // Dynamic parameters
    property var dynamicParameters: ({})
    property var dynamicValues: ({})

    Component.onCompleted: {
        var jsonStr = matlabExecutor.getModuleParameters("Preprocessing")
        try {
            var params = JSON.parse(jsonStr)
            
            // Set grey background for sliders in Preprocessing page
            for (var key in params) {
                if (params[key].component_type === 'RangeSliderTemplate') {
                    params[key].background_color = "#e0e0e0"
                }
            }
            dynamicParameters = params

            // Initialize dynamicValues
            var values = {}
            for (var key in dynamicParameters) {
                var config = dynamicParameters[key]
                if (config.component_type === 'RangeSliderTemplate') {
                    values[key] = [config.first_value, config.second_value]
                } else if (config.component_type === 'DropdownTemplate') {
                    if (config.is_multi_select) {
                        values[key] = config.selected_items || []
                    } else {
                        values[key] = config.model[config.current_index] || ""
                    }
                } else if (config.component_type === 'InputBoxTemplate') {
                    values[key] = config.text || ""
                } else if (config.component_type === 'CheckBoxTemplate') {
                    values[key] = config.checked || false
                }
            }
            dynamicValues = values

            // Sync selectedChannels with parsed accepted_channels
            if (dynamicParameters["accepted_channels"] && dynamicParameters["accepted_channels"].selected_items) {
                selectedChannels = dynamicParameters["accepted_channels"].selected_items
                console.log("Initialized selectedChannels from file:", selectedChannels)
            }
        } catch (e) {
            console.error("Failed to parse dynamic parameters:", e)
        }
    }
    
    // Function to initialize eventvalues from main.qml
    function setInitialEventvalues(eventvalues) {
        if (eventvalues && eventvalues.length > 0) {
            var params = JSON.parse(JSON.stringify(dynamicParameters))
            if (params["trialdef.eventvalue"]) {
                params["trialdef.eventvalue"].selected_items = eventvalues
                dynamicParameters = params
                
                var values = dynamicValues
                values["trialdef.eventvalue"] = eventvalues
                dynamicValues = values
            }
        }
    }
    
    // Function to initialize channels from main.qml
    function setInitialChannels(channels) {
        if (channels && channels.length > 0) {
            selectedChannels = channels
            
            // Update dynamic parameters if "accepted_channels" exists
            var params = JSON.parse(JSON.stringify(dynamicParameters))
            if (params["accepted_channels"]) {
                params["accepted_channels"].selected_items = channels
                dynamicParameters = params
                
                var values = dynamicValues
                values["accepted_channels"] = channels
                dynamicValues = values
            }
        }
    }
    
    // Function to initialize demean settings from main.qml
    function setInitialDemean(baselineWindow) {
        if (baselineWindow && baselineWindow.length >= 2) {
            var params = JSON.parse(JSON.stringify(dynamicParameters))
            if (params["baselinewindow"]) {
                params["baselinewindow"].first_value = baselineWindow[0]
                params["baselinewindow"].second_value = baselineWindow[1]
                dynamicParameters = params
                
                var values = dynamicValues
                values["baselinewindow"] = [baselineWindow[0], baselineWindow[1]]
                dynamicValues = values
            }
        }
    }
    
    // Function to initialize DFT filter settings from main.qml
    function setInitialDftfilter(dftfreq) {
        if (dftfreq && dftfreq.length >= 2) {
            var params = JSON.parse(JSON.stringify(dynamicParameters))
            if (params["dftfreq"]) {
                params["dftfreq"].first_value = dftfreq[0]
                params["dftfreq"].second_value = dftfreq[1]
                dynamicParameters = params
                
                var values = dynamicValues
                values["dftfreq"] = [dftfreq[0], dftfreq[1]]
                dynamicValues = values
            }
        }
    }

    Component {
        id: customDropdownComponent
        DropdownTemplate {
            label: customLabel
            hasAddFeature: true
            isMultiSelect: true
            maxSelections: -1
            model: []
            allItems: []
            selectedItems: []
            dropdownState: "add"
            matlabProperty: ""
            matlabPropertyDraft: ""
            addPlaceholder: "Add option..."

            property string customLabel: ""
            property string persistentId: ""
            property bool persistenceConnected: false

            anchors.left: parent ? parent.left : undefined
        }
    }

    Component {
        id: customRangeSliderComponent
        RangeSliderTemplate {
            label: customLabel
            matlabProperty: ""
            from: 0.0
            to: 1.0
            firstValue: 0.0
            secondValue: 1.0
            stepSize: 0.1
            unit: ""
            sliderState: "add"
            sliderId: ""
            matlabPropertyDraft: ""

            property string customLabel: ""
            property string persistentId: ""
            property bool persistenceConnected: false

            anchors.left: parent ? parent.left : undefined
        }
    }

    function persistCustomDropdown(dropdown) {
        if (!dropdown)
            return

        var propertyValue = dropdown.matlabProperty ? dropdown.matlabProperty.trim() : ""
        if (propertyValue.length === 0)
            return

        var labelValue = dropdown.label ? dropdown.label : (dropdown.customLabel ? dropdown.customLabel : "Custom Dropdown")
        labelValue = String(labelValue)

        var allItemsSnapshot = dropdown.allItems && dropdown.allItems.slice ? dropdown.allItems.slice(0) : (dropdown.allItems || [])
        var selectedItemsSnapshot = dropdown.selectedItems && dropdown.selectedItems.slice ? dropdown.selectedItems.slice(0) : (dropdown.selectedItems || [])
        var allItemsPayload = JSON.stringify(allItemsSnapshot)
        var selectedItemsPayload = JSON.stringify(selectedItemsSnapshot)

        if (dropdown.persistentId && dropdown.persistentId.length > 0) {
            matlabExecutor.updateCustomDropdown(dropdown.persistentId, labelValue, propertyValue, dropdown.isMultiSelect, dropdown.maxSelections, allItemsPayload, selectedItemsPayload)
        } else {
            var assignedId = matlabExecutor.saveCustomDropdown(labelValue, propertyValue, dropdown.isMultiSelect, dropdown.maxSelections, allItemsPayload, selectedItemsPayload)
            if (assignedId && assignedId.length > 0) {
                dropdown.persistentId = assignedId

                var match = assignedId.match(/(\d+)$/)
                if (match) {
                    var numericId = parseInt(match[1])
                    if (!isNaN(numericId)) {
                        preprocessingPageRoot.customDropdownCount = Math.max(preprocessingPageRoot.customDropdownCount, numericId)
                    }
                }
            }
        }
    }

    function persistCustomRangeSlider(rangeSlider) {
        if (!rangeSlider)
            return

        var propertyValue = rangeSlider.matlabProperty ? rangeSlider.matlabProperty.trim() : ""
        if (propertyValue.length === 0)
            return

        var labelValue = rangeSlider.label ? rangeSlider.label : (rangeSlider.customLabel ? rangeSlider.customLabel : "Custom Range Slider")
        labelValue = String(labelValue)

        if (rangeSlider.persistentId && rangeSlider.persistentId.length > 0) {
            matlabExecutor.updateCustomRangeSlider(rangeSlider.persistentId, labelValue, propertyValue, rangeSlider.from, rangeSlider.to, rangeSlider.firstValue, rangeSlider.secondValue, rangeSlider.stepSize, rangeSlider.unit)
        } else {
            var assignedId = matlabExecutor.saveCustomRangeSlider(labelValue, propertyValue, rangeSlider.from, rangeSlider.to, rangeSlider.firstValue, rangeSlider.secondValue, rangeSlider.stepSize, rangeSlider.unit)
            if (assignedId && assignedId.length > 0) {
                rangeSlider.persistentId = assignedId

                var match = assignedId.match(/(\d+)$/)
                if (match) {
                    var numericId = parseInt(match[1])
                    if (!isNaN(numericId)) {
                        preprocessingPageRoot.customRangeSliderCount = Math.max(preprocessingPageRoot.customRangeSliderCount, numericId)
                    }
                }
            }
        }
    }

    function applyEditModeToCustomDropdowns(newState) {
        for (var i = 0; i < customDropdownContainer.children.length; ++i) {
            var child = customDropdownContainer.children[i]
            if (!child)
                continue

            // Handle dropdowns
            if (child.dropdownState !== undefined) {
                if (child.dropdownState === "add")
                    continue

                if (child.dropdownState !== newState)
                    child.dropdownState = newState
            }
            // Handle range sliders
            else if (child.sliderState !== undefined) {
                if (child.sliderState === "add")
                    continue

                if (child.sliderState !== newState)
                    child.sliderState = newState
            }
        }
    }

    function attachCustomDropdownSignals(dropdown) {
        if (!dropdown || dropdown.persistenceConnected === true)
            return

        dropdown.persistenceConnected = true

        dropdown.propertySaveRequested.connect(function(propertyName, selectedValues, useCellFormat) {
            persistCustomDropdown(dropdown)
        })

        dropdown.addItem.connect(function() {
            persistCustomDropdown(dropdown)
        })

        dropdown.deleteItem.connect(function() {
            persistCustomDropdown(dropdown)
        })

        dropdown.multiSelectionChanged.connect(function() {
            persistCustomDropdown(dropdown)
        })

        dropdown.deleteRequested.connect(function() {
            if (dropdown.persistentId && dropdown.persistentId.length > 0) {
                matlabExecutor.removeCustomDropdown(dropdown.persistentId)
            }

            dropdown.destroy()

            var remainingHighest = 0
            for (var i = 0; i < customDropdownContainer.children.length; ++i) {
                var child = customDropdownContainer.children[i]
                if (!child || child === dropdown)
                    continue

                if (child.persistentId && child.persistentId.length > 0) {
                    var match = child.persistentId.match(/(\d+)$/)
                    if (match) {
                        var value = parseInt(match[1])
                        if (!isNaN(value)) {
                            remainingHighest = Math.max(remainingHighest, value)
                        }
                    }
                }
            }
            preprocessingPageRoot.customDropdownCount = Math.max(remainingHighest, Math.max(0, customDropdownContainer.children.length - 1))
        })

        dropdown.dropdownStateChanged.connect(function(newState) {
            if (newState === "add")
                return

            if (preprocessingPageRoot.editModeEnabled && newState === "default") {
                dropdown.dropdownState = "edit"
            } else if (!preprocessingPageRoot.editModeEnabled && newState === "edit") {
                dropdown.dropdownState = "default"
            }
        })

        if (preprocessingPageRoot.editModeEnabled && dropdown.dropdownState !== "add") {
            dropdown.dropdownState = "edit"
        }
    }

    function attachCustomRangeSliderSignals(rangeSlider) {
        if (!rangeSlider || rangeSlider.persistenceConnected === true)
            return

        rangeSlider.persistenceConnected = true

        rangeSlider.propertySaveRequested.connect(function(propertyName, firstValue, secondValue, unit) {
            persistCustomRangeSlider(rangeSlider)
        })

        rangeSlider.rangeChanged.connect(function(firstValue, secondValue) {
            persistCustomRangeSlider(rangeSlider)
        })

        rangeSlider.boundsChanged.connect(function(from, to) {
            persistCustomRangeSlider(rangeSlider)
        })

        rangeSlider.deleteRequested.connect(function() {
            if (rangeSlider.persistentId && rangeSlider.persistentId.length > 0) {
                matlabExecutor.removeCustomRangeSlider(rangeSlider.persistentId)
            }

            rangeSlider.destroy()

            var remainingHighest = 0
            for (var i = 0; i < customDropdownContainer.children.length; ++i) {
                var child = customDropdownContainer.children[i]
                if (!child || child === rangeSlider)
                    continue

                if (child.persistentId && child.persistentId.length > 0) {
                    var match = child.persistentId.match(/(\d+)$/)
                    if (match) {
                        var value = parseInt(match[1])
                        if (!isNaN(value)) {
                            remainingHighest = Math.max(remainingHighest, value)
                        }
                    }
                }
            }
            preprocessingPageRoot.customRangeSliderCount = Math.max(remainingHighest, Math.max(0, customDropdownContainer.children.length - 1))
        })

        rangeSlider.sliderStateChanged.connect(function(newState) {
            if (newState === "add")
                return

            if (preprocessingPageRoot.editModeEnabled && newState === "default") {
                rangeSlider.sliderState = "edit"
            } else if (!preprocessingPageRoot.editModeEnabled && newState === "edit") {
                rangeSlider.sliderState = "default"
            }
        })

        if (preprocessingPageRoot.editModeEnabled && rangeSlider.sliderState !== "add") {
            rangeSlider.sliderState = "edit"
        }
    }

    function addDropdownTemplate() {
        customDropdownCount += 1
        var labelText = "Custom Dropdown " + customDropdownCount
        var dropdown = customDropdownComponent.createObject(customDropdownContainer, {
            customLabel: labelText,
            label: labelText,
            dropdownState: "add",
            matlabProperty: "",
            matlabPropertyDraft: "",
            isMultiSelect: true,
            maxSelections: -1,
            persistentId: ""
        })

        if (!dropdown) {
            console.error("Failed to create custom dropdown template")
            customDropdownCount -= 1
            return
        }

        attachCustomDropdownSignals(dropdown)

        console.log("Added new dropdown template:", labelText)
    }

    function addRangeSliderTemplate() {
        customRangeSliderCount += 1
        var labelText = "Custom Range Slider " + customRangeSliderCount
        var rangeSlider = customRangeSliderComponent.createObject(customDropdownContainer, {
            customLabel: labelText,
            label: labelText,
            sliderState: "add",
            matlabProperty: "",
            matlabPropertyDraft: "",
            persistentId: ""
        })

        if (!rangeSlider) {
            console.error("Failed to create custom range slider template")
            customRangeSliderCount -= 1
            return
        }

        attachCustomRangeSliderSignals(rangeSlider)

        console.log("Added new range slider template:", labelText)
    }

    // Signals to communicate with main.qml
    signal openFolderDialog()
    signal openFieldtripDialog()
    signal createFunctionRequested()
    signal createScriptRequested()
    signal addDropdownRequested()
    signal addRangeSliderRequested()
    signal requestSaveConfiguration(real prestimValue, real poststimValue, string trialfunValue, string eventtypeValue, var selectedChannels, var selectedEventvalues, bool demeanEnabled, real baselineStart, real baselineEnd, bool dftfilterEnabled, real dftfreqStart, real dftfreqEnd)
    signal refreshFileExplorer()
    
    // Connection to handle processing completion
    Connections {
        target: matlabExecutor
        function onProcessingFinished() {
            preprocessingPageRoot.isProcessing = false
        }
    }
    
    // Property for backward compatibility with selectedChannels
    property var selectedChannels: ["F4", "Fz", "C3", "Pz", "P3", "O1", "Oz", "O2", "P4", "Cz", "C4"]
    property bool editModeEnabled: false  // Track edit mode state
    
    // JavaScript functions for channel selection
    function isChannelSelected(channel) {
        return selectedChannels.indexOf(channel) !== -1
    }

    function isAllSelected() {
        // return selectedChannels.length === channelDropdown.allItems.length
        return false // channelDropdown is removed
    }

    function toggleChannel(channel) {
        var index = selectedChannels.indexOf(channel)
        var newSelection = selectedChannels.slice() // Create a copy
        
        if (index !== -1) {
            // Remove channel
            newSelection.splice(index, 1)
        } else {
            // Add channel
            newSelection.push(channel)
        }
        
        selectedChannels = newSelection
    }

    function getSelectedChannelsText() {
        if (selectedChannels.length === 0) {
            return "None"
        } else {
            return selectedChannels.join(", ")
        }
    }

    function getSelectedChannelsCount() {
        return selectedChannels.length
    }

    // Function to handle edit mode toggle from TopMenu
    function setEditMode(editModeEnabled) {
        preprocessingPageRoot.editModeEnabled = editModeEnabled
        var newState = editModeEnabled ? "edit" : "default"
        
        // Update all dropdown states
        // channelDropdown.dropdownState = newState // Removed
        applyEditModeToCustomDropdowns(newState)
        
        console.log("Edit mode set to:", newState)
    }

    // Background area to close dropdown when clicking outside (removed MouseArea to fix scrolling)

    // File Explorer Rectangle - Using FileBrowserUI
    FileBrowserUI {
        id: fileExplorerRect
        

        // Connect signals if needed, though FileBrowserUI handles most logic internally

    }

    // Right side - Configuration Area with Scrolling (maximized space usage)
    Rectangle {
        anchors.left: fileExplorerRect.right
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 10  // Reduced from 20
        anchors.rightMargin: 5  // Reduced from 20 to push scrollbar right
        color: "transparent"
        
        // Scrollable content area - fills entire rectangle
        ScrollView {
            anchors.fill: parent
            clip: true
            contentWidth: mainColumn.width
            contentHeight: mainColumn.implicitHeight
            
            Column {
                id: mainColumn
                spacing: 10  // Reduced spacing for tighter layout
                // Match width of analysis page components: (PageWidth * 0.8 for module area) * (1/3 for component scale)
                width: Math.max(preprocessingPageRoot.width * 0.8 / 3, 250)
                anchors.horizontalCenter: parent.horizontalCenter
                
                Component.onCompleted: {
                    console.log("Fixed ScrollView - Column height:", height)
                    console.log("Fixed ScrollView - Available width:", width)
                }
            

                // Dynamic Parameters
                Repeater {
                    model: Object.keys(dynamicParameters)
                    delegate: DynamicParameterLoader {
                        width: mainColumn.width
                        parameterName: modelData
                        parameterConfig: dynamicParameters[modelData]
                        editModeEnabled: preprocessingPageRoot.editModeEnabled
                        contentWidthScale: 1.0
                        autoSaveEnabled: true
                        moduleName: "Preprocessing"

                        onParameterChanged: function(paramName, value) {
                            console.log("Parameter changed:", paramName, "=", value);
                            var newValues = dynamicValues
                            newValues[paramName] = value
                            dynamicValues = newValues
                            
                            // Special handling for accepted_channels to update selectedChannels
                            if (paramName === "accepted_channels") {
                                selectedChannels = value
                            }
                        }
                    }
                }

        Column {
            id: customDropdownContainer
            width: parent.width
            spacing: 10

            Component.onCompleted: {
                var highestIndex = 0
                for (var i = 0; i < customDropdownContainer.children.length; ++i) {
                    var child = customDropdownContainer.children[i]
                    if (!child)
                        continue

                    // Only attach dropdown signals to dropdown components
                    if (child.hasOwnProperty('propertySaveRequested') && child.hasOwnProperty('addItem')) {
                        attachCustomDropdownSignals(child)
                    } else if (child.hasOwnProperty('sliderState') && child.hasOwnProperty('rangeChanged')) {
                        attachCustomRangeSliderSignals(child)
                    }

                    if (child.persistentId && child.persistentId.length > 0) {
                        var match = child.persistentId.match(/(\d+)$/)
                        if (match) {
                            var numericValue = parseInt(match[1])
                            if (!isNaN(numericValue)) {
                                highestIndex = Math.max(highestIndex, numericValue)
                            }
                        }
                    }
                }

                if (customDropdownContainer.children.length > 0) {
                    highestIndex = Math.max(highestIndex, customDropdownContainer.children.length)
                }

                preprocessingPageRoot.customDropdownCount = Math.max(preprocessingPageRoot.customDropdownCount, highestIndex)
            }



}

        // Save confirmation message - Center using Item wrapper
        Item {
            width: parent.width
            height: saveConfirmationText.visible ? saveConfirmationText.height : 0
            
            Text {
                id: saveConfirmationText
                text: preprocessingPageRoot.saveMessage
                font.pixelSize: 12
                color: preprocessingPageRoot.saveMessage.includes("Error") ? "#d32f2f" : "#2e7d32"
                anchors.centerIn: parent
                visible: preprocessingPageRoot.saveMessage !== ""
            }
        }
                
            }  // End Column (mainColumn)
        }  // End ScrollView
    }  // End Rectangle

    // Helper function to save parameters
    function saveParameters() {
        console.log("Saving all preprocessing parameters...")
        var saveErrors = 0
        
        for (var key in dynamicValues) {
            var value = dynamicValues[key]
            var config = dynamicParameters[key]
            var success = false
            
            if (!config) continue
            
            // Skip baselinewindow if demean is disabled
            if (key === 'baselinewindow' && dynamicValues['demean'] === false) {
                console.log("Skipping baselinewindow (demean is disabled)")
                continue
            }
            
            if (config.component_type === 'RangeSliderTemplate') {
                // Handle range slider (including trial_time_window)
                success = matlabExecutor.saveRangeSliderPropertyToMatlab(
                    config.matlab_property, 
                    value[0], 
                    value[1], 
                    config.unit || "", 
                    "Preprocessing"
                )
            } else if (config.component_type === 'DropdownTemplate') {
                // Handle dropdowns (including accepted_channels)
                var needsCellFormat = config.is_multi_select && (config.max_selections !== 1)
                success = matlabExecutor.saveDropdownPropertyToMatlab(
                    config.matlab_property, 
                    value, 
                    needsCellFormat, 
                    "Preprocessing"
                )
            } else if (config.component_type === 'InputBoxTemplate') {
                success = matlabExecutor.saveInputPropertyToMatlab(
                    config.matlab_property,
                    value,
                    config.is_numeric || false,
                    "Preprocessing"
                )
            } else if (config.component_type === 'CheckBoxTemplate') {
                success = matlabExecutor.saveCheckboxPropertyToMatlab(
                    config.matlab_property,
                    value,
                    "Preprocessing"
                )
            }
            
            if (success) {
                console.log("Successfully saved parameter: " + key)
            } else {
                console.error("Failed to save parameter: " + key)
                saveErrors++
            }
        }
        
        if (saveErrors > 0) {
            console.warn("Warning: " + saveErrors + " parameters failed to save.")
            preprocessingPageRoot.saveMessage = "Warning: " + saveErrors + " parameters failed to save."
        } else {
            console.log("All parameters saved successfully.")
            preprocessingPageRoot.saveMessage = "All parameters saved successfully."
        }
        
        // Clear message after 3 seconds
        saveTimer.restart()
    }

    // Helper function to run the pipeline
    function runPipeline() {
        preprocessingPageRoot.isProcessing = true
        
        // Save parameters first
        saveParameters()

        console.log("Running preprocessing and ICA:")
        console.log("data path =", preprocessingPageRoot.currentFolder)
        
        // Update data directory and execute
        matlabExecutor.updateDataDirectory(preprocessingPageRoot.currentFolder)
        matlabExecutor.executePreprocessing()
    }
    
    Timer {
        id: saveTimer
        interval: 3000
        onTriggered: preprocessingPageRoot.saveMessage = ""
    }

    // Action Button - Top Right
    Rectangle {
        id: actionButton
        width: 200
        height: 50
        color: enabled ? "#2196f3" : "#888888"
        radius: 5
        
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 20
        anchors.rightMargin: 20
        
        z: 1000
        enabled: !preprocessingPageRoot.isProcessing

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            
            Rectangle {
                anchors.fill: parent
                color: parent.pressed ? "#1565c0" : (parent.containsMouse ? "#1976d2" : "transparent")
                radius: 5
            }

            Text {
                text: preprocessingPageRoot.isProcessing ? "Processing..." : "Preprocess and Run ICA"
                color: "white"
                font.pixelSize: 14
                anchors.centerIn: parent
            }
            
            onClicked: {
                preprocessingPageRoot.runPipeline()
            }
        }
    }
}  // End Item (preprocessingPageRoot)