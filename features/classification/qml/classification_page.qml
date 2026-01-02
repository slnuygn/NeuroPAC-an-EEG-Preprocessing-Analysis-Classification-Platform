import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
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
    
    Connections {
        target: classificationController
        function onLogReceived(message) {
            console.log("Controller Log: " + message)
        }
        function onTrainingFinished() {
            console.log("Training finished signal received.")
        }
    }

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

    // Sync selected folder from FileBrowser to controller
    Connections {
        target: fileExplorerRect
        function onDataDirectoryUpdateRequested(path) {
            classificationController.setDataFolder(path)
        }
        function onFolderChanged(folder) {
            classificationController.setDataFolder(folder)
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
                    displayText: "EEGNet Classifier"
                    classifierName: "EEGNet"
                    currentFolderContents: fileExplorerRect.folderContents
                    currentFolderPath: fileExplorerRect.currentFolder
                    subjectListModel: fileExplorerRect.labelListModel
                    onClassifyClicked: function(classifier, analysis, selectedClasses, configParams) {
                        console.log("Requesting " + classifier + " classification with " + analysis)
                        console.log("Selected classes:", selectedClasses)
                        classificationController.startClassification(classifier, analysis, selectedClasses, configParams)
                    }
                    onTestClassifierClicked: function(classifier, analysis, weightsPath) {
                        console.log("Testing " + classifier + " with analysis " + analysis + " using weights: " + weightsPath)
                        classificationController.testClassifier(classifier, analysis, weightsPath)
                    }
                }

                ClassifierTemplate {
                    displayText: "EEG-Inception Classifier"
                    classifierName: "EEG-Inception"
                    currentFolderContents: fileExplorerRect.folderContents
                    currentFolderPath: fileExplorerRect.currentFolder
                    subjectListModel: fileExplorerRect.labelListModel
                    onClassifyClicked: function(classifier, analysis, selectedClasses, configParams) {
                        console.log("Requesting " + classifier + " classification with " + analysis)
                        console.log("Selected classes:", selectedClasses)
                        classificationController.startClassification(classifier, analysis, selectedClasses, configParams)
                    }
                    onTestClassifierClicked: function(classifier, analysis, weightsPath) {
                        console.log("Testing " + classifier + " with analysis " + analysis + " using weights: " + weightsPath)
                        classificationController.testClassifier(classifier, analysis, weightsPath)
                    }
                }

                ClassifierTemplate {
                    displayText: "Riemannian Classifier"
                    classifierName: "Riemannian"
                    currentFolderContents: fileExplorerRect.folderContents
                    currentFolderPath: fileExplorerRect.currentFolder
                    subjectListModel: fileExplorerRect.labelListModel
                    onClassifyClicked: function(classifier, analysis, selectedClasses, configParams) {
                        console.log("Requesting " + classifier + " classification with " + analysis)
                        console.log("Selected classes:", selectedClasses)
                        classificationController.startClassification(classifier, analysis, selectedClasses, configParams)
                    }
                    onTestClassifierClicked: function(classifier, analysis, weightsPath) {
                        console.log("Testing " + classifier + " with analysis " + analysis + " using weights: " + weightsPath)
                        classificationController.testClassifier(classifier, analysis, weightsPath)
                    }
                }

            }
        }
    }
}
