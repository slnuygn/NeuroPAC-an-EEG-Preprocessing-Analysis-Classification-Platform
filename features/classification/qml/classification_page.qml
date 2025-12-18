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
    
    // Global properties for label persistence
    property var globalLabelListModel
    property bool globalIsLoadingLabels
    signal loadingStateChanged(bool loading)
    
    // Signals to communicate with main.qml
    signal openFolderDialog()
    signal refreshFileExplorer()
    
    // File Explorer Rectangle - Left side
    FileBrowserUI {
        id: fileExplorerRect
        anchors.left: parent.left
        anchors.top: parent.top
        width: parent.width * 0.2
        height: parent.height
        
        labelListModel: globalLabelListModel
        isLoadingLabels: globalIsLoadingLabels
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
