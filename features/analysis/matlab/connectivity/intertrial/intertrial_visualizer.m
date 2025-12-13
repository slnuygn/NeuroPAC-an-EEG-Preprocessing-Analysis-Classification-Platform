function intertrial_visualizer(itc_records)
% INTERTRIAL_VISUALIZER Interactive visualization of inter-trial coherence (ITPC).
%
%   intertrial_visualizer(itc_records) expects data from
%   intertrial_coherence_output.mat (subjects x 3 struct array with
%   target/standard/novelty). Displays per-channel ITPC time-frequency maps
%   in a channel x condition grid, similar to erp_visualizer.

% Normalize to subjects x 3 struct array
itc_records = normalize_itc_records(itc_records);
num_subjects = size(itc_records, 1);

% Figure
fig = figure('Name', 'Inter-Trial Coherence Visualization', 'NumberTitle', 'off', ...
    'Position', [50, 50, 1400, 900], 'WindowState', 'maximized', ...
    'Color', [1 1 1], 'Visible', 'off');

data.itc_records = itc_records;
data.num_subjects = num_subjects;
data.current_subject = 1;
data.channel_labels = get_channel_labels(itc_records);
data.selected_channel_indices = 1:numel(data.channel_labels);
data.xlim_override = [];
data.ylim_override = [];
data.coherence_mode = 'phase'; % 'phase' (ITPC) or 'linear' (ITLC)

guidata(fig, data);
create_ui_controls(fig, data);

if strcmp(get(fig, 'Visible'), 'off')
    set(fig, 'Visible', 'on');
    drawnow;
end

plot_subject(fig);

end

function out = normalize_itc_records(in)
if isnumeric(in)
    error('intertrial_visualizer:InvalidInput', 'Expected struct input, received numeric.');
end
if ndims(in) == 2 && size(in,2) == 3 && isstruct(in)
    out = in;
    return;
end
req = {'target','standard','novelty'};
if isstruct(in) && isvector(in) && all(isfield(in, req))
    n = numel(in);
    template = struct('itpc', [], 'itlc', [], 'label', [], 'freq', [], 'time', [], 'dimord', '', 'cfg', []);
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
error('intertrial_visualizer:InvalidInput', ['Unsupported ITC data format. Expected an (subjects x 3) struct array or a vector ', ...
    'struct with fields target, standard, novelty.']);
end

function cond = normalize_condition(inCond, template)
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
end

function labels = get_channel_labels(itc_records)
first = itc_records(1,1);
if isfield(first,'label') && ~isempty(first.label)
    raw = first.label;
    if isstring(raw) || ischar(raw)
        labels = cellstr(raw);
    else
        labels = raw;
    end
else
    if isfield(first,'itpc') && ~isempty(first.itpc)
        labels = arrayfun(@(i) sprintf('Ch %d', i), 1:size(first.itpc,1), 'UniformOutput', false);
    else
        labels = {};
    end
end
end

function plot_subject(fig)
data = guidata(fig);

target_data = data.itc_records(data.current_subject,1);
standard_data = data.itc_records(data.current_subject,2);
novelty_data = data.itc_records(data.current_subject,3);

num_channels = numel(data.channel_labels);
selected_channels = data.selected_channel_indices;
selected_channels = selected_channels(selected_channels <= num_channels);
data.selected_channel_indices = selected_channels;

% Clear axes only
delete(findall(fig, 'Type', 'axes'));

num_selected = numel(selected_channels);
if num_selected == 0
    uicontrol('Style','text','String','No channels selected', ...
        'Position',[200 200 200 40]);
    guidata(fig, data);
    return;
end

conds = {target_data, standard_data, novelty_data};
titles = {'Target','Standard','Novelty'};

for idx = 1:num_selected
    ch = selected_channels(idx);
    ch_label = data.channel_labels{ch};
    for c = 1:3
        subplot(num_selected,3,(idx-1)*3 + c);
        plot_itc(conds{c}, ch, ch_label, data);
        if idx == 1
            title(titles{c});
        end
        if idx == num_selected
            xlabel('Time (s)');
        end
    end
end

mode_label = 'Phase';
if strcmp(data.coherence_mode,'linear')
    mode_label = 'Linear';
end
sgtitle(sprintf('Inter-Trial Coherence (%s) - Subject %d/%d', mode_label, data.current_subject, data.num_subjects));

guidata(fig, data);
end

function plot_itc(condData, chIdx, chLabel, data)
if isempty(condData)
    text(0.5,0.5,'No data','HorizontalAlignment','center');
    return;
end

freqVec = [];
timeVec = [];
if isfield(condData,'freq'), freqVec = condData.freq; end
if isfield(condData,'time'), timeVec = condData.time; end

if strcmp(data.coherence_mode,'linear')
    fieldName = 'itlc';
else
    fieldName = 'itpc';
end

if ~isfield(condData, fieldName) || isempty(condData.(fieldName))
    text(0.5,0.5,'No data','HorizontalAlignment','center');
    return;
end

if chIdx > size(condData.(fieldName),1)
    text(0.5,0.5,'Channel missing','HorizontalAlignment','center');
    return;
end

Z = squeeze(condData.(fieldName)(chIdx,:,:)); % freq x time

imagesc(timeVec, freqVec, Z);
axis xy;
colormap(parula);
colorbar;
if ~isempty(data.xlim_override), xlim(data.xlim_override); end
if ~isempty(data.ylim_override), ylim(data.ylim_override); end
ylabel(chLabel);
end

function create_ui_controls(fig, data)

% nav buttons
uicontrol('Style','pushbutton','String','← Previous', ...
    'Position',[20 20 100 30], ...
    'Callback',@(src,evt) navigate_subject(fig,-1));

uicontrol('Style','pushbutton','String','Next →', ...
    'Position',[130 20 100 30], ...
    'Callback',@(src,evt) navigate_subject(fig,1));

uicontrol('Style','text','String','Coherence:', ...
    'Position',[250 25 70 20],'HorizontalAlignment','left');
uicontrol('Style','popupmenu','String',{'Phase','Linear'}, ...
    'Value',1, ...
    'Position',[320 20 80 30], ...
    'Callback',@(src,evt) set_coherence_mode(fig, src));

% axis limit controls
uicontrol('Style','text','String','xlim  min:', ...
    'Position',[20 130 55 15],'HorizontalAlignment','left');
data.xlim_min_edit = uicontrol('Style','edit','String','', ...
    'Position',[75 128 30 20], ...
    'Callback',@(src,evt) update_axis_limits(fig,'x'));
uicontrol('Style','text','String','max:', ...
    'Position',[110 130 30 15],'HorizontalAlignment','left');
data.xlim_max_edit = uicontrol('Style','edit','String','', ...
    'Position',[140 128 30 20], ...
    'Callback',@(src,evt) update_axis_limits(fig,'x'));

uicontrol('Style','text','String','ylim  min:', ...
    'Position',[20 100 55 15],'HorizontalAlignment','left');
data.ylim_min_edit = uicontrol('Style','edit','String','', ...
    'Position',[75 98 30 20], ...
    'Callback',@(src,evt) update_axis_limits(fig,'y'));
uicontrol('Style','text','String','max:', ...
    'Position',[110 100 30 15],'HorizontalAlignment','left');
data.ylim_max_edit = uicontrol('Style','edit','String','', ...
    'Position',[140 98 30 20], ...
    'Callback',@(src,evt) update_axis_limits(fig,'y'));

% channel chooser panel
toggle_btn = uicontrol('Style','pushbutton','String','Channels', ...
    'Position',[20 60 120 30], ...
    'Callback',@(src,evt) toggle_channel_panel(fig));

num_channels = numel(data.channel_labels);
panel_height = 30 + num_channels * 22;
panel_width = 200;
panel = uipanel('Parent', fig, 'Units', 'pixels', ...
    'Position',[20, 60 + 30, panel_width, panel_height], ...
    'BorderType','etchedin', ...
    'Visible','off');

all_selected = numel(data.selected_channel_indices) == num_channels;
all_cb = uicontrol('Parent', panel, 'Style','checkbox', ...
    'String','All Channels', ...
    'Value', all_selected, ...
    'Position',[10, panel_height - 25, panel_width - 20, 20], ...
    'Callback',[]);

channel_cbs = cell(1, num_channels);
for i = 1:num_channels
    y = panel_height - 25 - (i*22);
    channel_cbs{i} = uicontrol('Parent', panel, 'Style','checkbox', ...
        'String', data.channel_labels{i}, ...
        'Value', ismember(i, data.selected_channel_indices), ...
        'Position', [10, y, panel_width - 20, 20], ...
        'Callback', []);
end

set(all_cb,'Callback',@(src,evt) handle_all_checkbox(fig, src, channel_cbs));
for i = 1:num_channels
    set(channel_cbs{i},'Callback',@(src,evt) handle_channel_checkbox(fig, all_cb, channel_cbs, i));
end

data.channel_panel = panel;
data.channel_checkboxes = channel_cbs;
data.channel_all_checkbox = all_cb;
data.channel_panel_visible = false;
data.channel_toggle_btn = toggle_btn;

guidata(fig, data);
end

function handle_all_checkbox(fig, all_cb, channel_cbs)
value = get(all_cb,'Value');
for i = 1:numel(channel_cbs)
    set(channel_cbs{i},'Value', value);
end
if value == 1
    set_selected_channels(fig, 1:numel(channel_cbs));
else
    set_selected_channels(fig, []);
end
end

function handle_channel_checkbox(fig, all_cb, channel_cbs, idx)
vals = cellfun(@(cb) logical(get(cb,'Value')), channel_cbs);
if all(vals)
    set(all_cb,'Value',1);
else
    set(all_cb,'Value',0);
end
selected = find(vals);
set_selected_channels(fig, selected);
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
        warndlg('Enter numeric min < max for xlim.','Invalid axis limits');
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
        warndlg('Enter numeric min < max for ylim.','Invalid axis limits');
        return;
    end
end
guidata(fig, data);
plot_subject(fig);
end

function set_selected_channels(fig, selected_indices)
data = guidata(fig);
num_channels = numel(data.channel_labels);
selected_indices = selected_indices(selected_indices >=1 & selected_indices <= num_channels);
data.selected_channel_indices = selected_indices;

guidata(fig, data);
plot_subject(fig);
end

function toggle_channel_panel(fig)
data = guidata(fig);
is_visible = strcmp(get(data.channel_panel,'Visible'),'on');
if is_visible
    set(data.channel_panel,'Visible','off');
    set(data.channel_toggle_btn,'String','Channels');
    data.channel_panel_visible = false;
else
    set(data.channel_panel,'Visible','on');
    set(data.channel_toggle_btn,'String','Channels (open)');
    data.channel_panel_visible = true;
end

guidata(fig, data);
end

function set_coherence_mode(fig, popup)
data = guidata(fig);
val = get(popup,'Value');
if val == 2
    data.coherence_mode = 'linear';
else
    data.coherence_mode = 'phase';
end
guidata(fig, data);
plot_subject(fig);
end
