function spectral_visualizer(spectral_records)
% SPECTRAL_VISUALIZER Interactive visualization of spectral analysis results
%
%   spectral_visualizer(spectral_records) creates an interactive figure to
%   browse subjects and channels from spectral_output.mat. Expects input to
%   be a subjects x 3 struct array (target/standard/novelty) or a vector of
%   structs with fields target/standard/novelty.

spectral_records = normalize_spectral_records(spectral_records);
num_subjects = size(spectral_records, 1);

fig = figure('Name', 'Spectral Analysis Visualization', 'NumberTitle', 'off', ...
    'Position', [50, 50, 1400, 900], 'WindowState', 'maximized', ...
    'Color', [1 1 1], 'Visible', 'off');
colormap(fig, 'jet');

data.spectral_records = spectral_records;
data.num_subjects = num_subjects;
data.current_subject = 1;
[data.channel_labels, data.freq_vector] = get_channel_labels_and_freq(spectral_records);
if isempty(data.channel_labels)
    error('spectral_visualizer:InvalidInput', 'No channel labels found in spectral data.');
end
data.selected_channel_indices = [];

guidata(fig, data);
create_ui_controls(fig, data);

if strcmp(get(fig, 'Visible'), 'off')
    set(fig, 'Visible', 'on');
    drawnow;
end

plot_subject(fig);

end

function out = normalize_spectral_records(in)
if isnumeric(in)
    error('spectral_visualizer:InvalidInput', 'Expected struct input, received numeric.');
end

if ndims(in) == 2 && size(in, 2) == 3 && isstruct(in)
    out = in;
    return;
end

requiredFields = {'target', 'standard', 'novelty'};
if isstruct(in) && isvector(in) && all(isfield(in, requiredFields))
    numSubjects = numel(in);
    defaultRecord = struct('fourierspctrm', [], 'freq', [], 'label', [], 'dimord', '', 'cfg', []);
    out = repmat(defaultRecord, numSubjects, 3);
    for iSub = 1:numSubjects
        for j = 1:3
            fieldName = requiredFields{j};
            if ~isempty(in(iSub).(fieldName))
                out(iSub, j) = normalize_condition(in(iSub).(fieldName), defaultRecord);
            end
        end
    end
    return;
end

error('spectral_visualizer:InvalidInput', ['Unsupported spectral data format. Expected an (subjects x 3) struct array or a vector ', ...
    'struct with fields target, standard, novelty.']);
end

function cond = normalize_condition(inCond, template)
% Ensure the stored condition struct has the expected fields to avoid
% "Subscripted assignment between dissimilar structures" errors.
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

% Preserve freq/label if they exist with different shapes
if isfield(inCond, 'freq'), cond.freq = inCond.freq; end
if isfield(inCond, 'label'), cond.label = inCond.label; end
end

function navigate_subject(fig, direction)
data = guidata(fig);
new_subject = data.current_subject + direction;
if new_subject < 1
    new_subject = 1;
elseif new_subject > data.num_subjects
    new_subject = data.num_subjects;
end
if new_subject ~= data.current_subject
    data.current_subject = new_subject;
    guidata(fig, data);
    plot_subject(fig);
end
end

function plot_subject(fig)
data = guidata(fig);

target_data = data.spectral_records(data.current_subject, 1);
standard_data = data.spectral_records(data.current_subject, 2);
novelty_data = data.spectral_records(data.current_subject, 3);

num_channels = numel(data.channel_labels);
selected_channels = data.selected_channel_indices;
selected_channels = selected_channels(selected_channels <= num_channels);
data.selected_channel_indices = selected_channels;

delete(findall(fig, 'Type', 'axes'));

num_selected = numel(selected_channels);
if num_selected == 0
    guidata(fig, data);
    return;
end

for idx = 1:num_selected
    channel = selected_channels(idx);
    channel_label = data.channel_labels{channel};
    
    subplot(num_selected, 3, (idx-1)*3 + 1);
    plot_condition(target_data, channel, data);
    ylabel(channel_label);
    if ~isempty(data.xlim_override); xlim(data.xlim_override); end
    if ~isempty(data.ylim_override); ylim(data.ylim_override); end
    if idx == 1; title('Target'); end
    if idx == num_selected; xlabel('Frequency (Hz)'); end
    grid on;
    
    subplot(num_selected, 3, (idx-1)*3 + 2);
    plot_condition(standard_data, channel, data);
    if ~isempty(data.xlim_override); xlim(data.xlim_override); end
    if ~isempty(data.ylim_override); ylim(data.ylim_override); end
    if idx == 1; title('Standard'); end
    if idx == num_selected; xlabel('Frequency (Hz)'); end
    grid on;
    
    subplot(num_selected, 3, (idx-1)*3 + 3);
    plot_condition(novelty_data, channel, data);
    if ~isempty(data.xlim_override); xlim(data.xlim_override); end
    if ~isempty(data.ylim_override); ylim(data.ylim_override); end
    if idx == 1; title('Novelty'); end
    if idx == num_selected; xlabel('Frequency (Hz)'); end
    grid on;
end

sgtitle(sprintf('Spectral Analysis - Subject %d/%d', data.current_subject, data.num_subjects));

guidata(fig, data);
end

function plot_condition(condData, channelIdx, data)
[freq, powerMatrix] = extract_power(condData);
if isempty(freq) || isempty(powerMatrix)
    text(0.5, 0.5, 'No data', 'HorizontalAlignment', 'center');
    return;
end

if channelIdx > size(powerMatrix, 1)
    text(0.5, 0.5, 'Channel missing', 'HorizontalAlignment', 'center');
    return;
end

plot(freq, squeeze(powerMatrix(channelIdx, :)));
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
    'Position', [75, 128, 20, 20], ...
    'Callback', @(src, evt) update_axis_limits(fig, 'x'));
uicontrol('Style', 'text', 'String', 'max:', ...
    'Position', [100, 130, 30, 15], 'HorizontalAlignment', 'left');
data.xlim_max_edit = uicontrol('Style', 'edit', 'String', '', ...
    'Position', [130, 128, 20, 20], ...
    'Callback', @(src, evt) update_axis_limits(fig, 'x'));

uicontrol('Style', 'text', 'String', 'ylim  min:', ...
    'Position', [20, 100, 55, 15], 'HorizontalAlignment', 'left');
data.ylim_min_edit = uicontrol('Style', 'edit', 'String', '', ...
    'Position', [75, 98, 20, 20], ...
    'Callback', @(src, evt) update_axis_limits(fig, 'y'));
uicontrol('Style', 'text', 'String', 'max:', ...
    'Position', [100, 100, 30, 15], 'HorizontalAlignment', 'left');
data.ylim_max_edit = uicontrol('Style', 'edit', 'String', '', ...
    'Position', [130, 98, 20, 20], ...
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
        warndlg('Enter numeric min < max for xlim.', 'Invalid axis limits');
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
        warndlg('Enter numeric min < max for ylim.', 'Invalid axis limits');
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

function [labels, freq] = get_channel_labels_and_freq(spectral_records)
first_nonempty = [];
for i = 1:numel(spectral_records)
    if ~isempty(spectral_records(i).fourierspctrm)
        first_nonempty = spectral_records(i);
        break;
    end
end

if isempty(first_nonempty)
    labels = {};
    freq = [];
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
    fsz = size(first_nonempty.fourierspctrm);
    if numel(fsz) >= 2
        num_channels = fsz(end-1);
    else
        num_channels = size(first_nonempty.fourierspctrm, 1);
    end
    labels = arrayfun(@(i) sprintf('Ch %d', i), 1:num_channels, 'UniformOutput', false);
end

if isfield(first_nonempty, 'freq')
    freq = first_nonempty.freq;
else
    freq = [];
end
end

function [freq, powerMatrix] = extract_power(condData)
freq = [];
powerMatrix = [];
if isempty(condData) || ~isstruct(condData) || ~isfield(condData, 'fourierspctrm')
    return;
end

fouriers = condData.fourierspctrm;
freq = condData.freq;

magsq = abs(fouriers).^2;
if ndims(magsq) >= 3
    magsq = squeeze(mean(magsq, 1));
else
    magsq = squeeze(magsq);
end

if isvector(magsq)
    magsq = magsq(:).';
end

if ~isempty(freq)
    if size(magsq, 1) == numel(freq) && size(magsq, 2) ~= numel(freq)
        magsq = magsq.';
    elseif size(magsq, 2) ~= numel(freq) && size(magsq, 1) ~= numel(freq)
        if size(magsq, 1) > size(magsq, 2)
            magsq = magsq.';
        end
    end
end

powerMatrix = magsq;
end
