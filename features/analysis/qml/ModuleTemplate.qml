import QtQuick 2.15
import QtQuick.Window 2.15

Item {
    id: moduleTemplate
    width: parent.width
    height: rectangle.height + 4 + (expanded ? expandedRect.height + 2 : 0)
    z: 1000

    property string displayText: "Analysis Module"
    property bool expanded: false
    property string currentFolder: ""
    property var folderContents: []
    property string errorMessage: ""
    property string moduleName: ""  // Name used to find corresponding MATLAB file
    property bool editModeEnabled: false  // Track edit mode state
    property var dropdownOptions: ({})
    signal buttonClicked()
    default property alias expandedContent: contentContainer.data

    // Dynamic parameters loaded from MATLAB file
    property var dynamicParameters: ({})

    // Load parameters when module name is set
    Component.onCompleted: loadDropdownOptions

    onModuleNameChanged: {
        if (moduleName && moduleName !== "") {
            loadDropdownOptions()
            loadDynamicParameters()
        }
    }

    function loadDropdownOptions() {
        if (dropdownOptions && Object.keys(dropdownOptions).length > 0)
            return

        var optionsPath = Qt.resolvedUrl("../../../config/analysis_dropdown_options.json")
        var xhr = new XMLHttpRequest()
        try {
            xhr.open("GET", optionsPath, false)
            xhr.send()
            if (xhr.status === 200 && xhr.responseText.length > 0) {
                var payload = JSON.parse(xhr.responseText)
                dropdownOptions = payload && payload.parameters ? payload.parameters : {}
            } else {
                console.warn("Dropdown options file missing or unreadable", optionsPath)
            }
        } catch (error) {
            console.warn("Failed to load dropdown options:", error)
        }
    }

    function getDropdownOptionEntry(paramName) {
        if (!dropdownOptions)
            return null

        var normalized = (paramName || "").toLowerCase()
        var entry = dropdownOptions[normalized]
        if (!entry)
            return null

        if (entry.modules && entry.modules.length > 0 && entry.modules.indexOf(moduleName) === -1)
            return null

        return entry
    }

    function applyDropdownOptionOverrides(config, paramName, currentValue) {
        if (!config || config.component_type !== 'DropdownTemplate')
            return

        var entry = getDropdownOptionEntry(paramName)
        if (!entry)
            return

        var optionList = entry.options ? entry.options.slice() : []
        if (currentValue && optionList.indexOf(currentValue) === -1)
            optionList.unshift(currentValue)

        if (optionList.length > 0) {
            config.model = optionList.slice()
            if (config.is_multi_select) {
                config.all_items = optionList.slice()
                if (!config.selected_items || config.selected_items.length === 0)
                    config.selected_items = currentValue ? [currentValue] : []
            } else {
                config.current_index = Math.max(0, optionList.indexOf(currentValue))
            }
        }

        if (entry.has_add_feature !== undefined)
            config.has_add_feature = entry.has_add_feature
        if (entry.is_multi_select !== undefined)
            config.is_multi_select = entry.is_multi_select
        if (entry.max_selections !== undefined)
            config.max_selections = entry.max_selections
    }

    function applyRangeSliderOverrides(config, paramName) {
        if (!config || config.component_type !== 'RangeSliderTemplate')
            return

        var entry = getDropdownOptionEntry(paramName)
        if (!entry)
            return

        if (entry.min !== undefined) {
            config.from = entry.min
            // Ensure selection is within bounds
            if (config.first_value < config.from) config.first_value = config.from
            if (config.second_value < config.from) config.second_value = config.from
        }
        
        if (entry.max !== undefined) {
            config.to = entry.max
            // Ensure selection is within bounds
            if (config.first_value > config.to) config.first_value = config.to
            if (config.second_value > config.to) config.second_value = config.to
        }
    }

    function loadDynamicParameters() {
        // Parse MATLAB file directly
        var matlabFile = getMatlabFilePath(moduleName);
        if (matlabFile) {
            parseMatlabFile(matlabFile);
        }
    }

    function getMatlabFilePath(moduleName) {
        // Map module names to MATLAB file paths (relative to this QML file)
        var moduleMap = {
            "ERP Analysis": "../matlab/ERP/timelock_func.m",
            "Time-Frequency Analysis": "../matlab/timefrequency/timefreqanalysis.m",
            "Inter-Trial Coherence Analysis": "../matlab/connectivity/intertrial/intertrialcoherenceanalysis.m",
            "Channel-Wise Coherence Analysis": "../matlab/connectivity/channelwise/channelwise.m",
            "Spectral Analysis": "../matlab/spectral/spectralanalysis.m"
        };
        return moduleMap[moduleName] || "";
    }

    function parseMatlabFile(filePath) {
        // Read the MATLAB file
        var xhr = new XMLHttpRequest();
        xhr.open("GET", filePath, true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                var content = xhr.responseText;
                dynamicParameters = parseCfgParameters(content);
                console.log("Parsed parameters for " + moduleName + ":", Object.keys(dynamicParameters).length);
            }
        };
        xhr.send();
    }

    function parseCfgParameters(content) {
        var parameters = {};
        var lines = content.split('\n');

        // Look for cfg.xxx = ... patterns
        var cfgPattern = /cfg\.(\w+)\s*=\s*(.+);/g;
        var match;

        while ((match = cfgPattern.exec(content)) !== null) {
            var paramName = match[1];
            var paramValue = match[2].trim();

            // Skip if already processed
            if (parameters[paramName]) continue;

            parameters[paramName] = createParameterConfig(paramName, paramValue);
        }

        return parameters;
    }

    function createParameterConfig(paramName, paramValue) {
        var config = {
            'parameter_name': paramName,
            'matlab_property': 'cfg.' + paramName
        };

        // Check if it's a range [x y]
        if (paramValue.startsWith('[') && paramValue.endsWith(']')) {
            var values = paramValue.slice(1, -1).trim().split(/\s+/);
            if (values.length >= 2) {
                var from = parseFloat(values[0]);
                var to = parseFloat(values[1]);
                if (!isNaN(from) && !isNaN(to)) {
                    config.component_type = 'RangeSliderTemplate';
                    config.label = paramName.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
                    config.from = from;
                    config.to = to;
                    config.first_value = from;
                    config.second_value = to;
                    config.step_size = 0.1;
                    config.unit = paramName.toLowerCase().includes('latency') ? 'ms' : '';
                    config.width_factor = 0.1;
                    config.background_color = 'white';
                    applyRangeSliderOverrides(config, paramName);
                }
            }
        }
        // Check if it's MATLAB colon syntax (start:step:end or start:end)
        else if (/^-?\d+(\.\d+)?\s*:\s*-?\d+(\.\d+)?\s*(:\s*-?\d+(\.\d+)?)?$/.test(paramValue.trim())) {
            var colonParts = paramValue.trim().split(':');
            if (colonParts.length >= 2 && colonParts.length <= 3) {
                var start = parseFloat(colonParts[0]);
                var step = colonParts.length === 3 ? parseFloat(colonParts[1]) : 1.0;
                var end = parseFloat(colonParts[colonParts.length - 1]);

                if (!isNaN(start) && !isNaN(step) && !isNaN(end)) {
                    config.component_type = 'StepRangeSliderTemplate';
                    config.label = paramName.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
                    // Calculate appropriate range bounds (extend a bit beyond the actual range)
                    var range = end - start;
                    config.from = start - range * 0.1; // 10% below start
                    config.to = end + range * 0.1;    // 10% above end
                    config.first_value = start;
                    config.second_value = end;
                    config.step_size = step;
                    config.unit = paramName.toLowerCase().includes('time') || paramName.toLowerCase().includes('toi') ? 's' :
                                 paramName.toLowerCase().includes('freq') || paramName.toLowerCase().includes('foi') ? 'Hz' : '';
                    config.width_factor = 0.1;
                    config.background_color = 'white';
                }
            }
        }
        // Check if it's a cell array {'a' 'b'}
        else if (paramValue.startsWith('{') && paramValue.endsWith('}')) {
            config.component_type = 'DropdownTemplate';
            config.label = paramName.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
            
            // Extract strings from cell array
            var options = [];
            var stringPattern = /['"]([^'"]+)['"]/g;
            var match;
            while ((match = stringPattern.exec(paramValue)) !== null) {
                options.push(match[1]);
            }
            
            config.model = options;
            config.current_index = 0;
            config.has_add_feature = false;
            config.is_multi_select = true;
            config.selected_items = options;
            config.all_items = options;

            // Try to merge with JSON options if available
            var entry = getDropdownOptionEntry(paramName);
            if (entry && entry.options) {
                var jsonOptions = entry.options.slice();
                // Add any file options that aren't in JSON
                for (var i = 0; i < options.length; i++) {
                    if (jsonOptions.indexOf(options[i]) === -1) {
                        jsonOptions.push(options[i]);
                    }
                }
                config.model = jsonOptions;
                config.all_items = jsonOptions;
                
                if (entry.has_add_feature !== undefined) config.has_add_feature = entry.has_add_feature;
                if (entry.max_selections !== undefined) config.max_selections = entry.max_selections;
            }
        }
        // Check if it's a string 'value'
        else if ((paramValue.startsWith("'") && paramValue.endsWith("'")) ||
                 (paramValue.startsWith('"') && paramValue.endsWith('"'))) {
            var stringValue = paramValue.slice(1, -1);
            var lowerValue = stringValue.toLowerCase();

            // Check for boolean values
            if (lowerValue === 'yes' || lowerValue === 'no' || lowerValue === 'true' || lowerValue === 'false') {
                config.component_type = 'CheckBoxTemplate';
                config.label = paramName.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
                config.checked = (lowerValue === 'yes' || lowerValue === 'true');
            } else {
                config.component_type = 'DropdownTemplate';
                config.label = paramName.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
                config.model = [stringValue];
                config.current_index = 0;
                config.has_add_feature = false;
                config.is_multi_select = false;
                applyDropdownOptionOverrides(config, paramName, stringValue);
            }
        }
        // Check if it's a number
        else if (!isNaN(parseFloat(paramValue))) {
            // For now, treat numbers as dropdowns with single option
            config.component_type = 'DropdownTemplate';
            config.label = paramName.replace(/_/g, ' ').replace(/\b\w/g, function(l) { return l.toUpperCase(); });
            config.model = [paramValue];
            config.current_index = 0;
            config.has_add_feature = false;
            config.is_multi_select = false;
            applyDropdownOptionOverrides(config, paramName, paramValue);
        }

        return config;
    }    // Function to validate if target file exists in folder
    function validateTargetFile() {
        var targetFileName = "data_ICApplied_clean.mat"
        
        if (!currentFolder) {
            errorMessage = "No folder selected"
            return false
        }
        
        var foundCleanMat = false
        for (var i = 0; i < folderContents.length; i++) {
            var rawEntry = folderContents[i]
            var sanitizedEntry = rawEntry.replace(/^[^\w]+/, '').trim()
            if (sanitizedEntry.toLowerCase() === targetFileName.toLowerCase()) {
                foundCleanMat = true
                break
            }
        }
        
        if (!foundCleanMat) {
            errorMessage = "data_ICApplied_clean.mat not found in the selected folder"
            return false
        }
        
        errorMessage = ""
        return true
    }

    MouseArea {
        anchors.fill: parent
        onClicked: expanded = !expanded
    }

    Rectangle {
        id: rectangle
        width: parent.width - 10
        height: text.implicitHeight + 10
        anchors.top: parent.top
        anchors.topMargin: 2
        anchors.horizontalCenter: parent.horizontalCenter
        color: "#f0f0f0"
        border.color: "#ccc"
        border.width: 1
        radius: 3

        Text {
            id: text
            text: displayText
            font.pixelSize: 24
            color: "#333"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
        }

        Text {
            id: arrow
            text: "▼"
            font.pixelSize: 12
            color: "#666"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.rightMargin: 10
        }
    }

    Rectangle {
        id: expandedRect
        visible: expanded
        width: parent.width - 10
        height: expanded ? Math.max(contentContainer.implicitHeight + 20, 120) : 0
        anchors.top: rectangle.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 1
        color: "#e0e0e0"
        border.color: "#ccc"
        border.width: 1
        radius: 3

        Column {
            id: contentContainer
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            spacing: 10

            // Dynamic parameters loaded from MATLAB file
            Repeater {
                model: Object.keys(dynamicParameters)
                delegate: DynamicParameterLoader {
                    width: contentContainer.width
                    parameterName: modelData
                    parameterConfig: dynamicParameters[modelData]
                    editModeEnabled: moduleTemplate.editModeEnabled
                    moduleName: moduleTemplate.moduleName

                    onParameterChanged: function(paramName, value) {
                        console.log("Parameter changed:", paramName, "=", value);
                        // TODO: Save parameter to MATLAB
                    }
                }
            }

            // Error text display - common for all modules
            Text {
                id: errorText
                text: ""
                color: "red"
                visible: text !== ""
                font.pixelSize: 12
                width: parent.width
            }
        }

        Item {
            width: parent.width - 20
            height: moduleButton.implicitHeight
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 10

            Button {
                id: moduleButton
                text: "Feature Extract"
                anchors.right: parent.right
                flat: true
                padding: 10
                background: Rectangle {
                    color: "#2196f3"
                    radius: 4
                    anchors.fill: parent
                }

                onClicked: {
                    moduleTemplate.buttonClicked()
                }
            }
        }
    }
}
