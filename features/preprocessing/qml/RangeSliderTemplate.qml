import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: rangeSliderTemplate
    width: parent ? parent.width : 225
    height: Math.max(80, contentColumn ? contentColumn.implicitHeight : 80)

    // Properties for customization
    property string label: "Range Slider Label"
    property string matlabProperty: "cfg.property"
    property real from: 0.0
    property real to: 1.0
    property real firstValue: 0.0
    property real secondValue: 1.0
    property real stepSize: 0.1
    property string unit: ""
    property bool enabled: true
    property string sliderState: "default"  // "default", "edit", or "add"
    property string matlabPropertyDraft: matlabProperty
    property string sliderId: ""  // Identifier for the slider instance
    property color backgroundColor: "#e0e0e0"

    function calculateDecimalPlaces(step) {
        if (step <= 0) {
            return 3
        }
        var stepString = step.toString()
        var scientificIndex = stepString.indexOf("e-")
        if (scientificIndex !== -1) {
            var exponentText = stepString.substring(scientificIndex + 2)
            var exponentValue = parseInt(exponentText)
            if (!isNaN(exponentValue)) {
                return Math.min(6, Math.max(0, exponentValue))
            }
        }
        var decimalIndex = stepString.indexOf('.')
        if (decimalIndex !== -1) {
            return Math.min(6, Math.max(0, stepString.length - decimalIndex - 1))
        }
        return 0
    }

    function formatValue(value) {
        var precision = rangeSliderTemplate.decimalPlaces
        if (precision < 0) {
            precision = 0
        } else if (precision > 6) {
            precision = 6
        }
        var factor = Math.pow(10, precision)
        var rounded = Math.round(Number(value) * factor) / factor
        var fixedString = rounded.toFixed(precision)
        if (precision > 0) {
            fixedString = fixedString.replace(/(\.\d*?[1-9])0+$/, '$1')
            fixedString = fixedString.replace(/\.0+$/, '')
        }
        if (fixedString === "-0") {
            fixedString = "0"
        }
        return fixedString
    }

    property int decimalPlaces: calculateDecimalPlaces(stepSize)

    onDecimalPlacesChanged: {
        if (fromInput && !fromInput.activeFocus) {
            fromInput.text = formatValue(from)
        }
        if (toInput && !toInput.activeFocus) {
            toInput.text = formatValue(to)
        }
        if (firstValueInput && !firstValueInput.activeFocus) {
            firstValueInput.text = formatValue(firstValue)
        }
        if (secondValueInput && !secondValueInput.activeFocus) {
            secondValueInput.text = formatValue(secondValue)
        }
    }

    // Dynamic z-index management
    property int baseZ: 1000
    property int activeZ: 2000

    onActiveFocusChanged: {
        z = activeFocus ? activeZ : baseZ
    }

    onMatlabPropertyChanged: {
        if (sliderState !== "add") {
            matlabPropertyDraft = matlabProperty
        }
    }

    onFromChanged: {
        if (fromInput && !fromInput.activeFocus) {
            fromInput.text = formatValue(from)
        }
    }

    onToChanged: {
        if (toInput && !toInput.activeFocus) {
            toInput.text = formatValue(to)
        }
    }

    onFirstValueChanged: {
        if (firstValueInput && !firstValueInput.activeFocus) {
            firstValueInput.text = formatValue(firstValue)
        }
    }

    onSecondValueChanged: {
        if (secondValueInput && !secondValueInput.activeFocus) {
            secondValueInput.text = formatValue(secondValue)
        }
    }

    onSliderStateChanged: {
        if (sliderState === "add") {
            matlabPropertyDraft = matlabProperty
            if (propertyInput) {
                Qt.callLater(function() {
                    propertyInput.forceActiveFocus()
                    propertyInput.selectAll()
                })
            }
        }
    }

    // Signals
    signal rangeChanged(real firstValue, real secondValue)

    function snapValue(value) {
        if (rangeSlider && typeof rangeSlider.snapToStep === "function") {
            return rangeSlider.snapToStep(value)
        }
        return value
    }
    signal deleteRequested()
    signal propertySaveRequested(string propertyValue, real firstValue, real secondValue, string unit)

    Column {
        id: contentColumn
        width: parent.width
        spacing: 10

        Item {
            width: parent.width
            implicitHeight: propertyDisplay.visible ? propertyDisplay.implicitHeight : propertyEditColumn.implicitHeight

            Text {
                id: propertyDisplay
                visible: sliderState !== "add"
                text: matlabProperty + " = [" + rangeSliderTemplate.formatValue(rangeSlider.first.value) + unit + " " + rangeSliderTemplate.formatValue(rangeSlider.second.value) + unit + "]"
                font.pixelSize: 12
                color: "#666"
                wrapMode: Text.Wrap
                width: parent.width

                MouseArea {
                    anchors.fill: parent
                    onDoubleClicked: {
                        sliderState = "edit"
                    }
                }
            }

            Row {
                id: propertyEditColumn
                visible: sliderState === "add"
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
                        text: rangeSliderTemplate.matlabPropertyDraft
                        font.pixelSize: 12
                        color: "#333"
                        selectByMouse: true
                        verticalAlignment: TextInput.AlignVCenter
                        topPadding: 0
                        bottomPadding: 0
                        onTextChanged: {
                            if (rangeSliderTemplate.matlabPropertyDraft !== text) {
                                rangeSliderTemplate.matlabPropertyDraft = text
                                rangeSliderTemplate.matlabProperty = text
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
                    text: "= [" + rangeSliderTemplate.formatValue(rangeSlider.first.value) + unit + " " + rangeSliderTemplate.formatValue(rangeSlider.second.value) + unit + "]"
                    font.pixelSize: 12
                    color: "#666"
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                    width: parent.width - propertyEditColumn.spacing - (parent.width * 0.33)
                }
            }
        }

        RangeSlider {
            id: rangeSlider
            width: parent.width
            from: rangeSliderTemplate.from
            to: rangeSliderTemplate.to
            first.value: rangeSliderTemplate.firstValue
            second.value: rangeSliderTemplate.secondValue
            stepSize: rangeSliderTemplate.stepSize
            snapMode: RangeSlider.SnapAlways
            enabled: rangeSliderTemplate.enabled

            background: Rectangle {
                x: rangeSlider.leftPadding
                y: rangeSlider.topPadding + rangeSlider.availableHeight / 2 - height / 2
                implicitWidth: 200
                implicitHeight: 6
                width: rangeSlider.availableWidth
                height: implicitHeight
                radius: 3
                color: backgroundColor

                // Active range
                Rectangle {
                    x: rangeSlider.first.visualPosition * parent.width
                    width: (rangeSlider.second.visualPosition - rangeSlider.first.visualPosition) * parent.width
                    height: parent.height
                    color: rangeSlider.enabled ? "#2196f3" : "#cccccc"
                    radius: 3
                }
            }

            first.handle: Rectangle {
                x: rangeSlider.leftPadding + rangeSlider.first.visualPosition * (rangeSlider.availableWidth - width)
                y: rangeSlider.topPadding + rangeSlider.availableHeight / 2 - height / 2
                implicitWidth: 20
                implicitHeight: 20
                radius: 10
                color: rangeSlider.first.pressed ? "#1976d2" : (rangeSlider.enabled ? "#2196f3" : "#cccccc")
                border.color: rangeSlider.enabled ? "#1976d2" : "#999999"
                border.width: 2
                visible: rangeSlider.enabled
            }

            second.handle: Rectangle {
                x: rangeSlider.leftPadding + rangeSlider.second.visualPosition * (rangeSlider.availableWidth - width)
                y: rangeSlider.topPadding + rangeSlider.availableHeight / 2 - height / 2
                implicitWidth: 20
                implicitHeight: 20
                radius: 10
                color: rangeSlider.second.pressed ? "#1976d2" : (rangeSlider.enabled ? "#2196f3" : "#cccccc")
                border.color: rangeSlider.enabled ? "#1976d2" : "#999999"
                border.width: 2
                visible: rangeSlider.enabled
            }

            function snapToStep(value) {
                var step = rangeSliderTemplate.stepSize > 0 ? rangeSliderTemplate.stepSize : 0.1
                var snapped = Math.round((value - from) / step) * step + from
                var precision = rangeSliderTemplate.decimalPlaces
                var factor = Math.pow(10, precision)
                return Math.round(snapped * factor) / factor
            }

            first.onValueChanged: function() {
                var snapped = snapToStep(first.value)
                if (Math.abs(snapped - first.value) > 1e-6) {
                    first.value = snapped
                    return
                }
                rangeSliderTemplate.firstValue = snapped
                if (firstValueInput && !firstValueInput.activeFocus) {
                    firstValueInput.text = rangeSliderTemplate.formatValue(rangeSliderTemplate.firstValue)
                }
                rangeChanged(first.value, second.value)
                updateQmlFile()
            }

            second.onValueChanged: function() {
                var snapped = snapToStep(second.value)
                if (Math.abs(snapped - second.value) > 1e-6) {
                    second.value = snapped
                    return
                }
                rangeSliderTemplate.secondValue = snapped
                if (secondValueInput && !secondValueInput.activeFocus) {
                    secondValueInput.text = rangeSliderTemplate.formatValue(rangeSliderTemplate.secondValue)
                }
                rangeChanged(first.value, second.value)
                updateQmlFile()
            }
        }


        // Edit mode inputs
        Column {
            width: parent.width
            spacing: 5
            visible: sliderState === "edit" || sliderState === "add"

            // From input
            Row {
                spacing: 10
                Text {
                    text: "From:"
                    font.pixelSize: 11
                    color: "#666"
                    anchors.verticalCenter: parent.verticalCenter
                    width: 80
                }
                TextField {
                    id: fromInput
                    width: 80
                    font.pixelSize: 11
                    color: "#333"
                    background: Rectangle {
                        color: "#f5f5f5"
                        border.color: "#ccc"
                        border.width: 1
                        radius: 3
                    }
                    onAccepted: updateFrom()
                    Component.onCompleted: text = rangeSliderTemplate.formatValue(rangeSliderTemplate.from)
                    onActiveFocusChanged: {
                        if (!activeFocus) {
                            text = rangeSliderTemplate.formatValue(rangeSliderTemplate.from)
                        }
                    }
                }
            }

            // To input
            Row {
                spacing: 10
                Text {
                    text: "To:"
                    font.pixelSize: 11
                    color: "#666"
                    anchors.verticalCenter: parent.verticalCenter
                    width: 80
                }
                TextField {
                    id: toInput
                    width: 80
                    font.pixelSize: 11
                    color: "#333"
                    background: Rectangle {
                        color: "#f5f5f5"
                        border.color: "#ccc"
                        border.width: 1
                        radius: 3
                    }
                    onAccepted: updateTo()
                    Component.onCompleted: text = rangeSliderTemplate.formatValue(rangeSliderTemplate.to)
                    onActiveFocusChanged: {
                        if (!activeFocus) {
                            text = rangeSliderTemplate.formatValue(rangeSliderTemplate.to)
                        }
                    }
                }
            }

            // First Value input
            Row {
                spacing: 10
                Text {
                    text: "First Value:"
                    font.pixelSize: 11
                    color: "#666"
                    anchors.verticalCenter: parent.verticalCenter
                    width: 80
                }
                TextField {
                    id: firstValueInput
                    width: 80
                    font.pixelSize: 11
                    color: "#333"
                    background: Rectangle {
                        color: "#f5f5f5"
                        border.color: "#ccc"
                        border.width: 1
                        radius: 3
                    }
                    validator: DoubleValidator { bottom: rangeSliderTemplate.from; top: rangeSliderTemplate.to }
                    onAccepted: updateFirstValue()
                    Component.onCompleted: text = rangeSliderTemplate.formatValue(rangeSliderTemplate.firstValue)
                    onActiveFocusChanged: {
                        if (!activeFocus) {
                            text = rangeSliderTemplate.formatValue(rangeSliderTemplate.firstValue)
                        }
                    }
                }
            }

            // Second Value input
            Row {
                spacing: 10
                Text {
                    text: "Second Value:"
                    font.pixelSize: 11
                    color: "#666"
                    anchors.verticalCenter: parent.verticalCenter
                    width: 80
                }
                TextField {
                    id: secondValueInput
                    width: 80
                    font.pixelSize: 11
                    color: "#333"
                    background: Rectangle {
                        color: "#f5f5f5"
                        border.color: "#ccc"
                        border.width: 1
                        radius: 3
                    }
                    validator: DoubleValidator { bottom: rangeSliderTemplate.from; top: rangeSliderTemplate.to }
                    onAccepted: updateSecondValue()
                    Component.onCompleted: text = rangeSliderTemplate.formatValue(rangeSliderTemplate.secondValue)
                    onActiveFocusChanged: {
                        if (!activeFocus) {
                            text = rangeSliderTemplate.formatValue(rangeSliderTemplate.secondValue)
                        }
                    }
                }
            }

            // Warning text
            Text {
                id: warningText
                text: ""
                font.pixelSize: 10
                color: "red"
                visible: text !== ""
            }
        }
    }

    // Icons - only visible in edit/add mode, positioned to the right of the slider bar
    Column {
        x: rangeSlider.x + rangeSlider.width + 15
        y: rangeSlider.y + rangeSlider.height / 2 - height / 2
        spacing: 5
        visible: sliderState === "edit" || sliderState === "add"

        // Save icon
        Rectangle {
            width: 25
            height: 25
            color: "transparent"
            border.color: "#ccc"
            border.width: 1
            radius: 3
            visible: sliderState === "add"

            Text {
                anchors.centerIn: parent
                text: "💾"
                font.pixelSize: 12
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    rangeSliderTemplate.matlabPropertyDraft = propertyInput.text
                    rangeSliderTemplate.matlabProperty = rangeSliderTemplate.matlabPropertyDraft

                    if (typeof matlabExecutor !== "undefined" && matlabExecutor.saveRangeSliderPropertyToMatlab) {
                        matlabExecutor.saveRangeSliderPropertyToMatlab(
                                    rangeSliderTemplate.matlabProperty,
                                    rangeSlider.first.value,
                                    rangeSlider.second.value,
                                    rangeSliderTemplate.unit)
                    }

                    propertySaveRequested(rangeSliderTemplate.matlabProperty,
                                           rangeSlider.first.value,
                                           rangeSlider.second.value,
                                           rangeSliderTemplate.unit)
                    propertyInput.focus = false
                    rangeSliderTemplate.sliderState = "default"
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
                    if (rangeSliderTemplate.matlabProperty && typeof matlabExecutor !== "undefined" && matlabExecutor.removeMatlabProperty) {
                        matlabExecutor.removeMatlabProperty(rangeSliderTemplate.matlabProperty)
                    }
                    deleteRequested()
                }
            }
        }
    }

    // Functions for edit mode
    function updateFrom() {
        var newFrom = parseFloat(fromInput.text)
        if (isNaN(newFrom)) {
            warningText.text = "Invalid 'from' value"
            return
        }
        if (newFrom >= to) {
            warningText.text = "'From' must be less than 'to'"
            return
        }
        from = newFrom
        // Adjust values if necessary
        if (firstValue < newFrom) firstValue = newFrom
        if (secondValue < newFrom) secondValue = newFrom
        fromInput.text = formatValue(from)
        warningText.text = ""
        rangeChanged(firstValue, secondValue)
        updateQmlFile()
        console.log("Updated from:", from, "firstValue:", firstValue, "secondValue:", secondValue)
    }

    function updateTo() {
        var newTo = parseFloat(toInput.text)
        if (isNaN(newTo)) {
            warningText.text = "Invalid 'to' value"
            return
        }
        if (newTo <= from) {
            warningText.text = "'To' must be greater than 'from'"
            return
        }
        to = newTo
        // Adjust values if necessary
        if (firstValue > newTo) firstValue = newTo
        if (secondValue > newTo) secondValue = newTo
        toInput.text = formatValue(to)
        warningText.text = ""
        rangeChanged(firstValue, secondValue)
        updateQmlFile()
        console.log("Updated to:", to, "firstValue:", firstValue, "secondValue:", secondValue)
    }

    function updateFirstValue() {
        var newFirst = parseFloat(firstValueInput.text)
        if (isNaN(newFirst)) {
            warningText.text = "Invalid first value"
            return
        }
        if (newFirst < from || newFirst > to) {
            warningText.text = "First value must be between " + from.toFixed(1) + " and " + to.toFixed(1)
            return
        }
        if (newFirst >= secondValue) {
            warningText.text = "First value must be less than second value"
            return
        }
    firstValue = rangeSlider.snapToStep(newFirst)
        firstValueInput.text = formatValue(firstValue)
        warningText.text = ""
        rangeChanged(firstValue, secondValue)
        updateQmlFile()
        console.log("Updated firstValue:", firstValue, "secondValue:", secondValue)
    }

    function updateSecondValue() {
        var newSecond = parseFloat(secondValueInput.text)
        if (isNaN(newSecond)) {
            warningText.text = "Invalid second value"
            return
        }
        if (newSecond < from || newSecond > to) {
            warningText.text = "Second value must be between " + from.toFixed(1) + " and " + to.toFixed(1)
            return
        }
        if (newSecond <= firstValue) {
            warningText.text = "Second value must be greater than first value"
            return
        }
    secondValue = rangeSlider.snapToStep(newSecond)
        secondValueInput.text = formatValue(secondValue)
        warningText.text = ""
        rangeChanged(firstValue, secondValue)
        updateQmlFile()
        console.log("Updated secondValue:", secondValue, "firstValue:", firstValue)
    }

    // Function to update QML file with current values
    function updateQmlFile() {
        if (sliderId === "baselineSlider") {
            matlabExecutor.updateBaselineSliderValues(from, to, firstValue, secondValue)
        } else if (sliderId === "dftfreqSlider") {
            matlabExecutor.updateDftfreqSliderValues(from, to, firstValue, secondValue)
        } else if (sliderId === "prestimPoststimSlider") {
            matlabExecutor.updatePrestimPoststimSliderValues(from, to, firstValue, secondValue)
        } else if (sliderId === "erpRangeSlider" && typeof matlabExecutor !== "undefined" && matlabExecutor.updateErpRangeSliderValues) {
            matlabExecutor.updateErpRangeSliderValues(from, to, firstValue, secondValue)
        }
    }
}