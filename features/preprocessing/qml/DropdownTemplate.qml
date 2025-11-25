import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: dropdownTemplate
    width: parent ? parent.width : 225
    height: Math.max(60, contentColumn ? contentColumn.implicitHeight : 60)
    z: 1000  // Base z-index

    // Properties for customization
    property string label: "Dropdown Label"
    property string matlabProperty: "cfg.property"
    property var model: ["Option 1", "Option 2", "Option 3"]
    property int currentIndex: 0
    property bool hasAddFeature: false
    property bool isMultiSelect: false
    property int maxSelections: -1  // -1 = unlimited, 1 = single select in multi-style
    property string addPlaceholder: "Enter custom..."
    property var selectedItems: [] // For multi-select
    property var allItems: [] // For multi-select
    property bool addCheckboxChecked: false // For add item checkbox state

    property string dropdownState: "default"  // "default", "edit", or "add"
    property string matlabPropertyDraft: matlabProperty

    // Dynamic z-index management
    property int baseZ: 1000
    property int activeZ: 2000

    onActiveFocusChanged: {
        z = activeFocus ? activeZ : baseZ
    }

    // Exposed properties
    property string currentText: isMultiSelect ? getMultiSelectFormattedText() : (model[currentIndex] || "")

    // Signals
    signal selectionChanged(string value, int index)
    signal addItem(string newItem)
    signal deleteItem(string itemToDelete)
    signal multiSelectionChanged(var selected)
    signal deleteRequested()
    signal propertySaveRequested(string propertyValue, var selectedValues, bool useCellFormat)

    onMatlabPropertyChanged: {
        if (dropdownState !== "add") {
            matlabPropertyDraft = matlabProperty
        }
    }

    onDropdownStateChanged: {
        if (dropdownState === "add") {
            matlabPropertyDraft = matlabProperty
            if (propertyInput) {
                Qt.callLater(function() {
                    propertyInput.forceActiveFocus()
                    propertyInput.selectAll()
                })
            }
        }
    }

    // Function to get display text for multi-select
    function getMultiSelectText() {
        if (selectedItems.length === 0) {
            return "None"
        } else if (selectedItems.length === allItems.length) {
            return "All"
        } else {
            return selectedItems.length + " selected"
        }
    }

    // Function to get formatted text for multi-select
    function getMultiSelectFormattedText() {
        if (selectedItems.length === 0) {
            return ""
        } else {
            return selectedItems.join(", ")
        }
    }

    // Function to delete an option
    function deleteOption(itemToDelete, itemIndex) {
        if (isMultiSelect) {
            // For multi-select dropdowns
            var newAllItems = allItems.slice()
            var newSelectedItems = selectedItems.slice()

            // Remove from allItems
            var allItemsIndex = newAllItems.indexOf(itemToDelete)
            if (allItemsIndex !== -1) {
                newAllItems.splice(allItemsIndex, 1)
                allItems = newAllItems
            }

            // Remove from selectedItems if it was selected
            var selectedIndex = newSelectedItems.indexOf(itemToDelete)
            if (selectedIndex !== -1) {
                newSelectedItems.splice(selectedIndex, 1)
                selectedItems = newSelectedItems
                multiSelectionChanged(selectedItems)
            }

            // Emit signal to parent to remove from QML file
            deleteItem(itemToDelete)
        } else {
            // For single-select dropdowns
            var newModel = model.slice()

            // Remove from model
            if (itemIndex >= 0 && itemIndex < newModel.length) {
                newModel.splice(itemIndex, 1)
                model = newModel

                // Adjust currentIndex if necessary
                if (currentIndex >= itemIndex && currentIndex > 0) {
                    currentIndex = currentIndex - 1
                } else if (newModel.length === 0) {
                    currentIndex = 0
                }

                // Emit signal to parent to remove from QML file
                deleteItem(itemToDelete)
            }
        }
    }

    Column {
        id: contentColumn
        width: parent.width
        spacing: 5

        Item {
            width: parent.width
            implicitHeight: propertyDisplay.visible ? propertyDisplay.implicitHeight : propertyEditColumn.implicitHeight

            Text {
                id: propertyDisplay
                visible: dropdownState !== "add"
                text: matlabProperty + " = '" + (isMultiSelect ? "{" + getMultiSelectFormattedText() + "}" : (comboBox.currentText || "none")) + "'"
                font.pixelSize: 12
                color: "#666"
                wrapMode: Text.Wrap
                width: parent.width

                MouseArea {
                    anchors.fill: parent
                    onDoubleClicked: {
                        dropdownState = "edit"
                    }
                }
            }

            Row {
                id: propertyEditColumn
                visible: dropdownState === "add"
                width: parent.width
                spacing: 8

                Rectangle {
                    width: parent.width * 0.33
                    height: 32
                    color: "#f5f5f5"
                    border.color: "#ccc"
                    border.width: 1
                    radius: 3

                    TextInput {
                        id: propertyInput
                        anchors.fill: parent
                        anchors.margins: 6
                        text: dropdownTemplate.matlabPropertyDraft
                        font.pixelSize: 12
                        color: "#333"
                        selectByMouse: true
                        verticalAlignment: TextInput.AlignVCenter
                        topPadding: 0
                        bottomPadding: 0
                        onTextChanged: {
                            if (dropdownTemplate.matlabPropertyDraft !== text) {
                                dropdownTemplate.matlabPropertyDraft = text
                                dropdownTemplate.matlabProperty = text
                            }
                        }
                    }

                    Text {
                        anchors.verticalCenter: propertyInput.verticalCenter
                        anchors.left: propertyInput.left
                        anchors.right: propertyInput.right
                        anchors.leftMargin: 6
                        anchors.rightMargin: 6
                        text: "cfg."
                        font.pixelSize: 12
                        color: "#999"
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignLeft
                        visible: propertyInput.text.length === 0 && !propertyInput.activeFocus
                    }
                }

                Text {
                    id: valuePreview
                    anchors.verticalCenter: parent.verticalCenter
                    text: "= '" + (isMultiSelect ? "{" + getMultiSelectFormattedText() + "}" : (comboBox.currentText || "none")) + "'"
                    font.pixelSize: 12
                    color: "#666"
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                    width: parent.width - propertyEditColumn.spacing - (parent.width * 0.33)
                }
            }
        }

        // Single-select interface
        Column {
            id: singleSelectColumn
            width: parent.width
            spacing: 5
            visible: !isMultiSelect

            // Custom display rectangle (consistent with multi-select)
            Rectangle {
                id: singleSelectDisplay
                width: parent.width
                height: 30
                color: "#f5f5f5"
                border.color: "#ccc"
                border.width: 1
                radius: 3

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: comboBox.currentText || "Select option..."
                    font.pixelSize: 12
                    color: "#333"
                }

                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: "▼"
                    font.pixelSize: 10
                    color: "#666"
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        singleSelectPopup.visible = !singleSelectPopup.visible
                    }
                }
            }

            ComboBox {
                id: comboBox
                visible: false  // Hidden ComboBox for functionality
                width: parent.width
                height: 0
                model: dropdownTemplate.model
                currentIndex: dropdownTemplate.currentIndex

                onCurrentTextChanged: {
                    if (currentText) {
                        selectionChanged(currentText, currentIndex)
                    }
                }

                popup.onOpened: {
                    dropdownTemplate.z = dropdownTemplate.activeZ
                }

                popup.onClosed: {
                    dropdownTemplate.z = dropdownTemplate.baseZ
                }

                background: Rectangle {
                    visible: false  // Hide the default background
                }

                contentItem: Rectangle {
                    visible: false  // Hide the default content
                }
            }

            // Custom popup for single-select with add option
            Rectangle {
                id: singleSelectPopup
                objectName: "singleSelectPopup"
                visible: false
                width: parent.width
                property int computedHeight: {
                    var addVisible = hasAddFeature && (dropdownTemplate.dropdownState === "edit" || dropdownTemplate.dropdownState === "add")
                    var itemCount = comboBox.model.length + (addVisible ? 1 : 0)
                    var contentHeight = itemCount * 25 + Math.max(0, itemCount - 1) * 2
                    var maxHeight = 8 * 25 + 7 * 2 + 10  // Max 8 options visible
                    return Math.min(contentHeight + 10, maxHeight)
                }
                height: visible ? computedHeight : 0
                color: "white"
                border.color: "#ccc"
                border.width: 1
                radius: 3
                z: 1000

                onVisibleChanged: {
                    dropdownTemplate.z = visible ? dropdownTemplate.activeZ : dropdownTemplate.baseZ
                }

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 5

                    Column {
                        width: parent.width
                        spacing: 2

                        // Existing options
                        Repeater {
                            model: comboBox.model
                            delegate: Rectangle {
                                width: singleSelectPopup.width
                                height: 25
                                color: comboBox.currentIndex === index ? "#e3f2fd" : (optionMouseArea.containsMouse ? "#f5f5f5" : "transparent")

                                Item {
                                    anchors.fill: parent
                                    anchors.leftMargin: 5
                                    anchors.rightMargin: 5

                                    Text {
                                        id: singleOptionText
                                        anchors.left: parent.left
                                        anchors.right: dropdownTemplate.dropdownState === "edit" ? trashIcon.left : parent.right
                                        anchors.rightMargin: dropdownTemplate.dropdownState === "edit" ? 8 : 0
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData
                                        font.pixelSize: 12
                                        color: "#333"
                                        elide: Text.ElideRight  // Truncate text if too long
                                    }

                                    // Trash icon (visible only in edit mode, higher opacity on hover)
                                    Text {
                                        id: trashIcon
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.right: parent.right
                                        width: 20
                                        height: 20
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        text: "🗑️"
                                        font.pixelSize: 12
                                        color: "#666"
                                        opacity: optionMouseArea.containsMouse ? 0.9 : 0.3
                                        visible: dropdownTemplate.dropdownState === "edit"
                                    }
                                }

                                MouseArea {
                                    id: optionMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: function(mouse) {
                                        if (dropdownTemplate.dropdownState === "edit" && mouse.x >= parent.width - 25) {
                                            // Clicked on trash icon area - delete the option
                                            deleteOption(modelData, index)
                                        } else {
                                            // Clicked on option text area - select the option
                                            comboBox.currentIndex = index
                                            singleSelectPopup.visible = false
                                            selectionChanged(modelData, index)
                                        }
                                    }
                                }
                            }
                        }

                        // Add new item option (only when hasAddFeature is true and in edit/add mode)
                        Rectangle {
                            visible: hasAddFeature && (dropdownState === "edit" || dropdownState === "add")
                            width: singleSelectPopup.width
                            height: singleAddInput.visible ? 30 : 25
                            color: "transparent"

                            // Empty checkbox for consistency (always visible)
                            Rectangle {
                                id: singleAddCheckbox
                                anchors.left: parent.left
                                anchors.leftMargin: 5
                                anchors.verticalCenter: parent.verticalCenter
                                width: 15
                                height: 15
                                border.color: "#666"
                                border.width: 1
                                color: "white"
                            }

                            // Display text when not editing
                            Text {
                                id: singleAddText
                                anchors.left: singleAddCheckbox.right
                                anchors.leftMargin: 5
                                anchors.right: parent.right
                                anchors.rightMargin: 5
                                anchors.verticalCenter: parent.verticalCenter
                                text: addPlaceholder
                                font.pixelSize: 12
                                font.italic: true
                                color: "#666"
                                visible: !singleAddInput.visible
                            }

                            // Input field when editing
                            TextInput {
                                id: singleAddInput
                                anchors.left: singleAddCheckbox.right
                                anchors.leftMargin: 5
                                anchors.right: parent.right
                                anchors.rightMargin: 5
                                anchors.verticalCenter: parent.verticalCenter
                                font.pixelSize: 12
                                color: "#333"
                                visible: false
                                clip: true

                                onAccepted: { // Enter key pressed
                                    addNewItem()
                                }

                                onActiveFocusChanged: {
                                    if (!activeFocus && visible) {
                                        addNewItem()
                                    }
                                }

                                function addNewItem() {
                                    var newItem = text.trim()
                                    if (newItem !== "" && model.indexOf(newItem) === -1) {
                                        // Add to model
                                        var newModel = model.slice()
                                        newModel.push(newItem)
                                        model = newModel
                                        comboBox.currentIndex = newModel.length - 1

                                        // Emit signal
                                        addItem(newItem)

                                        // Hide input and show text
                                        text = ""
                                        visible = false
                                        singleAddText.visible = true
                                        singleSelectPopup.visible = false
                                    } else {
                                        // Hide input and show text
                                        text = ""
                                        visible = false
                                        singleAddText.visible = true
                                    }
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    if (!singleAddInput.visible) {
                                        singleAddText.visible = false
                                        singleAddInput.visible = true
                                        singleAddInput.forceActiveFocus()
                                    }
                                }
                            }
                        }
                    }
                }
            }


        }

        // Multi-select interface
        Rectangle {
            id: multiSelectDisplay
            visible: isMultiSelect
            width: parent.width
            height: 30
            color: "#f5f5f5"
            border.color: "#ccc"
            border.width: 1
            radius: 3

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: getMultiSelectText()
                font.pixelSize: 12
                color: "#333"
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: "▼"
                font.pixelSize: 10
                color: "#666"
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    multiSelectPopup.visible = !multiSelectPopup.visible
                }
            }
        }

        // Multi-select popup
        Rectangle {
            id: multiSelectPopup
            objectName: "multiSelectPopup"
            visible: false
            x: 0
            y: multiSelectDisplay.y + multiSelectDisplay.height
            width: parent.width
            height: {
                var addVisible = hasAddFeature && (dropdownTemplate.dropdownState === "edit" || dropdownTemplate.dropdownState === "add")
                var itemCount = (maxSelections !== 1 ? 1 : 0) + allItems.length + (addVisible ? 1 : 0)
                var contentHeight = itemCount * 25 + Math.max(0, itemCount - 1) * 2
                var maxHeight = 9 * 25 + 8 * 2 + 10  // Max 9 options visible
                return Math.min(contentHeight + 10, maxHeight)
            }
            color: "white"
            border.color: "#ccc"
            border.width: 1
            radius: 3
            z: 1000

            onVisibleChanged: {
                dropdownTemplate.z = visible ? dropdownTemplate.activeZ : dropdownTemplate.baseZ
            }

            ScrollView {
                anchors.fill: parent
                anchors.margins: 5

                Column {
                    width: parent.width
                    spacing: 2

                    // Include All option (only for multi-select with unlimited selections)
                    Rectangle {
                        width: multiSelectPopup.width
                        height: maxSelections === 1 ? 0 : 25
                        visible: maxSelections !== 1
                        color: selectedItems.length === allItems.length ? "#e3f2fd" : "transparent"

                        Row {
                            anchors.fill: parent
                            anchors.leftMargin: 5
                            spacing: 5

                            Rectangle {
                                width: 15
                                height: 15
                                anchors.verticalCenter: parent.verticalCenter
                                border.color: "#666"
                                border.width: 1
                                color: selectedItems.length === allItems.length ? "#2196f3" : "white"

                                Text {
                                    anchors.centerIn: parent
                                    text: "✓"
                                    color: "white"
                                    font.pixelSize: 10
                                    visible: selectedItems.length === allItems.length
                                }
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Include All"
                                font.pixelSize: 12
                                font.bold: true
                                color: "#333"
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            enabled: maxSelections !== 1
                            onClicked: {
                                if (maxSelections !== 1) {
                                    if (selectedItems.length === allItems.length) {
                                        selectedItems = []
                                    } else {
                                        selectedItems = allItems.slice()
                                    }
                                    multiSelectionChanged(selectedItems)
                                }
                            }
                        }
                    }

                    // Individual options
                    Repeater {
                        model: allItems

                        Rectangle {
                            width: multiSelectPopup.width
                            height: 25
                            color: selectedItems.indexOf(modelData) !== -1 ? "#e3f2fd" : (optionMouseArea.containsMouse ? "#f5f5f5" : "transparent")

                            Item {
                                anchors.fill: parent
                                anchors.leftMargin: 5
                                anchors.rightMargin: 5

                                Rectangle {
                                    id: optionCheckbox
                                    width: 15
                                    height: 15
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    border.color: "#666"
                                    border.width: 1
                                    color: selectedItems.indexOf(modelData) !== -1 ? "#2196f3" : "white"

                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"
                                        color: "white"
                                        font.pixelSize: 10
                                        visible: selectedItems.indexOf(modelData) !== -1
                                    }
                                }

                                Text {
                                    id: optionText
                                    anchors.left: optionCheckbox.right
                                    anchors.leftMargin: 8
                                    anchors.right: dropdownTemplate.dropdownState === "edit" ? trashIcon.left : parent.right
                                    anchors.rightMargin: dropdownTemplate.dropdownState === "edit" ? 8 : 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData
                                    font.pixelSize: 12
                                    color: "#333"
                                    elide: Text.ElideRight  // Truncate text if too long
                                }

                                // Trash icon (visible only in edit mode, higher opacity on hover)
                                Text {
                                    id: trashIcon
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.right: parent.right
                                    width: 20
                                    height: 20
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    text: "🗑️"
                                    font.pixelSize: 12
                                    color: "#666"
                                    opacity: optionMouseArea.containsMouse ? 0.9 : 0.3
                                    visible: dropdownTemplate.dropdownState === "edit"
                                }
                            }

                            MouseArea {
                                id: optionMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: function(mouse) {
                                    if (dropdownTemplate.dropdownState === "edit" && mouse.x >= parent.width - 25) {
                                        // Clicked on trash icon area - delete the option
                                        deleteOption(modelData, allItems.indexOf(modelData))
                                    } else {
                                        // Clicked on option area - toggle selection
                                        var index = selectedItems.indexOf(modelData)
                                        var newSelection = selectedItems.slice()

                                        if (index !== -1) {
                                            // If already selected and maxSelections allows, remove it
                                            if (maxSelections !== 1) {
                                                newSelection.splice(index, 1)
                                            }
                                        } else {
                                            // If not selected, add it
                                            if (maxSelections === 1) {
                                                // Single select mode - replace selection
                                                newSelection = [modelData]
                                            } else {
                                                // Multi select mode - add to selection
                                                newSelection.push(modelData)
                                            }
                                        }

                                        selectedItems = newSelection
                                        multiSelectionChanged(selectedItems)
                                    }
                                }
                            }
                        }
                    }

                        // Add new item option (only when hasAddFeature is true and in edit/add mode)
                    Rectangle {
                        visible: hasAddFeature && (dropdownState === "edit" || dropdownState === "add")
                        width: multiSelectPopup.width
                        height: addInput.visible ? 30 : 25
                        color: "transparent"

                        // Custom checkbox for the add item (always visible for consistency)
                        Rectangle {
                            id: addCheckbox
                            anchors.left: parent.left
                            anchors.leftMargin: 5
                            anchors.verticalCenter: parent.verticalCenter
                            width: 15
                            height: 15
                            border.color: "#666"
                            border.width: 1
                            color: addCheckboxChecked ? "#2196f3" : "white"

                            Text {
                                anchors.centerIn: parent
                                text: "✓"
                                color: "white"
                                font.pixelSize: 10
                                visible: addCheckboxChecked
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    addCheckboxChecked = !addCheckboxChecked
                                }
                            }
                        }

                        // Display text when not editing
                        Text {
                            id: addText
                            anchors.left: addCheckbox.right
                            anchors.leftMargin: 5
                            anchors.right: parent.right
                            anchors.rightMargin: 5
                            anchors.verticalCenter: parent.verticalCenter
                            text: addPlaceholder
                            font.pixelSize: 12
                            font.italic: true
                            color: "#666"
                            visible: !addInput.visible
                        }

                        // Input field when editing
                        TextInput {
                            id: addInput
                            anchors.left: addCheckbox.right
                            anchors.leftMargin: 5
                            anchors.right: parent.right
                            anchors.rightMargin: 5
                            anchors.verticalCenter: parent.verticalCenter
                            font.pixelSize: 12
                            color: "#333"
                            visible: false
                            clip: true

                            onAccepted: { // Enter key pressed
                                addNewItem()
                            }

                            onActiveFocusChanged: {
                                if (!activeFocus && visible) {
                                    addNewItem()
                                }
                            }

                            function addNewItem() {
                                var newItem = text.trim()
                                if (newItem !== "" && allItems.indexOf(newItem) === -1) {
                                    // Add to allItems
                                    var newAllItems = allItems.slice()
                                    newAllItems.push(newItem)
                                    allItems = newAllItems

                                    // Select the new item based on checkbox state
                                    var newSelection = selectedItems.slice()
                                    if (addCheckboxChecked) {
                                        if (maxSelections === 1) {
                                            newSelection = [newItem]
                                        } else {
                                            newSelection.push(newItem)
                                        }
                                    }
                                    selectedItems = newSelection

                                    // Emit signals
                                    addItem(newItem)
                                    multiSelectionChanged(selectedItems)

                                    // Hide input and show text
                                    text = ""
                                    visible = false
                                    addText.visible = true
                                } else {
                                    // Hide input and show text
                                    text = ""
                                    visible = false
                                    addText.visible = true
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                if (!addInput.visible) {
                                    addText.visible = false
                                    addInput.visible = true
                                    addCheckbox.visible = true
                                    addCheckboxChecked = false  // Start unchecked
                                    addInput.forceActiveFocus()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Icons - only visible in edit mode, positioned to the right of the display
    Column {
        x: (isMultiSelect ? multiSelectDisplay : singleSelectDisplay).x + (isMultiSelect ? multiSelectDisplay : singleSelectDisplay).width + 15
        y: (isMultiSelect ? multiSelectDisplay : singleSelectDisplay).y + (isMultiSelect ? multiSelectDisplay : singleSelectDisplay).height / 2 - height / 2
        spacing: 5
        visible: dropdownState === "edit" || dropdownState === "add"

        // Save icon
        Rectangle {
            width: 25
            height: 25
            color: "transparent"
            border.color: "#ccc"
            border.width: 1
            radius: 3
            visible: dropdownState === "add"

            Text {
                anchors.centerIn: parent
                text: "💾"
                font.pixelSize: 12
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    dropdownTemplate.matlabPropertyDraft = propertyInput.text
                    dropdownTemplate.matlabProperty = dropdownTemplate.matlabPropertyDraft
                    var selectionPayload
                    if (dropdownTemplate.isMultiSelect) {
                        selectionPayload = dropdownTemplate.selectedItems && dropdownTemplate.selectedItems.slice ? dropdownTemplate.selectedItems.slice(0) : (dropdownTemplate.selectedItems || [])
                    } else {
                        selectionPayload = []
                        if (comboBox.currentText && comboBox.currentText.length > 0) {
                            selectionPayload.push(comboBox.currentText)
                        }
                    }

                    var needsCellFormat = dropdownTemplate.isMultiSelect && dropdownTemplate.maxSelections !== 1

                    if (typeof matlabExecutor !== "undefined" && matlabExecutor.saveDropdownPropertyToMatlab) {
                        matlabExecutor.saveDropdownPropertyToMatlab(
                                    dropdownTemplate.matlabProperty,
                                    selectionPayload,
                                    needsCellFormat)
                    }

                    propertySaveRequested(dropdownTemplate.matlabProperty, selectionPayload, needsCellFormat)
                    propertyInput.focus = false
                    dropdownTemplate.dropdownState = "default"
                }
            }
        }

        // Trash icon
        Rectangle {
            width: 25
            height: 25
            color: "transparent"
            border.color: "#ccc"
            border.width: 1
            radius: 3

            Text {
                anchors.centerIn: parent
                text: "🗑️"
                font.pixelSize: 12
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if (dropdownTemplate.matlabProperty && typeof matlabExecutor !== "undefined" && matlabExecutor.removeMatlabProperty) {
                        matlabExecutor.removeMatlabProperty(dropdownTemplate.matlabProperty)
                    }
                    deleteRequested()
                }
            }
        }
    }
}