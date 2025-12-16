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
    
    // File Explorer Rectangle - Left side
    FileBrowserUI {
        id: fileExplorerRect
        anchors.left: parent.left
        anchors.top: parent.top
        width: parent.width * 0.2
        height: parent.height
    }

    // Populate label window when the file browser reports a data.mat click
    Connections {
        target: fileExplorerRect
        function onFileMatClicked(fileName, fullPath, displayName) {
            labelListModel.clear()

            // Normalize path separators
            var fp = fullPath.replace(/\\/g, '/')

            // Request dataset names for struct `data` and extract the last path segment via fileparts
            var matlabCmdRows = "tmp=load('" + fp + "'); if isfield(tmp,'data'), d=tmp.data; else d=[]; end; "
            matlabCmdRows += "if isstruct(d), for i=1:min(numel(d),10000), nm=''; try if isfield(d(i),'cfg') && isfield(d(i).cfg,'dataset'), v=d(i).cfg.dataset; if isstring(v)||ischar(v), s=char(string(v)); [~,nm2,~]=fileparts(s); nm=nm2; elseif isnumeric(v), nm=num2str(v); else nm='<nonstring>'; end; end; catch, nm='<err>'; end; disp(nm); end; else disp('NOT_STRUCT'); end"

            try {
                var result = matlabExecutor.runMatlabScript(matlabCmdRows)
                if (result) {
                    var out = result.replace(/^MATLAB Output:\s*\r?\n/, '')
                    var lines = out.split(/\r?\n/)
                    // If MATLAB signaled NOT_STRUCT, fall back
                    if (lines.length === 1 && lines[0].trim() === 'NOT_STRUCT') {
                        labelListModel.append({"text": displayName || fileName})
                    } else {
                        for (var i = 0; i < lines.length; ++i) {
                            var line = lines[i].trim()
                            if (line) labelListModel.append({"text": line})
                        }
                    }
                    if (labelListModel.count === 0) {
                        labelListModel.append({"text": displayName || fileName})
                    }
                } else {
                    labelListModel.append({"text": displayName || fileName})
                }
            } catch (e) {
                console.log('Error calling matlabExecutor for rows:', e)
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
