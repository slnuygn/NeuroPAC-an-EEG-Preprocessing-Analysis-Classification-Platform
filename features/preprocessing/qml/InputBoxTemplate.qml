import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: inputBoxTemplate
    width: parent ? parent.width : 225
    height: Math.max(60, contentColumn ? contentColumn.implicitHeight : 60)
    z: 1000

    // Properties for customization
    property string label: "Input Label"
    property string matlabProperty: "cfg.property"
    property string text: ""
    property string placeholderText: "Enter value..."
    property bool enabled: true
    property bool isNumeric: false
    property string inputBoxState: "default"  // "default", "edit", or "add"
    property string matlabPropertyDraft: matlabProperty

    // Dynamic z-index management
    property int baseZ: 1000
    property int activeZ: 2000

    onActiveFocusChanged: {
        z = activeFocus ? activeZ : baseZ
    }

    // Signals
    signal valueChanged(string newValue)
    signal deleteRequested()
    signal propertySaveRequested(string propertyValue, string value, bool isNumeric)

    onMatlabPropertyChanged: {
        if (inputBoxState !== "add") {
            matlabPropertyDraft = matlabProperty
        }
    }

    onInputBoxStateChanged: {
        if (inputBoxState === "add") {
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
                visible: inputBoxState !== "add"
                text: matlabProperty + " = " + (isNumeric ? inputField.text : ("'" + inputField.text + "'"))
                font.pixelSize: 12
                color: "#666"
                wrapMode: Text.Wrap
                width: parent.width

                MouseArea {
                    anchors.fill: parent
                    onDoubleClicked: {
                        inputBoxState = "edit"
                    }
                }
            }

            Row {
                id: propertyEditColumn
                visible: inputBoxState === "add"
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
                        text: inputBoxTemplate.matlabPropertyDraft
                        font.pixelSize: 12
                        color: "#333"
                        selectByMouse: true
                        verticalAlignment: TextInput.AlignVCenter
                        topPadding: 0
                        bottomPadding: 0
                        onTextChanged: {
                            if (inputBoxTemplate.matlabPropertyDraft !== text) {
                                inputBoxTemplate.matlabPropertyDraft = text
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
                    text: "= " + (isNumeric ? inputField.text : ("'" + inputField.text + "'"))
                    font.pixelSize: 12
                    color: "#666"
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                    width: parent.width - propertyEditColumn.spacing - (parent.width * 0.33)
                }
            }
        }

        // Input Box
        Rectangle {
            id: inputBoxBackground
            width: parent.width
            height: 30
            color: enabled ? "#f5f5f5" : "#e0e0e0"
            border.color: "#ccc"
            border.width: 1
            radius: 3

            TextInput {
                id: inputField
                anchors.fill: parent
                anchors.margins: 8
                text: inputBoxTemplate.text
                font.pixelSize: 12
                color: enabled ? "#333" : "#666"
                selectByMouse: true
                enabled: inputBoxTemplate.enabled
                verticalAlignment: TextInput.AlignVCenter
                clip: true

                Text {
                    text: inputBoxTemplate.placeholderText
                    color: "#999"
                    visible: !inputField.text && !inputField.activeFocus
                    anchors.fill: parent
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 12
                    font.italic: true
                }

                onTextChanged: {
                    if (inputBoxTemplate.text !== text) {
                        inputBoxTemplate.text = text
                        valueChanged(text)
                    }
                }
            }
        }
    }

    // Icons - only visible in edit/add mode
    Column {
        x: inputBoxBackground.width + 15
        y: contentColumn.y + inputBoxBackground.y + inputBoxBackground.height / 2 - height / 2
        spacing: 5
        visible: inputBoxState === "edit" || inputBoxState === "add"

        // Save icon
        Rectangle {
            width: 25
            height: 25
            color: "transparent"
            border.color: "#ccc"
            border.width: 1
            radius: 3
            visible: inputBoxState === "add"

            Text {
                anchors.centerIn: parent
                text: "💾"
                font.pixelSize: 12
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    inputBoxTemplate.matlabPropertyDraft = propertyInput.text
                    inputBoxTemplate.matlabProperty = inputBoxTemplate.matlabPropertyDraft

                    if (typeof matlabExecutor !== "undefined" && matlabExecutor.saveInputPropertyToMatlab) {
                        matlabExecutor.saveInputPropertyToMatlab(
                            inputBoxTemplate.matlabProperty,
                            inputBoxTemplate.text,
                            inputBoxTemplate.isNumeric
                        )
                    }

                    propertySaveRequested(inputBoxTemplate.matlabProperty, inputBoxTemplate.text, inputBoxTemplate.isNumeric)
                    propertyInput.focus = false
                    inputBoxTemplate.inputBoxState = "default"
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
                    if (inputBoxTemplate.matlabProperty && typeof matlabExecutor !== "undefined" && matlabExecutor.removeMatlabProperty) {
                        matlabExecutor.removeMatlabProperty(inputBoxTemplate.matlabProperty)
                    }
                    deleteRequested()
                }
            }
        }
    }
}
