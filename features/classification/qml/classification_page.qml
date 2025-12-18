import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import "."
import "../../preprocessing/qml"
import "../../../ui"

Item {
    id: classificationPageRoot
    anchors.fill: parent
    anchors.margins: 10
    
    property bool editModeEnabled: false
    property string currentFolder: ""
    property var folderContents: []
    
    // Signals to communicate with main.qml
    signal openFolderDialog()
    signal refreshFileExplorer()

    // Model for the label window contents
    ListModel {
        id: labelListModel
    }
    
    // Loading indicator
    property bool isLoadingLabels: false
    
    // File Explorer Rectangle - Left side
    FileBrowserUI {
        id: fileExplorerRect
        anchors.left: parent.left
        anchors.top: parent.top
        width: parent.width * 0.2
        height: parent.height
        isLoadingLabels: classificationPageRoot.isLoadingLabels
    }

    // Populate label window when the file browser reports a data.mat click
    Connections {
        target: fileExplorerRect
        function onFileMatClicked(fileName, fullPath, displayName) {
            labelListModel.clear()
            isLoadingLabels = true

            // Normalize path separators
            var fp = fullPath.replace(/\\/g, '/')

            // Use Python method to get dataset names
            try {
                var datasetNames = matlabExecutor.listMatDatasets(fp)
                isLoadingLabels = false
                if (datasetNames && datasetNames.length > 0) {
                    for (var i = 0; i < datasetNames.length; ++i) {
                        labelListModel.append({"text": datasetNames[i]})
                    }
                } else {
                    labelListModel.append({"text": displayName || fileName})
                }
            } catch (e) {
                isLoadingLabels = false
                console.log('Error calling matlabExecutor.listMatDatasets:', e)
                labelListModel.append({"text": displayName || fileName})
            }
        }
    }

    // Right side - Classifiers Area with Scrolling
    Rectangle {
        anchors.left: fileExplorerRect.right
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 10
        anchors.rightMargin: 5
        color: "transparent"
        
        ScrollView {
            id: scrollArea
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth

            Column {
                width: scrollArea.availableWidth
                spacing: 1

                    

                ClassifierTemplate {
                    displayText: "CNN Classifier"
                }

                ClassifierTemplate {
                    displayText: "RNN Classifier"
                }

                ClassifierTemplate {
                    displayText: "SVM Classifier"
                }

                ClassifierTemplate {
                    displayText: "KNN Classifier"
                }

                ClassifierTemplate {
                    displayText: "LSTM Classifier"
                }
            }
        }
    }
}
