function channelwise_visualizer(coherence_records)
% CHANNELWISE_VISUALIZER Interactive viewer for channel-wise coherence results.
%
%   channelwise_visualizer(coherence_records) expects the contents of
%   channelwise_coherence_output.mat (subjects x 3 struct array of
%   conditions target/standard/novelty). It plots coherence time-frequency
%   maps for a selected channel pair across the three conditions.

ensure_fieldtrip_on_path();

coherence_records = normalize_coherence_records(coherence_records);
num_subjects = size(coherence_records, 1);

fig = figure('Name', 'Channel-Wise Coherence Visualization', 'NumberTitle', 'off', ...
    'Position', [50, 50, 1400, 900], 'WindowState', 'maximized', ...
    'Color', [1 1 1], 'Visible', 'off');

data.coherence_records = coherence_records;
data.num_subjects = num_subjects;
data.current_subject = 1;
[data.pair_labels, data.pair_indices] = build_pair_list(coherence_records);
if isempty(data.pair_labels)
    error('channelwise_visualizer:InvalidInput', 'No channel pairs found in coherence data.');
end
data.selected_pair_indices = []; % default to no pairs selected

data.xlim_override = [];
data.ylim_override = [];

guidata(fig, data);
create_ui_controls(fig, data);

if strcmp(get(fig, 'Visible'), 'off')
    set(fig, 'Visible', 'on');
    drawnow;
end

plot_subject(fig);

end

function out = normalize_coherence_records(in)
if isnumeric(in)
    error('channelwise_visualizer:InvalidInput', 'Expected struct input, received numeric.');
end
if ndims(in) == 2 && size(in, 2) == 3 && isstruct(in)
    out = in;
    return;
end
req = {'target','standard','novelty'};
if isstruct(in) && isvector(in) && all(isfield(in, req))
    n = numel(in);
    template = struct('cohspctrm', [], 'label', [], 'labelcmb', [], 'freq', [], 'time', [], 'dimord', '', 'cfg', []);
    out = repmat(template, n, 3);
    for i = 1:n
        for j = 1:3
            fld = req{j};
            if ~isempty(in(i).(fld))
                out(i,j) = normalize_condition(in(i).(fld), template);
            end
        end
    end
    return;
end
error('channelwise_visualizer:InvalidInput', ['Unsupported coherence data format. Expected an (subjects x 3) struct array or a vector ', ...
    'struct with fields target, standard, novelty.']);
end

function cond = normalize_condition(inCond, template)
cond = template;
if ~isstruct(inCond)
    return;
end
fns = fieldnames(template);
for k = 1:numel(fns)
    fn = fns{k};
    if isfield(inCond, fn)
        cond.(fn) = inCond.(fn);
    end
end
end

function [pair_labels, pair_indices] = build_pair_list(records)
pair_labels = {};
pair_indices = [];
% find first non-empty condition
first = [];
for i = 1:numel(records)
    if ~isempty(records(i).cohspctrm)
        first = records(i);
        break;
    end
end
if isempty(first)
    return;
end
if isfield(first, 'labelcmb') && ~isempty(first.labelcmb)
    cmb = first.labelcmb;
    if isstring(cmb) || ischar(cmb)
        cmb = cellstr(cmb);
    end
    pair_labels = cellfun(@(r) strjoin(r, ' - '), cmb, 'UniformOutput', false);
    pair_indices = (1:numel(pair_labels)).';
elseif isfield(first, 'label') && ~isempty(first.label)
    labels = first.label;
    if isstring(labels) || ischar(labels)
        labels = cellstr(labels);
    end
    n = numel(labels);
    idx = 1;
    for a = 1:n-1
        for b = a+1:n
            pair_labels{idx,1} = sprintf('%s - %s', labels{a}, labels{b}); %#ok<AGROW>
            pair_indices(idx,:) = [a b]; %#ok<AGROW>
            idx = idx + 1;
        end
    end
end
end

function plot_subject(fig)
data = guidata(fig);

selected_pairs = data.selected_pair_indices;
num_pairs = numel(selected_pairs);

cond_target = data.coherence_records(data.current_subject,1);
cond_standard = data.coherence_records(data.current_subject,2);
cond_novelty = data.coherence_records(data.current_subject,3);

% Clear axes
delete(findall(fig, 'Type', 'axes'));

titles = {'Target','Standard','Novelty'};
conds = {cond_target, cond_standard, cond_novelty};

% Create grid of subplots for selected pairs x 3 conditions
for idx = 1:num_pairs
    pairIdx = selected_pairs(idx);
    pairLabel = data.pair_labels{pairIdx};
    
    for c = 1:3
        subplot(num_pairs, 3, (idx-1)*3 + c);
        
        tfr = extract_pair_tfr(conds{c}, pairIdx, data.pair_labels, data.pair_indices);
        if isempty(tfr)
            text(0.5,0.5,'No data','HorizontalAlignment','center');
        else
            cfg = [];
            cfg.channel = tfr.label;
            cfg.colorbar = 'no';
            cfg.zlim = [0 1];
            cfg.figure = gca;
            cfg.interactive = 'no';
            cfg.title = '';
            cfg.comment = 'no';
            if ~isempty(data.ylim_override), cfg.ylim = data.ylim_override; end
            if ~isempty(data.xlim_override), cfg.xlim = data.xlim_override; end
            try
                ft_singleplotTFR(cfg, tfr);
                colormap('jet');
                if idx == 1
                    title(titles{c});
                end
            catch plotErr
                text(0.5,0.5,sprintf('Plot error: %s', plotErr.message),'HorizontalAlignment','center');
            end
        end
        if c == 1
            ylabel(pairLabel);
        end
        if idx == num_pairs
            xlabel('Time (s)');
        end
    end
end

sgtitle(sprintf('Channel-Wise Coherence - Subject %d/%d', data.current_subject, data.num_subjects));

guidata(fig, data);
end

function tfr = extract_pair_tfr(condData, pairIdx, pairLabels, pairIndices)
tfr = [];
if isempty(condData) || ~isfield(condData,'cohspctrm') || isempty(condData.cohspctrm)
    return;
end
coh = condData.cohspctrm;
freq = [];
time = [];
if isfield(condData,'freq'), freq = condData.freq; end
if isfield(condData,'time'), time = condData.time; end

if isfield(condData,'labelcmb') && ~isempty(condData.labelcmb)
    if pairIdx > size(coh,1)
        return;
    end
    pairData = squeeze(coh(pairIdx,:,:));
elseif ndims(coh) >= 4 && size(coh,1) == size(coh,2)
    ij = pairIndices(pairIdx,:);
    if any(ij==0) || ij(1) > size(coh,1) || ij(2) > size(coh,2)
        return;
    end
    pairData = squeeze(coh(ij(1), ij(2), :, :));
else
    return;
end

% Ensure 2-D freq x time (or freq) matrix
pairSize = size(pairData);
if numel(pairSize) == 1
    pairData = pairData(:).';
    elif numel(pairSize) == 2
    % freq x time or freq x 1
else
    pairData = squeeze(pairData);
end

pow = reshape(pairData, [1 size(pairData)]);

tfr = struct();
tfr.powspctrm = pow;
tfr.label = {pairLabels{pairIdx}};
tfr.freq = freq;
tfr.time = time;
tfr.dimord = 'chan_freq_time';
end

function create_ui_controls(fig, data)
% Axis limit controls (moved closer to navigation buttons)
uicontrol('Style','text','String','xlim min:', ...
    'Position',[20 90 55 15],'HorizontalAlignment','left');
edit_xmin = uicontrol('Style','edit','String','', ...
    'Position',[75 87 40 22], ...
    'Callback',@(src,evt) update_axis_limits(fig,'x'));

uicontrol('Style','text','String','max:', ...
    'Position',[120 90 30 15],'HorizontalAlignment','left');
edit_xmax = uicontrol('Style','edit','String','', ...
    'Position',[150 87 40 22], ...
    'Callback',@(src,evt) update_axis_limits(fig,'x'));

uicontrol('Style','text','String','ylim min:', ...
    'Position',[20 60 55 15],'HorizontalAlignment','left');
edit_ymin = uicontrol('Style','edit','String','', ...
    'Position',[75 57 40 22], ...
    'Callback',@(src,evt) update_axis_limits(fig,'y'));

uicontrol('Style','text','String','max:', ...
    'Position',[120 60 30 15],'HorizontalAlignment','left');
edit_ymax = uicontrol('Style','edit','String','', ...
    'Position',[150 57 40 22], ...
    'Callback',@(src,evt) update_axis_limits(fig,'y'));

% navigation
uicontrol('Style','pushbutton','String','← Previous', ...
    'Position',[20 20 100 30], ...
    'Callback',@(src,evt) navigate_subject(fig,-1));

uicontrol('Style','pushbutton','String','Next →', ...
    'Position',[130 20 100 30], ...
    'Callback',@(src,evt) navigate_subject(fig,1));

% Channel pair toggle button
pair_toggle_btn = uicontrol('Style','pushbutton','String','Channel pairs', ...
    'Position',[250 20 140 30], ...
    'Callback',@(src,evt) toggle_pair_panel(fig));

% Create checkbox panel for pairs
num_pairs = numel(data.pair_labels);
pairs_per_column = ceil(num_pairs / 2);  % Split into two columns

% Calculate panel width based on text content
max_label_length = max(cellfun(@length, data.pair_labels));
estimated_char_width = 7;  % Approximate pixels per character
column_padding = 20;  % Padding for each column
min_column_width = 120;  % Minimum width per column
calculated_column_width = max(min_column_width, max_label_length * estimated_char_width + 30);
panel_width = calculated_column_width * 2 + column_padding;  % Two columns plus padding

panel_height = 20 + pairs_per_column * 18;  % Height based on pairs per column

panel = uipanel('Parent', fig, 'Units', 'pixels', ...
    'Position', [250, 50, panel_width, panel_height], ...
    'BorderType', 'etchedin', ...
    'Visible', 'off');

all_selected = numel(data.selected_pair_indices) == num_pairs;
all_cb = uicontrol('Parent', panel, 'Style', 'checkbox', ...
    'String', 'All Pairs', ...
    'Value', all_selected, ...
    'Position', [10, panel_height - 20, panel_width - 20, 20], ...
    'Callback', []); % assign after pair checkboxes exist

pair_cbs = cell(1, num_pairs);
column_width = calculated_column_width;  % Use calculated width for each column
for i = 1:num_pairs
    % Determine column (1 or 2) and row within column
    if i <= pairs_per_column
        col = 1;
        row_in_col = i;
        x_pos = 10;
    else
        col = 2;
        row_in_col = i - pairs_per_column;
        x_pos = 10 + column_width + 10;
    end
    
    y = panel_height - 20 - (row_in_col * 18);
    pair_cbs{i} = uicontrol('Parent', panel, 'Style', 'checkbox', ...
        'String', data.pair_labels{i}, ...
        'Value', ismember(i, data.selected_pair_indices), ...
        'Position', [x_pos, y, column_width - 10, 20], ...
        'Callback', []); % assign after creation
end

% Now wire callbacks with full handle visibility
set(all_cb, 'Callback', @(src, evt) handle_all_pairs_checkbox(fig, src, pair_cbs));
for i = 1:num_pairs
    set(pair_cbs{i}, 'Callback', @(src, evt) handle_pair_checkbox(fig, all_cb, pair_cbs, i));
end

% Store handles
s = guidata(fig);
s.xlim_min_edit = edit_xmin;
s.xlim_max_edit = edit_xmax;
s.ylim_min_edit = edit_ymin;
s.ylim_max_edit = edit_ymax;
s.pair_toggle_btn = pair_toggle_btn;
s.pair_panel = panel;
s.pair_checkboxes = pair_cbs;
s.pair_all_checkbox = all_cb;
s.pair_panel_visible = false;
guidata(fig, s);
end

function navigate_subject(fig, direction)
data = guidata(fig);
new_subject = data.current_subject + direction;
new_subject = max(1, min(data.num_subjects, new_subject));
if new_subject ~= data.current_subject
    data.current_subject = new_subject;
    guidata(fig, data);
    plot_subject(fig);
end
end

function handle_all_pairs_checkbox(fig, all_cb, pair_cbs)
value = get(all_cb, 'Value');
for i = 1:numel(pair_cbs)
    set(pair_cbs{i}, 'Value', value);
end
if value == 1
    set_selected_pairs(fig, 1:numel(pair_cbs));
else
    set_selected_pairs(fig, []);
end
end

function handle_pair_checkbox(fig, all_cb, pair_cbs, idx)
unused = idx; %#ok<NASGU> Intentionally unused but keeps signature clear
vals = cellfun(@(cb) logical(get(cb, 'Value')), pair_cbs);
if all(vals)
    set(all_cb, 'Value', 1);
else
    set(all_cb, 'Value', 0);
end

selected = find(vals);
set_selected_pairs(fig, selected);
end

function set_selected_pairs(fig, selected_indices)
data = guidata(fig);
num_pairs = numel(data.pair_labels);

selected_indices = selected_indices(selected_indices >= 1 & selected_indices <= num_pairs);

data.selected_pair_indices = selected_indices;
guidata(fig, data);
plot_subject(fig);
end

function toggle_pair_panel(fig)
data = guidata(fig);

is_visible = strcmp(get(data.pair_panel, 'Visible'), 'on');
if is_visible
    set(data.pair_panel, 'Visible', 'off');
    set(data.pair_toggle_btn, 'String', 'Channel pairs');
    data.pair_panel_visible = false;
else
    set(data.pair_panel, 'Visible', 'on');
    set(data.pair_toggle_btn, 'String', 'Channel pairs (open)');
    data.pair_panel_visible = true;
end

guidata(fig, data);
end

function update_axis_limits(fig, axis_type)
data = guidata(fig);
if axis_type == 'x'
    min_str = strtrim(get(data.xlim_min_edit,'String'));
    max_str = strtrim(get(data.xlim_max_edit,'String'));
    min_val = str2double(min_str);
    max_val = str2double(max_str);
    if isempty(min_str) || isempty(max_str)
        data.xlim_override = [];
    elseif isfinite(min_val) && isfinite(max_val) && min_val < max_val
        data.xlim_override = [min_val, max_val];
    else
        warndlg('Enter numeric min < max for xlim (time).','Invalid axis limits');
        return;
    end
else
    min_str = strtrim(get(data.ylim_min_edit,'String'));
    max_str = strtrim(get(data.ylim_max_edit,'String'));
    min_val = str2double(min_str);
    max_val = str2double(max_str);
    if isempty(min_str) || isempty(max_str)
        data.ylim_override = [];
    elseif isfinite(min_val) && isfinite(max_val) && min_val < max_val
        data.ylim_override = [min_val, max_val];
    else
        warndlg('Enter numeric min < max for ylim (frequency).','Invalid axis limits');
        return;
    end
end
guidata(fig, data);
plot_subject(fig);
end

function ensure_fieldtrip_on_path()
if exist('ft_singleplotTFR', 'file') == 3 || exist('ft_singleplotTFR', 'file') == 2
    return;
end
fprintf('FieldTrip not found in path. Attempting to locate and add it...\n');
ft_paths = {};
currentFile = mfilename('fullpath');
[currentDir, ~, ~] = fileparts(currentFile);
preprocessingScript = fullfile(currentDir, '..', '..', '..', 'preprocessing', 'matlab', 'preprocessing.m');
if exist(preprocessingScript, 'file')
    fid = fopen(preprocessingScript, 'r');
    if fid ~= -1
        while ~feof(fid)
            tline = fgetl(fid);
            if ischar(tline) && contains(tline, 'addpath') && (contains(tline, 'fieldtrip', 'IgnoreCase', true) || contains(tline, 'FIELDTRIP'))
                tokens = regexp(tline, 'addpath\([''\"]([^''\"]+)[''\"]\)', 'tokens');
                if ~isempty(tokens) && ~isempty(tokens{1})
                    extractedPath = tokens{1}{1};
                    fprintf('Found FieldTrip path in preprocessing.m: %s\n', extractedPath);
                    ft_paths{end+1} = extractedPath; %#ok<AGROW>
                end
            end
        end
        fclose(fid);
    end
else
    fprintf('Warning: preprocessing.m not found at %s\n', preprocessingScript);
end
if isempty(ft_paths)
    ft_paths = {
        'C:\\Program Files\\MATLAB\\fieldtrip';
        'C:\\fieldtrip';
        'D:\\fieldtrip';
        fullfile(userpath, 'fieldtrip')
        };
end
ft_found = false;
for i = 1:length(ft_paths)
    ft_path = ft_paths{i};
    if exist(ft_path, 'dir')
        fprintf('Trying FieldTrip at: %s\n', ft_path);
        addpath(ft_path);
        try
            ft_defaults;
            fprintf('FieldTrip initialized successfully\n');
            ft_found = true;
            break;
        catch
            fprintf('Failed to initialize FieldTrip from: %s\n', ft_path);
            rmpath(ft_path);
        end
    end
end
if ~ft_found
    error(['FieldTrip not found. Please install FieldTrip and ensure it is on the MATLAB path.\n' ...
        'Common locations: C:\\Program Files\\MATLAB\\fieldtrip, C:\\fieldtrip, D:\\fieldtrip, or userpath/fieldtrip']);
end
end
