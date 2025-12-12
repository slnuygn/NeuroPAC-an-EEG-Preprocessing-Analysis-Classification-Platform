function timefreq_visualizer(timefreq_records)
% TIMEFREQ_VISUALIZER Interactive visualization of time-frequency analysis results.
%
%   timefreq_visualizer(timefreq_records) renders subject/condition TFRs
%   from timefreq_output.mat using ft_singleplotTFR. Input can be either a
%   subjects x 3 struct array (target/standard/novelty) or a vector of
%   structs with fields target/standard/novelty.

% Ensure FieldTrip is available (for ft_singleplotTFR)
ensure_fieldtrip_on_path();

% Normalize input layout
timefreq_records = normalize_timefreq_records(timefreq_records);
num_subjects = size(timefreq_records, 1);

% Create figure
fig = figure('Name', 'Time-Frequency Analysis Visualization', 'NumberTitle', 'off', ...
    'Position', [50, 50, 1400, 900], 'WindowState', 'maximized', ...
    'Color', [1 1 1], 'Visible', 'off');

data.timefreq_records = timefreq_records;
data.num_subjects = num_subjects;
data.current_subject = 1;
[data.channel_labels, data.default_freq, data.default_time] = get_channel_labels_and_axes(timefreq_records);
if isempty(data.channel_labels)
    error('timefreq_visualizer:InvalidInput', 'No channel labels found in time-frequency data.');
end
data.selected_channel_indices = 1:numel(data.channel_labels);

% Store state and build UI
guidata(fig, data);
create_ui_controls(fig, data);

if strcmp(get(fig, 'Visible'), 'off')
    set(fig, 'Visible', 'on');
    drawnow;
end

plot_subject(fig);

end

function out = normalize_timefreq_records(in)
if isnumeric(in)
    error('timefreq_visualizer:InvalidInput', 'Expected struct input, received numeric.');
end

% Already desired shape
if ndims(in) == 2 && size(in, 2) == 3 && isstruct(in)
    out = in;
    return;
end

requiredFields = {'target', 'standard', 'novelty'};
if isstruct(in) && isvector(in) && all(isfield(in, requiredFields))
    numSubjects = numel(in);
    template = struct('powspctrm', [], 'freq', [], 'time', [], 'label', [], 'dimord', '', 'cfg', []);
    out = repmat(template, numSubjects, 3);
    for iSub = 1:numSubjects
        for j = 1:3
            fieldName = requiredFields{j};
            if ~isempty(in(iSub).(fieldName))
                out(iSub, j) = normalize_condition(in(iSub).(fieldName), template);
            end
        end
    end
    return;
end

error('timefreq_visualizer:InvalidInput', ['Unsupported time-frequency data format. Expected an (subjects x 3) struct array or a vector ', ...
    'struct with fields target, standard, novelty.']);
end

function ensure_fieldtrip_on_path()
% Add FieldTrip to the path if ft_singleplotTFR is missing. Mirrors the
% fallback logic used in timelock_func.
if exist('ft_singleplotTFR', 'file') == 3 || exist('ft_singleplotTFR', 'file') == 2
    return; % already available
end

fprintf('FieldTrip not found in path. Attempting to locate and add it...\n');

ft_paths = {};

% Look for preprocessing.m to discover an addpath line
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

% Common fallback locations
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

function cond = normalize_condition(inCond, template)
% Copy only known fields to avoid dissimilar-structure assignment issues.
cond = template;
if ~isstruct(inCond)
    return;
end
fields = fieldnames(template);
for k = 1:numel(fields)
    fname = fields{k};
    if isfield(inCond, fname)
        cond.(fname) = inCond.(fname);
    end
end
% Preserve time/freq/label even if shapes differ
if isfield(inCond, 'freq'), cond.freq = inCond.freq; end
if isfield(inCond, 'time'), cond.time = inCond.time; end
if isfield(inCond, 'label'), cond.label = inCond.label; end
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

function plot_subject(fig)
data = guidata(fig);

freq_target = data.timefreq_records(data.current_subject, 1);
freq_standard = data.timefreq_records(data.current_subject, 2);
freq_novelty = data.timefreq_records(data.current_subject, 3);

num_channels = numel(data.channel_labels);
selected_channels = data.selected_channel_indices;
selected_channels = selected_channels(selected_channels <= num_channels);
data.selected_channel_indices = selected_channels;

% Clear axes only
delete(findall(fig, 'Type', 'axes'));
% Clear any lingering "no channels" label
delete(findobj(fig, 'Tag', 'noChannelsLabel'));

num_selected = numel(selected_channels);
if num_selected == 0
    uicontrol('Style', 'text', 'String', 'No channels selected', ...
        'Position', [200, 200, 200, 40], 'Tag', 'noChannelsLabel');
    guidata(fig, data);
    return;
end

for idx = 1:num_selected
    channelIdx = selected_channels(idx);
    channel_label = data.channel_labels{channelIdx};
    
    subplot(num_selected, 3, (idx-1)*3 + 1);
    plot_condition(freq_target, channel_label, data);
    ylabel(channel_label); % mirror ERP labeling per channel row
    if idx == 1; title('Target'); end
    
    subplot(num_selected, 3, (idx-1)*3 + 2);
    plot_condition(freq_standard, channel_label, data);
    if idx == 1; title('Standard'); end
    
    subplot(num_selected, 3, (idx-1)*3 + 3);
    plot_condition(freq_novelty, channel_label, data);
    if idx == 1; title('Novelty'); end
end

sgtitle(sprintf('Time-Frequency Analysis - Subject %d/%d', data.current_subject, data.num_subjects));

guidata(fig, data);
end

function plot_condition(freqStruct, channel_label, data)
if isempty(freqStruct) || ~isstruct(freqStruct) || ~isfield(freqStruct, 'powspctrm')
    text(0.5, 0.5, 'No data', 'HorizontalAlignment', 'center');
    return;
end

cfg = [];
cfg.channel = {channel_label};
cfg.colorbar = 'yes';
cfg.zlim = 'maxabs';
cfg.figure = gca; % render into the current subplot
cfg.interactive = 'no'; % disable FieldTrip interactive callbacks
cfg.title = ''; % suppress FieldTrip's auto channel title
cfg.comment = 'no'; % suppress auto comments above plots
if ~isempty(data.ylim_override)
    cfg.ylim = data.ylim_override; % frequency limits
end
if ~isempty(data.xlim_override)
    cfg.xlim = data.xlim_override; % time limits
end

% Use provided layout if available in cfg; otherwise skip to avoid errors
if isfield(freqStruct, 'cfg') && isfield(freqStruct.cfg, 'layout')
    cfg.layout = freqStruct.cfg.layout;
end

try
    ft_singleplotTFR(cfg, freqStruct);
catch plotErr
    text(0.5, 0.5, sprintf('Plot error: %s', plotErr.message), 'HorizontalAlignment', 'center');
end
end

function create_ui_controls(fig, data)

data.xlim_override = [];
data.ylim_override = [];

data.prev_btn = uicontrol('Style', 'pushbutton', 'String', '← Previous', ...
    'Position', [20, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, -1));

data.next_btn = uicontrol('Style', 'pushbutton', 'String', 'Next →', ...
    'Position', [130, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, 1));

uicontrol('Style', 'text', 'String', 'xlim  min:', ...
    'Position', [20, 130, 55, 15], 'HorizontalAlignment', 'left');
data.xlim_min_edit = uicontrol('Style', 'edit', 'String', '', ...
    'Position', [75, 128, 30, 20], ...
    'Callback', @(src, evt) update_axis_limits(fig, 'x'));
uicontrol('Style', 'text', 'String', 'max:', ...
    'Position', [110, 130, 30, 15], 'HorizontalAlignment', 'left');
data.xlim_max_edit = uicontrol('Style', 'edit', 'String', '', ...
    'Position', [140, 128, 30, 20], ...
    'Callback', @(src, evt) update_axis_limits(fig, 'x'));

uicontrol('Style', 'text', 'String', 'ylim  min:', ...
    'Position', [20, 100, 55, 15], 'HorizontalAlignment', 'left');
data.ylim_min_edit = uicontrol('Style', 'edit', 'String', '', ...
    'Position', [75, 98, 30, 20], ...
    'Callback', @(src, evt) update_axis_limits(fig, 'y'));
uicontrol('Style', 'text', 'String', 'max:', ...
    'Position', [110, 100, 30, 15], 'HorizontalAlignment', 'left');
data.ylim_max_edit = uicontrol('Style', 'edit', 'String', '', ...
    'Position', [140, 98, 30, 20], ...
    'Callback', @(src, evt) update_axis_limits(fig, 'y'));

data.channel_toggle_btn = uicontrol('Style', 'pushbutton', 'String', 'Channels', ...
    'Position', [20, 60, 120, 30], ...
    'Callback', @(src, evt) toggle_channel_panel(fig));

num_channels = numel(data.channel_labels);
panel_height = 30 + num_channels * 22;
panel_width = 200;

panel = uipanel('Parent', fig, 'Units', 'pixels', ...
    'Position', [20, 60 + 30, panel_width, panel_height], ...
    'BorderType', 'etchedin', ...
    'Visible', 'off');

all_selected = numel(data.selected_channel_indices) == num_channels;
all_cb = uicontrol('Parent', panel, 'Style', 'checkbox', ...
    'String', 'All Channels', ...
    'Value', all_selected, ...
    'Position', [10, panel_height - 25, panel_width - 20, 20], ...
    'Callback', []);

channel_cbs = cell(1, num_channels);
for i = 1:num_channels
    y = panel_height - 25 - (i * 22);
    channel_cbs{i} = uicontrol('Parent', panel, 'Style', 'checkbox', ...
        'String', data.channel_labels{i}, ...
        'Value', ismember(i, data.selected_channel_indices), ...
        'Position', [10, y, panel_width - 20, 20], ...
        'Callback', []);
end

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
vals = cellfun(@(cb) logical(get(cb, 'Value')), channel_cbs);
if all(vals)
    set(all_cb, 'Value', 1);
else
    set(all_cb, 'Value', 0);
end
selected = find(vals);
set_selected_channels(fig, selected);
end

function update_axis_limits(fig, axis_type)
data = guidata(fig);

if axis_type == 'x'
    min_str = strtrim(get(data.xlim_min_edit, 'String'));
    max_str = strtrim(get(data.xlim_max_edit, 'String'));
    min_val = str2double(min_str);
    max_val = str2double(max_str);
    if isempty(min_str) || isempty(max_str)
        data.xlim_override = [];
    elseif isfinite(min_val) && isfinite(max_val) && min_val < max_val
        data.xlim_override = [min_val, max_val];
    else
        warndlg('Enter numeric min < max for xlim (time).', 'Invalid axis limits');
        return;
    end
else
    min_str = strtrim(get(data.ylim_min_edit, 'String'));
    max_str = strtrim(get(data.ylim_max_edit, 'String'));
    min_val = str2double(min_str);
    max_val = str2double(max_str);
    if isempty(min_str) || isempty(max_str)
        data.ylim_override = [];
    elseif isfinite(min_val) && isfinite(max_val) && min_val < max_val
        data.ylim_override = [min_val, max_val];
    else
        warndlg('Enter numeric min < max for ylim (frequency).', 'Invalid axis limits');
        return;
    end
end

guidata(fig, data);
plot_subject(fig);
end

function set_selected_channels(fig, selected_indices)
data = guidata(fig);
num_channels = numel(data.channel_labels);
selected_indices = selected_indices(selected_indices >= 1 & selected_indices <= num_channels);
data.selected_channel_indices = selected_indices;

guidata(fig, data);
plot_subject(fig);
end

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

function [labels, freq, timeVec] = get_channel_labels_and_axes(timefreq_records)
first_nonempty = [];
for i = 1:numel(timefreq_records)
    if ~isempty(timefreq_records(i).powspctrm)
        first_nonempty = timefreq_records(i);
        break;
    end
end

if isempty(first_nonempty)
    labels = {};
    freq = [];
    timeVec = [];
    return;
end

if isfield(first_nonempty, 'label') && ~isempty(first_nonempty.label)
    raw_labels = first_nonempty.label;
    if isstring(raw_labels) || ischar(raw_labels)
        labels = cellstr(raw_labels);
    else
        labels = raw_labels;
    end
else
    ps = size(first_nonempty.powspctrm);
    if numel(ps) >= 3
        num_channels = ps(end-2); % powspctrm often trials x channels x freq x time
    else
        num_channels = ps(1);
    end
    labels = arrayfun(@(i) sprintf('Ch %d', i), 1:num_channels, 'UniformOutput', false);
end

if isfield(first_nonempty, 'freq'), freq = first_nonempty.freq; else, freq = []; end
if isfield(first_nonempty, 'time'), timeVec = first_nonempty.time; else, timeVec = []; end
end
