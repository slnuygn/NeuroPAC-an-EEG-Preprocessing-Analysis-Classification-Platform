function browse_ICA(mat_file_path)
% Function to browse ICA components from a .mat file
% Input: mat_file_path - path to the .mat file containing ICA data

set(groot, 'DefaultFigureColormap', jet);

try
    % Load the .mat file containing the ICA results
    fprintf('Loading file: %s\n', mat_file_path);
    loaded_data = load(mat_file_path);
    
    % Display what variables we found
    var_names = fieldnames(loaded_data);
    fprintf('Variables in file: %s\n', strjoin(var_names, ', '));
    
    % Determine folder for associated data.mat
    [mat_folder, ~, ~] = fileparts(mat_file_path);
    raw_data_path = fullfile(mat_folder, 'data.mat');
    
    % Try to find ICA data variable automatically (prioritize data_ICApplied)
    ICA_data = [];
    var_used = '';
    if isfield(loaded_data, 'data_ICApplied')
        ICA_data = loaded_data.data_ICApplied;
        var_used = 'data_ICApplied';
        fprintf('Found ICA data in variable: %s\n', var_used);
    end
    
    raw_data = [];
    raw_var_used = '';
    if exist(raw_data_path, 'file')
        try
            raw_struct = load(raw_data_path, 'data');
            if isfield(raw_struct, 'data')
                raw_data = raw_struct.data;
                raw_var_used = 'data';
                fprintf('Loaded sensor-space data from %s (variable: %s)\n', raw_data_path, raw_var_used);
            else
                fprintf('Warning: %s does not contain variable ''data''.\n', raw_data_path);
            end
        catch rawLoadErr
            fprintf('Warning: Failed to load %s (%s).\n', raw_data_path, rawLoadErr.message);
        end
    else
        fprintf('Warning: data.mat not found in %s. Falling back to reconstructing raw data if needed.\n', mat_folder);
    end
    
    % Get all non-metadata variable names
    var_names = fieldnames(loaded_data);
    data_vars = {};
    for j = 1:length(var_names)
        if length(var_names{j}) < 2 || ~strcmp(var_names{j}(1:2), '__')
            data_vars{end+1} = var_names{j};
        end
    end
    
    fprintf('Searching for ICA data in %d variables...\n', length(data_vars));
    
    % Look for variables that contain ICA data structures (only if not already resolved)
    for i = 1:length(data_vars)
        var_name = data_vars{i};
        var_data = loaded_data.(var_name);
        
        fprintf('Checking variable: %s\n', var_name);
        
        % Check if this variable looks like ICA data
        if isempty(ICA_data) && isICAData(var_data)
            ICA_data = var_data;
            var_used = var_name;
            fprintf('Found ICA data in variable: %s\n', var_name);
        end
        
        if isempty(raw_data) && isRawData(var_data)
            raw_data = var_data;
            raw_var_used = var_name;
            fprintf('Found sensor-space data in variable: %s\n', var_name);
        end
    end
    
    if isempty(ICA_data)
        error('No suitable ICA data variable found in file');
    end
    
    fprintf('Using variable: %s\n', var_used);
    fprintf('Data contains %d subject(s)\n', length(ICA_data));
    if ~isempty(raw_data)
        fprintf('Raw data variable detected: %s\n', raw_var_used);
    end
    
    % Initialize rejected ICs array - zeros array with same size as ICA_data
    rejected_ICs_array = cell(length(ICA_data), 1);
    for j = 1:length(ICA_data)
        rejected_ICs_array{j} = [];  % Initialize as empty array for each subject
    end
    
    % Browse the ICA components
    for i = 1:length(ICA_data)
        cfg = [];
        cfg.allowoverlap = 'yes';
        cfg.layout = 'easycapM11.lay';  % your layout file
        cfg.viewmode = 'component';      % component view mode
        cfg.continuous = 'no';
        cfg.total_subjects = length(ICA_data);  % Pass total subject count
        cfg.current_subject_index = i;  % Pass current subject index
        
        fprintf('Showing components for subject %d\n', i);
        
        % Call ft_databrowser and wait for it to complete
        cfg_out = ft_databrowser(cfg, ICA_data(i));
        
        % Collect rejected ICs for current subject
        if isfield(cfg_out, 'rejected_ICs') && ~isempty(cfg_out.rejected_ICs)
            % Since we're processing one subject at a time, the rejected_ICs
            % should contain data for the current subject at index i
            subject_rejected = [];
            
            if i <= length(cfg_out.rejected_ICs)
                current_subject_data = cfg_out.rejected_ICs{i};
                
                if isequal(current_subject_data, 0)
                    subject_rejected = [];  % No rejected components
                elseif iscell(current_subject_data)
                    subject_rejected = cell2mat(current_subject_data);
                else
                    subject_rejected = current_subject_data;
                end
            end
            
            rejected_ICs_array{i} = subject_rejected;
        else
            rejected_ICs_array{i} = [];  % No rejected components
        end
        
        % Display what was rejected for this subject
        if isempty(rejected_ICs_array{i})
            fprintf('Subject %d: No components rejected\n', i);
        else
            fprintf('Subject %d: Rejected components [%s]\n', i, num2str(rejected_ICs_array{i}));
        end
        
        % Wait for user input to proceed to next subject (except for the last one)
        if i < length(ICA_data)
            fprintf('Subject %d processing complete. Press any key to continue to subject %d...\n', i, i+1);
            pause;
            % Close the current figure before opening the next one
            if ishandle(gcf)
                close(gcf);
            end
        end
    end
    
    % Display final results
    fprintf('\n=== Final Rejected Components Summary ===\n');
    for i = 1:length(rejected_ICs_array)
        if isempty(rejected_ICs_array{i})
            fprintf('Subject %d: No components rejected\n', i);
        else
            fprintf('Subject %d: Rejected components [%s]\n', i, num2str(rejected_ICs_array{i}));
        end
    end
    
    try
        fprintf('\nApplying reject_components to produce cleaned data...\n');
        sensor_space_data = derive_sensor_space_data(raw_data, ICA_data);
        ICApplied = ICA_data;
        clean_data = reject_components(sensor_space_data, ICApplied, rejected_ICs_array);
        assignin('base', 'clean_data', clean_data);
        fprintf('Cleaned data assigned to workspace as ''clean_data''.\n');
        
        % Decompose data
        fprintf('Decomposing cleaned data...\n');
        num_subjects = length(clean_data);
        clean_data_decomposed = struct( ...
            'target_data', cell(1, num_subjects), ...
            'standard_data', cell(1, num_subjects), ...
            'novelty_data', cell(1, num_subjects));
        
        for i = 1:num_subjects
            fprintf('Decomposing subject %d/%d\n', i, num_subjects);
            [clean_data_decomposed(i).target_data, ...
                clean_data_decomposed(i).standard_data, ...
                clean_data_decomposed(i).novelty_data] = decompose(clean_data{i});
        end
        
        assignin('base', 'clean_data_decomposed', clean_data_decomposed);
        
        clean_filename = 'data_ICApplied_clean_decomposed.mat';
        clean_fullpath = fullfile(mat_folder, clean_filename);
        save(clean_fullpath, 'clean_data_decomposed');
        fprintf('Decomposed cleaned data saved to %s\n', clean_fullpath);
        fprintf('Rejected component indices stored inside each clean_data entry (field ''rejected_components'').\n');
    catch rejectionME
        fprintf('Warning: Failed to apply reject_components within browse_ICA (%s).\n', rejectionME.message);
    end
    fprintf('ICA component browsing completed.\n');
    
catch ME
    fprintf('Error in browse_ICA: %s\n', ME.message);
    fprintf('Stack trace:\n');
    for i = 1:length(ME.stack)
        fprintf('  %s (line %d)\n', ME.stack(i).name, ME.stack(i).line);
    end
end

    function is_ica = isICAData(data)
        % Helper function to determine if a variable contains ICA data
        % Returns true if the data structure looks like FieldTrip ICA data
        
        is_ica = false;
        
        fprintf('  -> Checking data type: %s\n', class(data));
        
        % Check if it's a structure
        if ~isstruct(data)
            fprintf('  -> Not a struct\n');
            return;
        end
        
        fprintf('  -> Is a struct\n');
        
        % Check for basic FieldTrip fields
        if isfield(data, 'label')
            fprintf('  -> Has label field\n');
        else
            fprintf('  -> Missing label field\n');
        end
        
        if isfield(data, 'trial')
            fprintf('  -> Has trial field\n');
        else
            fprintf('  -> Missing trial field\n');
        end
        
        if isfield(data, 'time')
            fprintf('  -> Has time field\n');
        else
            fprintf('  -> Missing time field\n');
        end
        
        % If it has basic FieldTrip structure, consider it ICA data
        if isfield(data, 'label') && isfield(data, 'trial') && isfield(data, 'time')
            fprintf('  -> Has basic FieldTrip structure - assuming ICA data\n');
            is_ica = true;
        else
            fprintf('  -> Missing required FieldTrip fields\n');
        end
    end

    function is_raw = isRawData(candidate)
        % Identify FieldTrip-like sensor-space data structures
        is_raw = false;
        if isempty(candidate)
            return;
        end
        [first_entry, entry_count] = extract_first_struct(candidate);
        if isempty(first_entry) || entry_count == 0
            return;
        end
        
        required_fields = {'label', 'trial', 'time'};
        for fIdx = 1:numel(required_fields)
            if ~isfield(first_entry, required_fields{fIdx})
                return;
            end
        end
        is_raw = true;
    end

    function [first_entry, entry_count] = extract_first_struct(candidate)
        % Get the first struct from a cell/struct container and the total count
        first_entry = [];
        entry_count = 0;
        if iscell(candidate)
            entry_count = numel(candidate);
            for cellIdx = 1:entry_count
                if isstruct(candidate{cellIdx})
                    first_entry = candidate{cellIdx};
                    break;
                end
            end
        elseif isstruct(candidate)
            entry_count = numel(candidate);
            if entry_count > 0
                first_entry = candidate(1);
            end
        end
    end

    function data = derive_sensor_space_data(raw_candidate, ICA_struct)
        % Decide whether to use existing raw data or reconstruct from ICA
        expected_subjects = numel(ICA_struct);
        if isempty(raw_candidate)
            data = reconstruct_sensor_data(ICA_struct);
            return;
        end
        
        data = raw_candidate;
        subject_count = count_entries(data);
        if subject_count ~= expected_subjects
            fprintf('Raw data subject count (%d) does not match ICA data (%d). Reconstructing sensor-space data.\n', ...
                subject_count, expected_subjects);
            data = reconstruct_sensor_data(ICA_struct);
            return;
        end
        if ~isempty(raw_var_used)
            fprintf('Using sensor-space data from variable: %s\n', raw_var_used);
        end
    end

    function count = count_entries(container)
        if iscell(container) || isstruct(container)
            count = numel(container);
        else
            count = 0;
        end
    end

    function data = reconstruct_sensor_data(ICA_struct)
        % Rebuild sensor-space data from ICA components to enable rejection
        num_subjects = numel(ICA_struct);
        data = cell(1, num_subjects);
        for subjIdx = 1:num_subjects
            comp = ICA_struct(subjIdx);
            raw = struct();
            raw.label = comp.topolabel;
            raw.fsample = comp.fsample;
            raw.time = comp.time;
            raw.trial = cell(size(comp.trial));
            for trialIdx = 1:numel(comp.trial)
                raw.trial{trialIdx} = comp.topo * comp.trial{trialIdx};
            end
            raw.sampleinfo = extract_metadata_field(comp, 'sampleinfo');
            raw.trialinfo = extract_metadata_field(comp, 'trialinfo');
            raw.hdr = extract_metadata_field(comp, 'hdr');
            raw.cfg = extract_metadata_field(comp, 'cfg');
            if isempty(raw.cfg) && isfield(comp, 'cfg')
                raw.cfg = comp.cfg;
            end
            data{subjIdx} = raw;
        end
    end

    function value = extract_metadata_field(comp_struct, field_name)
        % Attempt to retrieve metadata fields from component structure chains
        value = [];
        if nargin < 2 || ~isstruct(comp_struct)
            return;
        end
        max_depth = 10;
        queue = {comp_struct};
        depths = 0;
        visited = cell(0, 1);
        while ~isempty(queue)
            current = queue{1};
            queue(1) = [];
            current_depth = depths(1);
            depths(1) = [];
            if isempty(current) || ~isstruct(current)
                continue;
            end
            if any(cellfun(@(s) isequal(s, current), visited))
                continue;
            end
            visited{end+1, 1} = current; %#ok<AGROW>
            if isfield(current, field_name) && ~isempty(current.(field_name))
                value = current.(field_name);
                return;
            end
            if current_depth >= max_depth
                continue;
            end
            next_depth = current_depth + 1;
            if isfield(current, 'previous') && isstruct(current.previous)
                queue{end+1} = current.previous; %#ok<AGROW>
                depths(end+1) = next_depth; %#ok<AGROW>
            end
            if isfield(current, 'raw') && isstruct(current.raw)
                queue{end+1} = current.raw; %#ok<AGROW>
                depths(end+1) = next_depth; %#ok<AGROW>
            end
            if isfield(current, 'cfg') && ~strcmp(field_name, 'cfg') && isstruct(current.cfg)
                queue{end+1} = current.cfg; %#ok<AGROW>
                depths(end+1) = next_depth; %#ok<AGROW>
            end
        end
    end

end