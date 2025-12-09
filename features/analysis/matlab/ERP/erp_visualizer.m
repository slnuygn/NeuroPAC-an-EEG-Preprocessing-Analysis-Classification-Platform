function erp_visualizer(erp_records)
% ERP_VISUALIZER Interactive visualization of ERP analysis results
%
%   erp_visualizer(erp_records) creates a single interactive figure window
%   with a 1x3 grid layout that allows navigation through subject records
%   using Previous/Next buttons.
%
%   Input:
%       erp_records - Structure array where each row is a subject and
%                     columns are: target, standard, novelty
%                     Each cell contains a struct with fields: time, label,
%                     avg, var, dof, dimord, cfg
%
%   Example:
%       results = perform_erp_analysis(data);
%       erp_visualizer(results);

% Normalize input to expected subjects x 3 struct array (target/standard/novelty)
erp_records = normalize_erp_records(erp_records);

% Get number of subjects from the data
num_subjects = size(erp_records, 1);

% Create figure (hidden initially to avoid flash) with white background
fig = figure('Name', 'ERP Analysis Visualization', 'NumberTitle', 'off', ...
    'Position', [50, 50, 1400, 900], 'WindowState', 'maximized', ...
    'Color', [1 1 1], 'Visible', 'off');

% Create data structure to store current state
data.erp_records = erp_records;
data.num_subjects = num_subjects;
data.current_subject = 1;
data.channel_labels = get_channel_labels(erp_records);
data.selected_channel_indices = 1:numel(data.channel_labels); % default to all channels

% Store data in figure, build UI once
guidata(fig, data);
create_ui_controls(fig, data);

% Show the figure (controls appear immediately) and draw UI
if strcmp(get(fig, 'Visible'), 'off')
    set(fig, 'Visible', 'on');
    drawnow; % ensure controls render promptly
end

% Plot initial subject
plot_subject(fig);

end

% Helper: accept either already-formatted erp_records or a 1-D ERP_data struct
function out = normalize_erp_records(in)
% If already in expected shape (subjects x 3), return as-is
if isnumeric(in)
    error('erp_visualizer:InvalidInput', 'Expected struct input, received numeric.');
end

if ndims(in) == 2 && size(in, 2) == 3 && isstruct(in)
    out = in;
    return;
end

% If input is a vector of structs with fields target/standard/novelty, reshape
requiredFields = {'target', 'standard', 'novelty'};
if isstruct(in) && isvector(in) && all(isfield(in, requiredFields))
    numSubjects = numel(in);
    defaultRecord = struct('time', [], 'avg', [], 'label', [], 'var', [], 'dof', [], 'dimord', '', 'cfg', []);
    out = repmat(defaultRecord, numSubjects, 3);
    
    for iSub = 1:numSubjects
        for j = 1:3
            fieldName = requiredFields{j};
            if ~isempty(in(iSub).(fieldName))
                out(iSub, j) = in(iSub).(fieldName);
            end
        end
    end
    return;
end

error('erp_visualizer:InvalidInput', ['Unsupported ERP data format. Expected an (subjects x 3) struct array or a vector ', ...
    'struct with fields target, standard, novelty.']);
end

% Navigation callback function
function navigate_subject(fig, direction)
data = guidata(fig);

% Update current subject index
new_subject = data.current_subject + direction;

% Clamp to valid range
if new_subject < 1
    new_subject = 1;
elseif new_subject > data.num_subjects
    new_subject = data.num_subjects;
end

% Update if changed
if new_subject ~= data.current_subject
    data.current_subject = new_subject;
    guidata(fig, data);
    plot_subject(fig);
end
end

% Main plotting function
function plot_subject(fig)
data = guidata(fig);

% Get current subject's data (row contains target, standard, novelty)
target_data = data.erp_records(data.current_subject, 1);
standard_data = data.erp_records(data.current_subject, 2);
novelty_data = data.erp_records(data.current_subject, 3);

num_channels = size(target_data.avg, 1);

% Ensure channel selection is valid for current data
selected_channels = data.selected_channel_indices;
selected_channels = selected_channels(selected_channels <= num_channels);
data.selected_channel_indices = selected_channels;

% Clear existing axes only (keep UI controls for responsiveness)
delete(findall(fig, 'Type', 'axes'));

% Create grid of subplots for selected channels x 3 conditions
num_selected = numel(selected_channels);
for idx = 1:num_selected
    channel = selected_channels(idx);
    channel_label = data.channel_labels{channel};
    
    % Target column (column 1)
    subplot(num_selected, 3, (idx-1)*3 + 1);
    plot(target_data.time, target_data.avg(channel, :));
    ylabel(channel_label);
    if idx == 1
        title('Target');
    end
    if idx == num_selected
        xlabel('Time (s)');
    end
    grid on;
    
    % Standard column (column 2)
    subplot(num_selected, 3, (idx-1)*3 + 2);
    plot(standard_data.time, standard_data.avg(channel, :));
    if idx == 1
        title('Standard');
    end
    if idx == num_selected
        xlabel('Time (s)');
    end
    grid on;
    
    % Novelty column (column 3)
    subplot(num_selected, 3, (idx-1)*3 + 3);
    plot(novelty_data.time, novelty_data.avg(channel, :));
    if idx == 1
        title('Novelty');
    end
    if idx == num_selected
        xlabel('Time (s)');
    end
    grid on;
end

% Add main title with subject info
sgtitle(sprintf('ERP Analysis - Subject %d/%d', data.current_subject, data.num_subjects));

end

% UI creation helper
function create_ui_controls(fig, data)

data.prev_btn = uicontrol('Style', 'pushbutton', 'String', '← Previous', ...
    'Position', [20, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, -1));

data.next_btn = uicontrol('Style', 'pushbutton', 'String', 'Next →', ...
    'Position', [130, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, 1));

data.channel_toggle_btn = uicontrol('Style', 'pushbutton', 'String', 'Channels', ...
    'Position', [20, 70, 120, 30], ...
    'Callback', @(src, evt) toggle_channel_panel(fig));

num_channels = numel(data.channel_labels);
panel_height = 30 + num_channels * 22;
panel_width = 200;

panel = uipanel('Parent', fig, 'Units', 'pixels', ...
    'Position', [20, 70 + 30, panel_width, panel_height], ...
    'BorderType', 'etchedin', ...
    'Visible', 'off');

all_selected = numel(data.selected_channel_indices) == num_channels;
all_cb = uicontrol('Parent', panel, 'Style', 'checkbox', ...
    'String', 'All Channels', ...
    'Value', all_selected, ...
    'Position', [10, panel_height - 25, panel_width - 20, 20], ...
    'Callback', []); % assign after channel checkboxes exist

channel_cbs = cell(1, num_channels);
for i = 1:num_channels
    y = panel_height - 25 - (i * 22);
    channel_cbs{i} = uicontrol('Parent', panel, 'Style', 'checkbox', ...
        'String', data.channel_labels{i}, ...
        'Value', ismember(i, data.selected_channel_indices), ...
        'Position', [10, y, panel_width - 20, 20], ...
        'Callback', []); % assign after creation
end

% Now wire callbacks with full handle visibility
set(all_cb, 'Callback', @(src, evt) handle_all_checkbox(fig, src, channel_cbs));
for i = 1:num_channels
    set(channel_cbs{i}, 'Callback', @(src, evt) handle_channel_checkbox(fig, all_cb, channel_cbs, i));
end

data.channel_panel = panel;
data.channel_checkboxes = channel_cbs;
data.channel_all_checkbox = all_cb;
data.channel_panel_visible = false;

guidata(fig, data);
end

% Checkbox callbacks
function handle_all_checkbox(fig, all_cb, channel_cbs)
value = get(all_cb, 'Value');
for i = 1:numel(channel_cbs)
    set(channel_cbs{i}, 'Value', value);
end
if value == 1
    set_selected_channels(fig, 1:numel(channel_cbs));
else
    set_selected_channels(fig, []);
end
end

function handle_channel_checkbox(fig, all_cb, channel_cbs, idx)
unused = idx; %#ok<NASGU> Intentionally unused but keeps signature clear
vals = cellfun(@(cb) logical(get(cb, 'Value')), channel_cbs);
if all(vals)
    set(all_cb, 'Value', 1);
else
    set(all_cb, 'Value', 0);
end

selected = find(vals);
set_selected_channels(fig, selected);
end

function set_selected_channels(fig, selected_indices)
data = guidata(fig);
num_channels = numel(data.channel_labels);

selected_indices = selected_indices(selected_indices >= 1 & selected_indices <= num_channels);

data.selected_channel_indices = selected_indices;
guidata(fig, data);
plot_subject(fig);
end

% Toggle panel visibility
function toggle_channel_panel(fig)
data = guidata(fig);

is_visible = strcmp(get(data.channel_panel, 'Visible'), 'on');
if is_visible
    set(data.channel_panel, 'Visible', 'off');
    set(data.channel_toggle_btn, 'String', 'Channels');
    data.channel_panel_visible = false;
else
    set(data.channel_panel, 'Visible', 'on');
    set(data.channel_toggle_btn, 'String', 'Channels (open)');
    data.channel_panel_visible = true;
end

guidata(fig, data);
end

% Helper to extract channel labels or generate defaults
function labels = get_channel_labels(erp_records)
first_record = erp_records(1, 1);

if isfield(first_record, 'label') && ~isempty(first_record.label)
    raw_labels = first_record.label;
    if isstring(raw_labels) || ischar(raw_labels)
        labels = cellstr(raw_labels);
    else
        labels = raw_labels;
    end
else
    num_channels = size(first_record.avg, 1);
    labels = arrayfun(@(i) sprintf('Ch %d', i), 1:num_channels, 'UniformOutput', false);
end
end
