import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../preprocessing/ui"

Item {
    id: dynamicParameterLoader
    width: parent.width
    height: parameterComponentLoader.height

    property string parameterName: ""
    property var parameterConfig: ({})
    property bool editModeEnabled: false

    // MATLAB executor is available globally as matlabExecutor context property

    // Signal to notify when parameter value changes
    signal parameterChanged(string parameterName, var value)

    Loader {
        id: parameterComponentLoader
        width: parent.width / 3

        onLoaded: {
            if (parameterConfig.component_type === "DropdownTemplate" && parameterComponentLoader.item) {
                adjustDropdownIconAlignment(parameterComponentLoader.item)
            }
        }

        sourceComponent: {
            if (!parameterConfig || !parameterConfig.component_type) {
                return null;
            }

            switch (parameterConfig.component_type) {
                case "RangeSliderTemplate":
                    return rangeSliderComponent;
                case "DropdownTemplate":
                    return dropdownComponent;
                case "StepRangeSliderTemplate":
                    return stepRangeSliderComponent;
                default:
                    return null;
            }
        }
    }

    // Align dropdown action icons with the actual visible display rectangle so
    // they stay centered even when rendered via nested loaders.
    function adjustDropdownIconAlignment(dropdownItem) {
        if (!dropdownItem || !dropdownItem.children || dropdownItem.children.length < 2)
            return;

        var contentColumn = dropdownItem.children[0];
        var iconColumn = dropdownItem.children[dropdownItem.children.length - 1];
        
        if (!contentColumn || !iconColumn)
            return;

        var saveIcon = iconColumn.children.length > 1 ? iconColumn.children[0] : null;

        if (saveIcon) {
            saveIcon.visible = Qt.binding(function() {
                return dropdownItem.dropdownState === "add";
            });

            saveIcon.height = Qt.binding(function() {
                return dropdownItem.dropdownState === "add" ? 25 : 0;
            });
        }

        iconColumn.spacing = Qt.binding(function() {
            return dropdownItem.dropdownState === "add" ? 5 : 0;
        });

        // Clear any existing anchor bindings that might conflict
        iconColumn.anchors.verticalCenter = undefined;
        iconColumn.anchors.top = undefined;
        iconColumn.anchors.bottom = undefined;

        // Manually calculate Y position to account for nested coordinates
        iconColumn.y = Qt.binding(function() {
            var displayRect = null;
            var yOffset = 0;

            if (dropdownItem.isMultiSelect) {
                // MultiSelect: displayRect is direct child of contentColumn (index 2)
                if (contentColumn.children.length > 2) {
                    displayRect = contentColumn.children[2];
                    yOffset = displayRect.y;
                }
            } else {
                // SingleSelect: displayRect is inside singleSelectColumn (index 1)
                var singleColumn = contentColumn.children.length > 1 ? contentColumn.children[1] : null;
                if (singleColumn && singleColumn.children && singleColumn.children.length > 0) {
                    displayRect = singleColumn.children[0];
                    // Add singleColumn.y to offset because displayRect.y is relative to singleColumn
                    yOffset = singleColumn.y + displayRect.y;
                }
            }

            if (displayRect) {
                // Center the icon column relative to the display rect
                return yOffset + (displayRect.height - iconColumn.height) / 2;
            }
            return 0;
        });
    }

    Component {
        id: rangeSliderComponent

        RangeSliderTemplate {
            id: rangeSlider
            sliderId: parameterConfig.parameter_name || "dynamic_slider"
            label: parameterConfig.label || parameterName
            matlabProperty: parameterConfig.matlab_property || ""
            from: parameterConfig.from || 0
            to: parameterConfig.to || 1
            firstValue: parameterConfig.first_value || parameterConfig.from || 0
            secondValue: parameterConfig.second_value || parameterConfig.to || 1
            stepSize: parameterConfig.step_size || 0.1
            unit: parameterConfig.unit || ""
            backgroundColor: parameterConfig.background_color || "white"
            sliderState: editModeEnabled ? "edit" : "default"

                    onFirstValueChanged: {
                        if (initialized) {
                            dynamicParameterLoader.parameterChanged(parameterName, [firstValue, secondValue]);
                            // Auto-save to MATLAB
                            matlabExecutor.saveRangeSliderPropertyToMatlab(parameterConfig.matlab_property, firstValue, secondValue, parameterConfig.unit || "");
                        }
                    }

                    onSecondValueChanged: {
                        if (initialized) {
                            dynamicParameterLoader.parameterChanged(parameterName, [firstValue, secondValue]);
                            // Auto-save to MATLAB
                            matlabExecutor.saveRangeSliderPropertyToMatlab(parameterConfig.matlab_property, firstValue, secondValue, parameterConfig.unit || "");
                        }
                    }            property bool initialized: false
            Component.onCompleted: {
                initialized = true;
            }
        }
    }

    Component {
        id: dropdownComponent

        DropdownTemplate {
            id: dropdown
            label: parameterConfig.label || parameterName
            matlabProperty: parameterConfig.matlab_property || ""
            model: parameterConfig.model || []
            currentIndex: parameterConfig.current_index || 0
            property bool addFeatureEnabled: parameterConfig.has_add_feature !== undefined ? parameterConfig.has_add_feature : true
            property string propertySuffix: {
                var prop = parameterConfig.matlab_property || ""
                if (prop.indexOf(".") !== -1) {
                    var parts = prop.split('.')
                    prop = parts[parts.length - 1]
                }
                return prop.length > 0 ? prop.replace(/_/g, " ") : parameterName
            }
            hasAddFeature: addFeatureEnabled
            addPlaceholder: addFeatureEnabled ? "Add custom " + propertySuffix + "..." : ""
            isMultiSelect: parameterConfig.is_multi_select || false
            maxSelections: parameterConfig.max_selections || -1
            allItems: parameterConfig.all_items !== undefined ? parameterConfig.all_items : (parameterConfig.model || [])
            selectedItems: parameterConfig.selected_items || []
            dropdownState: editModeEnabled ? "edit" : "default"

            onSelectionChanged: {
                if (isMultiSelect) {
                    dynamicParameterLoader.parameterChanged(parameterName, selectedItems);
                    // Auto-save to MATLAB
                    var needsCellFormat = parameterConfig.is_multi_select && (parameterConfig.max_selections !== 1);
                    matlabExecutor.saveDropdownPropertyToMatlab(parameterConfig.matlab_property, selectedItems, needsCellFormat);
                } else {
                    dynamicParameterLoader.parameterChanged(parameterName, model[currentIndex]);
                    // Auto-save to MATLAB
                    matlabExecutor.saveDropdownPropertyToMatlab(parameterConfig.matlab_property, [model[currentIndex]], false);
                }
            }

            onMultiSelectionChanged: {
                dynamicParameterLoader.parameterChanged(parameterName, selectedItems);
                // Auto-save to MATLAB
                var needsCellFormat = parameterConfig.is_multi_select && (parameterConfig.max_selections !== 1);
                matlabExecutor.saveDropdownPropertyToMatlab(parameterConfig.matlab_property, selectedItems, needsCellFormat);
            }
        }
    }

    Component {
        id: stepRangeSliderComponent

        StepRangeSliderTemplate {
            id: stepRangeSlider
            sliderId: parameterConfig.parameter_name || "dynamic_step_range_slider"
            label: parameterConfig.label || parameterName
            matlabProperty: parameterConfig.matlab_property || ""
            from: parameterConfig.from || 0
            to: parameterConfig.to || 1
            firstValue: parameterConfig.first_value || parameterConfig.from || 0
            secondValue: parameterConfig.second_value || parameterConfig.to || 1
            stepSize: parameterConfig.step_size || 0.1
            unit: parameterConfig.unit || ""
            backgroundColor: parameterConfig.background_color || "white"
            sliderState: editModeEnabled ? "edit" : "default"

            onRangeChanged: {
                dynamicParameterLoader.parameterChanged(parameterName, [firstValue, secondValue]);
                // Auto-save to MATLAB
                matlabExecutor.saveRangeSliderPropertyToMatlab(parameterConfig.matlab_property, firstValue, secondValue, parameterConfig.unit || "");
            }
        }
    }

    // Function to get current parameter value
    function getCurrentValue() {
        if (parameterComponentLoader.item) {
            if (parameterConfig.component_type === "RangeSliderTemplate" || parameterConfig.component_type === "StepRangeSliderTemplate") {
                return [parameterComponentLoader.item.firstValue, parameterComponentLoader.item.secondValue];
            } else if (parameterConfig.component_type === "DropdownTemplate") {
                if (parameterComponentLoader.item.isMultiSelect) {
                    return parameterComponentLoader.item.selectedItems;
                } else {
                    return parameterComponentLoader.item.model[parameterComponentLoader.item.currentIndex];
                }
            }
        }
        return null;
    }

    // Function to set parameter value
    function setValue(value) {
        if (!parameterComponentLoader.item) return;

        if ((parameterConfig.component_type === "RangeSliderTemplate" || parameterConfig.component_type === "StepRangeSliderTemplate") && Array.isArray(value) && value.length >= 2) {
            parameterComponentLoader.item.firstValue = value[0];
            parameterComponentLoader.item.secondValue = value[1];
        } else if (parameterConfig.component_type === "DropdownTemplate") {
            if (parameterComponentLoader.item.isMultiSelect && Array.isArray(value)) {
                parameterComponentLoader.item.selectedItems = value;
            } else if (typeof value === "string") {
                var index = parameterComponentLoader.item.model.indexOf(value);
                if (index !== -1) {
                    parameterComponentLoader.item.currentIndex = index;
                }
            }
        }
    }
}