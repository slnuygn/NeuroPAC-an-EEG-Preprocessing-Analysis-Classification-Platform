import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: topMenuComponent
    width: parent.width
    height: 30
    color: "#f8f9fa"
    z: 1000
    clip: false
    
    // Properties for menu states
    property bool fileMenuOpen: false
    property bool matlabSubmenuOpen: false
    property bool editMenuOpen: false
    property bool editModeChecked: false
    property bool addSubmenuOpen: false
    
    // Signals for communication with parent
    signal fieldtripDialogRequested()
    signal folderDialogRequested()
    signal createFunctionRequested()
    signal createScriptRequested()
    signal editModeToggled(bool checked)
    signal addDropdownRequested()
    signal addRangeSliderRequested()
    signal menuStateChanged(bool fileMenuOpen, bool matlabSubmenuOpen, bool editMenuOpen)
    
    // Function to close menus (can be called from parent)
    function closeMenus() {
        fileMenuOpen = false
        matlabSubmenuOpen = false
        editMenuOpen = false
        addSubmenuOpen = false
        menuStateChanged(fileMenuOpen, matlabSubmenuOpen, editMenuOpen)
    }
    
    // Function to emit menu state changes
    function updateMenuState() {
        menuStateChanged(fileMenuOpen, matlabSubmenuOpen, editMenuOpen)
    }
    
    // Bottom border
    Rectangle {
        width: parent.width
        height: 1
        color: "#dee2e6"
        anchors.bottom: parent.bottom
    }

    Row {
        id: menuRow
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        spacing: 20

        // File Menu
        Rectangle {
            id: fileMenuButton
            width: fileMenuText.width + 20
            height: 25
            color: fileMenuArea.containsMouse || topMenuComponent.fileMenuOpen ? "#d1d3d4" : "transparent"
            radius: 3

            Text {
                id: fileMenuText
                text: "File"
                anchors.centerIn: parent
                font.pixelSize: 12
                color: "#333"
            }

            MouseArea {
                id: fileMenuArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    console.log("File menu clicked, current state:", topMenuComponent.fileMenuOpen)
                    topMenuComponent.addSubmenuOpen = false
                    topMenuComponent.fileMenuOpen = !topMenuComponent.fileMenuOpen
                    if (topMenuComponent.fileMenuOpen) {
                        topMenuComponent.matlabSubmenuOpen = false
                        topMenuComponent.editMenuOpen = false
                        topMenuComponent.addSubmenuOpen = false
                    }
                    console.log("File menu new state:", topMenuComponent.fileMenuOpen)
                    topMenuComponent.menuStateChanged(topMenuComponent.fileMenuOpen, topMenuComponent.matlabSubmenuOpen, topMenuComponent.editMenuOpen)
                }
            }
        }

        // Edit Menu
        Rectangle {
            width: editMenuText.width + 20
            height: 25
            color: editMenuArea.containsMouse || topMenuComponent.editMenuOpen ? "#d1d3d4" : "transparent"
            radius: 3

            Text {
                id: editMenuText
                text: "Edit"
                anchors.centerIn: parent
                font.pixelSize: 12
                color: "#333"
            }

            MouseArea {
                id: editMenuArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    console.log("Edit menu clicked, current state:", topMenuComponent.editMenuOpen)
                    topMenuComponent.addSubmenuOpen = false
                    topMenuComponent.editMenuOpen = !topMenuComponent.editMenuOpen
                    if (topMenuComponent.editMenuOpen) {
                        topMenuComponent.fileMenuOpen = false
                        topMenuComponent.matlabSubmenuOpen = false
                    } else {
                        topMenuComponent.addSubmenuOpen = false
                    }
                    console.log("Edit menu new state:", topMenuComponent.editMenuOpen)
                    topMenuComponent.menuStateChanged(topMenuComponent.fileMenuOpen, topMenuComponent.matlabSubmenuOpen, topMenuComponent.editMenuOpen)
                }
            }

            // Edit Menu Dropdown
            Rectangle {
                id: editMenuDropdown
                x: 0
                y: parent.height + 2
                width: 180
                height: editMenuList.implicitHeight + 4
                color: "white"
                border.color: "#d0d0d0"
                border.width: 1
                radius: 6
                visible: topMenuComponent.editMenuOpen
                z: 10000

                // Simple shadow effect
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: -2
                    color: "transparent"
                    border.color: "#00000015"
                    border.width: 2
                    radius: 7
                    z: -1
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: -4
                    color: "transparent"
                    border.color: "#00000010"
                    border.width: 2
                    radius: 8
                    z: -2
                }

                Column {
                    id: editMenuList
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 2
                    spacing: 2

                    // Edit Mode Checkbox Item
                    Rectangle {
                        id: editModeItem
                        width: parent.width
                        height: 35
                        color: editModeArea.containsMouse ? "#e8e8e8" : "transparent"
                        radius: 4

                        Row {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8

                            // Checkbox
                            Rectangle {
                                width: 16
                                height: 16
                                anchors.verticalCenter: parent.verticalCenter
                                color: topMenuComponent.editModeChecked ? "#2196f3" : "white"
                                border.color: "#666"
                                border.width: 1
                                radius: 2

                                Text {
                                    text: topMenuComponent.editModeChecked ? "✓" : ""
                                    anchors.centerIn: parent
                                    font.pixelSize: 10
                                    color: "white"
                                    font.bold: true
                                }
                            }

                            Text {
                                text: "Edit Mode"
                                anchors.verticalCenter: parent.verticalCenter
                                font.pixelSize: 13
                                color: editModeArea.containsMouse ? "#1a1a1a" : "#333"
                                font.weight: editModeArea.containsMouse ? Font.Medium : Font.Normal
                            }
                        }

                        MouseArea {
                            id: editModeArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                topMenuComponent.editModeChecked = !topMenuComponent.editModeChecked
                                console.log("Edit mode toggled:", topMenuComponent.editModeChecked)
                                topMenuComponent.editModeToggled(topMenuComponent.editModeChecked)
                                topMenuComponent.editMenuOpen = false
                                topMenuComponent.addSubmenuOpen = false
                                topMenuComponent.menuStateChanged(topMenuComponent.fileMenuOpen, topMenuComponent.matlabSubmenuOpen, topMenuComponent.editMenuOpen)
                            }
                        }
                    }

                    // Add Button Item
                    Rectangle {
                        id: addMenuItem
                        width: parent.width
                        height: 35
                        color: (addButtonArea.containsMouse || topMenuComponent.addSubmenuOpen) ? "#e8e8e8" : "transparent"
                        radius: 4

                        Text {
                            id: addMenuLabel
                            text: "Add"
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            font.pixelSize: 13
                            color: (addButtonArea.containsMouse || topMenuComponent.addSubmenuOpen) ? "#1a1a1a" : "#333"
                            font.weight: (addButtonArea.containsMouse || topMenuComponent.addSubmenuOpen) ? Font.Medium : Font.Normal
                        }

                        Text {
                            text: "\u25B6"
                            font.pixelSize: 12
                            color: (addButtonArea.containsMouse || topMenuComponent.addSubmenuOpen) ? "#1a1a1a" : "#666"
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        MouseArea {
                            id: addButtonArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                topMenuComponent.matlabSubmenuOpen = false
                                topMenuComponent.addSubmenuOpen = !topMenuComponent.addSubmenuOpen
                            }
                        }
                    }
                }
            }
        }

        // View Menu
        Rectangle {
            width: viewMenuText.width + 20
            height: 25
            color: viewMenuArea.containsMouse ? "#d1d3d4" : "transparent"
            radius: 3

            Text {
                id: viewMenuText
                text: "View"
                anchors.centerIn: parent
                font.pixelSize: 12
                color: "#333"
            }

            MouseArea {
                id: viewMenuArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    console.log("View menu clicked")
                    // TODO: Implement view menu dropdown
                }
            }
        }

        // Tools Menu
        Rectangle {
            width: toolsMenuText.width + 20
            height: 25
            color: toolsMenuArea.containsMouse ? "#d1d3d4" : "transparent"
            radius: 3

            Text {
                id: toolsMenuText
                text: "Tools"
                anchors.centerIn: parent
                font.pixelSize: 12
                color: "#333"
            }

            MouseArea {
                id: toolsMenuArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    console.log("Tools menu clicked")
                    // TODO: Implement tools menu dropdown
                }
            }
        }

        // Help Menu
        Rectangle {
            width: helpMenuText.width + 20
            height: 25
            color: helpMenuArea.containsMouse ? "#d1d3d4" : "transparent"
            radius: 3

            Text {
                id: helpMenuText
                text: "Help"
                anchors.centerIn: parent
                font.pixelSize: 12
                color: "#333"
            }

            MouseArea {
                id: helpMenuArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    console.log("Help menu clicked")
                    // TODO: Implement help menu dropdown
                }
            }
        }
    }

    // File Menu Dropdown
    Rectangle {
        id: fileDropdownMenu
        x: menuRow.x + fileMenuButton.x
        y: parent.height
        width: 220
        height: 110
        color: "white"
        border.color: "#ccc"
        border.width: 1
        radius: 4
        visible: topMenuComponent.fileMenuOpen
        z: 10000

        // Drop shadow effect
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 2
            anchors.leftMargin: 2
            color: "#00000020"
            radius: 4
            z: -1
        }

        Column {
            anchors.fill: parent
            anchors.margins: 2

            // Add MATLAB function/script
            Rectangle {
                width: parent.width
                height: 35
                color: matlabFunctionMouseArea.containsMouse || topMenuComponent.matlabSubmenuOpen ? "#e8e8e8" : "transparent"
                radius: 4

                Row {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Text {
                        text: "Add MATLAB function/script..."
                        anchors.verticalCenter: parent.verticalCenter
                        font.pixelSize: 13
                        color: matlabFunctionMouseArea.containsMouse ? "#1a1a1a" : "#333"
                        font.weight: matlabFunctionMouseArea.containsMouse ? Font.Medium : Font.Normal
                    }
                }

                // Arrow indicator for submenu
                Text {
                    text: "\u25B6"
                    font.pixelSize: 12
                    color: "#666"
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                }

                MouseArea {
                    id: matlabFunctionMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        topMenuComponent.matlabSubmenuOpen = !topMenuComponent.matlabSubmenuOpen
                        topMenuComponent.updateMenuState()
                    }
                }
            }

            // Change FieldTrip path
            Rectangle {
                width: parent.width
                height: 35
                color: changeFieldtripMouseArea.containsMouse ? "#e8e8e8" : "transparent"
                radius: 4

                Row {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Text {
                        text: "Change FieldTrip path..."
                        anchors.verticalCenter: parent.verticalCenter
                        font.pixelSize: 13
                        color: changeFieldtripMouseArea.containsMouse ? "#1a1a1a" : "#333"
                        font.weight: changeFieldtripMouseArea.containsMouse ? Font.Medium : Font.Normal
                    }
                }

                MouseArea {
                    id: changeFieldtripMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        topMenuComponent.closeMenus()
                        topMenuComponent.fieldtripDialogRequested()
                    }
                }
            }

            // Change data path
            Rectangle {
                width: parent.width
                height: 35
                color: changeDataPathMouseArea.containsMouse ? "#e8e8e8" : "transparent"
                radius: 4

                Row {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Text {
                        text: "Change data path..."
                        anchors.verticalCenter: parent.verticalCenter
                        font.pixelSize: 13
                        color: changeDataPathMouseArea.containsMouse ? "#1a1a1a" : "#333"
                        font.weight: changeDataPathMouseArea.containsMouse ? Font.Medium : Font.Normal
                    }
                }

                MouseArea {
                    id: changeDataPathMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        topMenuComponent.closeMenus()
                        topMenuComponent.folderDialogRequested()
                    }
                }
            }
        }
    }

    // MATLAB Submenu
    Rectangle {
        id: matlabSubmenu
        x: fileDropdownMenu.x + fileDropdownMenu.width
        y: fileDropdownMenu.y
        width: 180
        height: 80
        color: "white"
        border.color: "#ccc"
        border.width: 1
        radius: 4
        visible: topMenuComponent.matlabSubmenuOpen && topMenuComponent.fileMenuOpen
    z: topMenuComponent.z + 1

        // Drop shadow effect
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 2
            anchors.leftMargin: 2
            color: "#00000020"
            radius: 4
            z: -1
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: {
                // Prevent closing when clicking inside submenu
            }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 2

            // Create function
            Rectangle {
                width: parent.width
                height: 35
                color: createFunctionMouseArea.containsMouse ? "#e8e8e8" : "transparent"
                radius: 4

                Row {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Text {
                        text: "Function"
                        anchors.verticalCenter: parent.verticalCenter
                        font.pixelSize: 13
                        color: createFunctionMouseArea.containsMouse ? "#1a1a1a" : "#333"
                        font.weight: createFunctionMouseArea.containsMouse ? Font.Medium : Font.Normal
                    }
                }

                MouseArea {
                    id: createFunctionMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        topMenuComponent.closeMenus()
                        topMenuComponent.createFunctionRequested()
                    }
                }
            }

            // Create script
            Rectangle {
                width: parent.width
                height: 35
                color: createScriptMouseArea.containsMouse ? "#e8e8e8" : "transparent"
                radius: 4

                Row {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Text {
                        text: "Script"
                        anchors.verticalCenter: parent.verticalCenter
                        font.pixelSize: 13
                        color: createScriptMouseArea.containsMouse ? "#1a1a1a" : "#333"
                        font.weight: createScriptMouseArea.containsMouse ? Font.Medium : Font.Normal
                    }
                }

                MouseArea {
                    id: createScriptMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        topMenuComponent.closeMenus()
                        topMenuComponent.createScriptRequested()
                    }
                }
            }
        }
    }

    // Add Submenu
    Rectangle {
        id: addSubmenu
    property int submenuHorizontalPadding: 1
        function reposition() {
            if (!addMenuItem)
                return;

            var topLeft = addMenuItem.mapToItem(topMenuComponent, 0, 0);
            var rightEdge = addMenuItem.mapToItem(topMenuComponent, addMenuItem.width, 0);
            x = rightEdge.x + submenuHorizontalPadding;
            y = topLeft.y;
        }
        onVisibleChanged: {
            if (visible)
                reposition();
        }
        width: 180
        height: 80
        color: "white"
        border.color: "#ccc"
        border.width: 1
        radius: 4
        visible: topMenuComponent.addSubmenuOpen && topMenuComponent.editMenuOpen
    z: topMenuComponent.z + 2

        Connections {
            target: addMenuItem
            function onWidthChanged() {
                if (addSubmenu.visible)
                    addSubmenu.reposition();
            }
            function onHeightChanged() {
                if (addSubmenu.visible)
                    addSubmenu.reposition();
            }
            function onXChanged() {
                if (addSubmenu.visible)
                    addSubmenu.reposition();
            }
            function onYChanged() {
                if (addSubmenu.visible)
                    addSubmenu.reposition();
            }
        }

        // Drop shadow effect
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 2
            anchors.leftMargin: 2
            color: "#00000020"
            radius: 4
            z: -1
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: {
                // Prevent closing when clicking inside submenu
            }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 2

            Rectangle {
                width: parent.width
                height: 35
                color: addDropdownArea.containsMouse ? "#e8e8e8" : "transparent"
                radius: 4

                Text {
                    text: "Dropdown Menu"
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    font.pixelSize: 12
                    color: addDropdownArea.containsMouse ? "#1a1a1a" : "#333"
                    font.weight: addDropdownArea.containsMouse ? Font.Medium : Font.Normal
                }

                MouseArea {
                    id: addDropdownArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        console.log("Add submenu - Dropdown Menu selected")
                        topMenuComponent.closeMenus()
                        topMenuComponent.addDropdownRequested()
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 35
                color: addRangeSliderArea.containsMouse ? "#e8e8e8" : "transparent"
                radius: 4

                Text {
                    text: "Range Slider"
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    font.pixelSize: 12
                    color: addRangeSliderArea.containsMouse ? "#1a1a1a" : "#333"
                    font.weight: addRangeSliderArea.containsMouse ? Font.Medium : Font.Normal
                }

                MouseArea {
                    id: addRangeSliderArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        console.log("Add submenu - Range Slider selected")
                        topMenuComponent.closeMenus()
                        topMenuComponent.addRangeSliderRequested()
                    }
                }
            }
        }
    }
}