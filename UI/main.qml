import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs
import MatlabExecutor 1.0
import FileBrowser 1.0
import "../features/preprocessing/qml/"

ApplicationWindow {
    id: window
    visible: true
    width: 600
    height: 500
    title: "NeuroPAC: Preprocessing and Analysis Console"

    // Property to hold MATLAB output
    property string matlabOutput: "Click 'Run MATLAB' to execute script"
    property string saveMessage: ""
    property string fieldtripPath: ""
    
    // Global model for label data persistence across pages
    ListModel {
        id: globalLabelListModel
    }
    property bool globalIsLoadingLabels: false
    
    // FileBrowser component (Hidden, used for dialogs and logic)
    FileBrowserUI {
        id: fileBrowserComponent
        visible: false
    }
    
    // Connections for FileBrowser component
    Connections {
        target: fileBrowserComponent
        function onFieldtripPathRequested() {
            window.fileMenuOpen = false
            window.matlabSubmenuOpen = false
        }
        
        function onDataDirectoryUpdateRequested(path) {
            if (matlabExecutor) {
                matlabExecutor.updateDataDirectory(path)
            }
        }
        
        function onFieldtripPathUpdateRequested(path) {
            if (matlabExecutor) {
                matlabExecutor.updateFieldtripPath(path)
            }
        }
    }

    // Connect to the matlabExecutor signal
    Connections {
        target: matlabExecutor
        function onOutputChanged(output) {
            window.matlabOutput = output
        }
        function onConfigSaved(message) {
            window.saveMessage = message
            saveMessageTimer.start()
            // Refresh FieldTrip path display if updated
            if (message.includes("FieldTrip path updated")) {
                fieldtripPathRefreshTimer.start()
            }
        }

    }

    // JavaScript functions for channel selection
    function isChannelSelected(channel) {
        return channelPopup.selectedChannels.indexOf(channel) !== -1
    }

    function isAllSelected() {
        return channelPopup.selectedChannels.length === channelPopup.allChannels.length
    }

    function toggleChannel(channel) {
        var index = channelPopup.selectedChannels.indexOf(channel)
        var newSelection = channelPopup.selectedChannels.slice() // Create a copy
        if (index !== -1) {
            newSelection.splice(index, 1)
        } else {
            newSelection.push(channel)
        }
        channelPopup.selectedChannels = newSelection // Reassign to trigger property change
    }

    function getSelectedChannelsText() {
        if (channelPopup.selectedChannels.length === 0) {
            return "None"
        } else if (channelPopup.selectedChannels.length <= 3) {
            return channelPopup.selectedChannels.join(", ")
        } else {
            return channelPopup.selectedChannels.slice(0, 3).join(", ") + "... (" + channelPopup.selectedChannels.length + " total)"
        }
    }

    function getSelectedChannelsCount() {
        return channelPopup.selectedChannels.length.toString()
    }

    // Timer to clear save message after a few seconds
    Timer {
        id: saveMessageTimer
        interval: 3000
        onTriggered: window.saveMessage = ""
    }

    // Timer to refresh FieldTrip path display
    Timer {
        id: fieldtripPathRefreshTimer
        interval: 200
        onTriggered: {
            if (matlabExecutor) {
                window.fieldtripPath = matlabExecutor.getCurrentFieldtripPath()
            }
        }
    }





    // Top Menu Bar
    TopMenu {
        id: topMenuBar
        width: parent.width
        
        onFieldtripDialogRequested: {
            fileBrowserComponent.fieldtripDialog.open()
        }
        
        onFolderDialogRequested: {
            fileBrowserComponent.folderDialog.open()
        }
        
        onCreateFunctionRequested: {
            console.log("Create function requested")
            // TODO: Implement function creation
        }
        
        onCreateScriptRequested: {
            console.log("Create script requested")
            // TODO: Implement script creation
        }
        
        onEditModeToggled: function(checked) {
            console.log("Edit mode toggled:", checked)
            // Forward to preprocessing page
            if (preprocessingPageLoader.item) {
                preprocessingPageLoader.item.setEditMode(checked)
            }
            if (featureExtractionAnalysisPageLoader.item && featureExtractionAnalysisPageLoader.item.setEditMode) {
                featureExtractionAnalysisPageLoader.item.setEditMode(checked)
            }
        }

        onAddDropdownRequested: {
            if (preprocessingPageLoader.item && preprocessingPageLoader.item.addDropdownTemplate) {
                preprocessingPageLoader.item.addDropdownTemplate()
            }
        }

        onAddRangeSliderRequested: {
            if (preprocessingPageLoader.item && preprocessingPageLoader.item.addRangeSliderTemplate) {
                preprocessingPageLoader.item.addRangeSliderTemplate()
            }
        }
    }

    // MouseArea to close menus when clicking outside
    MouseArea {
        anchors.fill: parent
        anchors.topMargin: topMenuBar.height
        z: -10
        onClicked: {
            topMenuBar.closeMenus()
        }
        
        // Allow scroll events to pass through to underlying ScrollView
        propagateComposedEvents: true
        
        onWheel: function(wheel) {
            wheel.accepted = false  // Let the ScrollView handle wheel events
        }
    }

    // Tab bar at the top
    Rectangle {
        id: tabBar
        anchors.top: topMenuBar.bottom
        width: parent.width
        height: 40
        color: "#e0e0e0"

        // Top border only
        Rectangle {
            width: parent.width
            height: 1
            color: "#e0e0e0"
            anchors.top: parent.top
        }

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 5
            anchors.top: parent.top
            anchors.topMargin: 2  // Start below the top border
            height: parent.height - 2  // Adjust height to account for border

            // Tab 1 - Preprocessing
            Rectangle {
                id: preprocessingTab
                width: preprocessingText.implicitWidth + 20
                height: parent.height
                color: contentArea.currentIndex === 0 ? "white" : "#e0e0e0"

                Text {
                    id: preprocessingText
                    text: "Preprocessing"
                    anchors.centerIn: parent
                    font.pixelSize: 14
                    color: "#333"
                    
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: contentArea.currentIndex = 0
                }
            }

            // Tab 2 - Feature Extraction Analysis
            Rectangle {
                id: featureExtractionAnalysisTab
                width: featureExtractionText.implicitWidth + 20
                height: parent.height
                color: contentArea.currentIndex === 1 ? "white" : "#e0e0e0"

                Text {
                    id: featureExtractionText
                    text: "Feature Extraction Analysis"
                    anchors.centerIn: parent
                    font.pixelSize: 14
                    color: "#333"
                    
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: contentArea.currentIndex = 1
                }
            }

            // Tab 3 - Classification
            Rectangle {
                id: classificationTab
                width: classificationText.implicitWidth + 20
                height: parent.height
                color: contentArea.currentIndex === 2 ? "white" : "#e0e0e0"

                Text {
                    id: classificationText
                    text: "Classification"
                    anchors.centerIn: parent
                    font.pixelSize: 14
                    color: "#333"
                    
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: contentArea.currentIndex = 2
                }
            }
        }
    }

    // Content area (window underneath)
    Rectangle {
        id: contentArea
        anchors.top: tabBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        color: "white"
        

        property int currentIndex: 0

        // Tab 1 Content - Preprocessing
        Item {
            id: preprocessingPage
            anchors.fill: parent
            visible: contentArea.currentIndex === 0

            Loader {
                id: preprocessingPageLoader
                anchors.fill: parent
                source: "../features/preprocessing/qml/preprocessing_page.qml"
                
                onLoaded: {
                    item.currentFolder = Qt.binding(function() { return fileBrowserComponent.currentFolder })
                    item.folderContents = Qt.binding(function() { return fileBrowserComponent.folderContents })
                    item.fieldtripPath = Qt.binding(function() { return window.fieldtripPath })
                    item.saveMessage = Qt.binding(function() { return window.saveMessage })
                    
                    // Set global label model for persistence across pages
                    item.globalLabelListModel = globalLabelListModel
                    item.globalIsLoadingLabels = Qt.binding(function() { return window.globalIsLoadingLabels })
                    item.loadingStateChanged.connect(function(loading) {
                        window.globalIsLoadingLabels = loading
                    })
                    
                    // Initialize eventvalue dropdown with current values from MATLAB file
                    if (matlabExecutor) {
                        var currentEventvalues = matlabExecutor.getCurrentEventvalue()
                        item.setInitialEventvalues(currentEventvalues)
                        
                        // Initialize channels with current values from CTL_preprocessing.m
                        var currentChannels = matlabExecutor.getCurrentChannels()
                        item.setInitialChannels(currentChannels)
                        
                        // Initialize demean settings from prep_data.m
                        var currentDemean = matlabExecutor.getCurrentDemean()
                        var currentBaseline = matlabExecutor.getCurrentBaselineWindow()
                        item.setInitialDemean(currentDemean, currentBaseline)
                        
                        // Initialize DFT filter settings from prep_data.m
                        var currentDftfilter = matlabExecutor.getCurrentDftfilter()
                        var currentDftfreq = matlabExecutor.getCurrentDftfreq()
                        item.setInitialDftfilter(currentDftfilter, currentDftfreq)
                    }
                    
                    item.openFolderDialog.connect(function() { fileBrowserComponent.folderDialog.open() })
                    item.openFieldtripDialog.connect(function() { fileBrowserComponent.fieldtripDialog.open() })
                    item.requestSaveConfiguration.connect(function(prestimValue, poststimValue, trialfunValue, eventtypeValue, selectedChannels, selectedEventvalues, demeanEnabled, baselineStart, baselineEnd, dftfilterEnabled, dftfreqStart, dftfreqEnd) {
                        matlabExecutor.saveConfiguration(prestimValue, poststimValue, trialfunValue, eventtypeValue, selectedChannels, selectedEventvalues, demeanEnabled, baselineStart, baselineEnd, dftfilterEnabled, dftfreqStart, dftfreqEnd)
                    })
                    item.refreshFileExplorer.connect(function() { 
                        fileBrowserComponent.refreshFolderContents()
                    })
                }
            }
        }

        // Tab 2 Content - Feature Extraction Analysis
        Item {
            id: featureExtractionAnalysisPage
            anchors.fill: parent
            visible: contentArea.currentIndex === 1

            Loader {
                id: featureExtractionAnalysisPageLoader
                anchors.fill: parent
                source: "../features/analysis/qml/processing_page.qml"

                onLoaded: {
                    console.log("Processing page loaded successfully")
                    
                    // Bind fileBrowser properties
                    if (item) {
                        item.currentFolder = Qt.binding(function() { return fileBrowserComponent.currentFolder })
                        item.folderContents = Qt.binding(function() { return fileBrowserComponent.folderContents })
                        
                        // Set global label model for persistence across pages
                        item.globalLabelListModel = globalLabelListModel
                        item.globalIsLoadingLabels = Qt.binding(function() { return window.globalIsLoadingLabels })
                        item.loadingStateChanged.connect(function(loading) {
                            window.globalIsLoadingLabels = loading
                        })
                        
                        // Connect signals
                        item.openFolderDialog.connect(function() { fileBrowserComponent.folderDialog.open() })
                        item.refreshFileExplorer.connect(function() { 
                            fileBrowserComponent.refreshFolderContents()
                        })
                    }
                }

                onStatusChanged: {
                    if (status === Loader.Error) {
                        console.log("Error loading processing_page.qml:", source)
                    } else if (status === Loader.Ready) {
                        console.log("Processing page ready")
                    } else if (status === Loader.Loading) {
                        console.log("Loading processing page...")
                    }
                }
            }
        }

        // Tab 3 Content - Classification
        Item {
            id: classificationPage
            anchors.fill: parent
            visible: contentArea.currentIndex === 2

            Loader {
                id: classificationPageLoader
                anchors.fill: parent
                source: "../features/classification/qml/classification_page.qml"

                onLoaded: {
                    console.log("Classification page loaded successfully")
                    
                    // Bind fileBrowser properties
                    if (item) {
                        item.currentFolder = Qt.binding(function() { return fileBrowserComponent.currentFolder })
                        item.folderContents = Qt.binding(function() { return fileBrowserComponent.folderContents })
                        
                        // Set global label model for persistence across pages
                        item.globalLabelListModel = globalLabelListModel
                        item.globalIsLoadingLabels = Qt.binding(function() { return window.globalIsLoadingLabels })
                        item.loadingStateChanged.connect(function(loading) {
                            window.globalIsLoadingLabels = loading
                        })
                        
                        // Connect signals
                        item.openFolderDialog.connect(function() { fileBrowserComponent.folderDialog.open() })
                        item.refreshFileExplorer.connect(function() { 
                            fileBrowserComponent.refreshFolderContents()
                        })
                    }
                }

                onStatusChanged: {
                    if (status === Loader.Error) {
                        console.log("Error loading classification_page.qml:", source)
                    } else if (status === Loader.Ready) {
                        console.log("Classification page ready")
                    } else if (status === Loader.Loading) {
                        console.log("Loading classification page...")
                    }
                }
            }
        }
    }

}
