import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: checkboxTemplate
    width: parent ? parent.width : 225
    height: Math.max(40, contentColumn ? contentColumn.implicitHeight : 40)
    z: 1000

    // Properties for customization
    property string label: "Checkbox Label"
    property string matlabProperty: "cfg.property"
    property bool checked: false
    property bool enabled: true
    property string checkboxState: "default"  // "default", "edit", or "add"
    property string matlabPropertyDraft: matlabProperty

    // Dynamic z-index management
    property int baseZ: 1000
    property int activeZ: 2000

    onActiveFocusChanged: {
        z = activeFocus ? activeZ : baseZ
    }

    // Signals
    signal toggled(bool isChecked)
    signal deleteRequested()
    signal propertySaveRequested(string propertyValue, bool isChecked)

    onMatlabPropertyChanged: {
        if (checkboxState !== "add") {
            matlabPropertyDraft = matlabProperty
        }
    }

    onCheckboxStateChanged: {
        if (checkboxState === "add") {
            matlabPropertyDraft = matlabProperty
            if (propertyInput) {
                Qt.callLater(function() {
                    propertyInput.forceActiveFocus()
                    propertyInput.selectAll()
                })
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
                visible: checkboxState !== "add"
                text: matlabProperty + " = " + (checkbox.checked ? "'yes'" : "'no'")
                font.pixelSize: 12
                color: "#666"
                wrapMode: Text.Wrap
                width: parent.width

                MouseArea {
                    anchors.fill: parent
                    onDoubleClicked: {
                        checkboxState = "edit"
                    }
                }
            }

            Row {
                id: propertyEditColumn
                visible: checkboxState === "add"
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
                        text: checkboxTemplate.matlabPropertyDraft
                        font.pixelSize: 12
                        color: "#333"
                        selectByMouse: true
                        verticalAlignment: TextInput.AlignVCenter
                        topPadding: 0
                        bottomPadding: 0
                        onTextChanged: {
                            if (checkboxTemplate.matlabPropertyDraft !== text) {
                                checkboxTemplate.matlabPropertyDraft = text
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
                    text: "= " + (checkbox.checked ? "'yes'" : "'no'")
                    font.pixelSize: 12
                    color: "#666"
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                    width: parent.width - propertyEditColumn.spacing - (parent.width * 0.33)
                }
            }
        }

        // Custom Checkbox Control (Matching DropdownTemplate style)
        Row {
            spacing: 8
            width: parent.width
            
            Rectangle {
                id: customCheckbox
                width: 15
                height: 15
                anchors.verticalCenter: parent.verticalCenter
                border.color: "#666"
                border.width: 1
                color: checkboxTemplate.checked ? "#2196f3" : "white"

                Text {
                    anchors.centerIn: parent
                    text: "✓"
                    color: "white"
                    font.pixelSize: 10
                    visible: checkboxTemplate.checked
                }
                
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (checkboxTemplate.enabled) {
                            checkboxTemplate.checked = !checkboxTemplate.checked
                            toggled(checkboxTemplate.checked)
                        }
                    }
                }
            }
            
            Text {
                text: checkboxTemplate.label
                font.pixelSize: 12
                color: checkboxTemplate.enabled ? "#333" : "#999"
                anchors.verticalCenter: parent.verticalCenter
                
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (checkboxTemplate.enabled) {
                            checkboxTemplate.checked = !checkboxTemplate.checked
                            toggled(checkboxTemplate.checked)
                        }
                    }
                }
            }
        }
    }

    // Icons - only visible in edit/add mode
    Column {
        x: parent.width + 15
        y: contentColumn.y + contentColumn.height / 2 - height / 2
        spacing: 5
        visible: checkboxState === "edit" || checkboxState === "add"

        // Save icon
        Rectangle {
            width: 25
            height: 25
            color: "transparent"
            border.color: "#ccc"
            border.width: 1
            radius: 3
            visible: checkboxState === "add"

            Text {
                anchors.centerIn: parent
                text: "💾"
                font.pixelSize: 12
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    checkboxTemplate.matlabPropertyDraft = propertyInput.text
                    checkboxTemplate.matlabProperty = checkboxTemplate.matlabPropertyDraft

                    if (typeof matlabExecutor !== "undefined" && matlabExecutor.saveCheckboxPropertyToMatlab) {
                        matlabExecutor.saveCheckboxPropertyToMatlab(
                            checkboxTemplate.matlabProperty,
                            checkboxTemplate.checked
                        )
                    }

                    propertySaveRequested(checkboxTemplate.matlabProperty, checkboxTemplate.checked)
                    propertyInput.focus = false
                    checkboxTemplate.checkboxState = "default"
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
                    if (checkboxTemplate.matlabProperty && typeof matlabExecutor !== "undefined" && matlabExecutor.removeMatlabProperty) {
                        matlabExecutor.removeMatlabProperty(checkboxTemplate.matlabProperty)
                    }
                    deleteRequested()
                }
            }
        }
    }
}
