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

% Create figure with 12x3 grid
fig = figure('Name', 'ERP Analysis Visualization', 'NumberTitle', 'off', ...
    'Position', [50, 50, 1400, 900], 'WindowState', 'maximized');

% Create data structure to store current state
data.erp_records = erp_records;
data.num_subjects = num_subjects;
data.current_subject = 1;

% Create UI controls for navigation
data.prev_btn = uicontrol('Style', 'pushbutton', 'String', '← Previous', ...
    'Position', [20, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, -1));

data.next_btn = uicontrol('Style', 'pushbutton', 'String', 'Next →', ...
    'Position', [130, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, 1));

data.subject_label = uicontrol('Style', 'text', 'String', ...
    sprintf('Subject: 1/%d', num_subjects), ...
    'Position', [240, 20, 150, 30], ...
    'FontSize', 10);

% Store data in figure
guidata(fig, data);

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
    set(data.subject_label, 'String', sprintf('Subject: %d/%d', new_subject, data.num_subjects));
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

% Clear existing plots
clf(fig, 'reset');

% Recreate UI controls (since clf removes them)
data.prev_btn = uicontrol('Style', 'pushbutton', 'String', '← Previous', ...
    'Position', [20, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, -1));

data.next_btn = uicontrol('Style', 'pushbutton', 'String', 'Next →', ...
    'Position', [130, 20, 100, 30], ...
    'Callback', @(src, evt) navigate_subject(fig, 1));

data.subject_label = uicontrol('Style', 'text', 'String', ...
    sprintf('Subject: %d/%d', data.current_subject, data.num_subjects), ...
    'Position', [240, 20, 150, 30], ...
    'FontSize', 10);

guidata(fig, data);

% Get number of channels (should be 12)
num_channels = size(target_data.avg, 1);

% Create 12x3 grid of subplots (12 channels x 3 conditions)
for channel = 1:num_channels
    % Target column (column 1)
    subplot(num_channels, 3, (channel-1)*3 + 1);
    plot(target_data.time, target_data.avg(channel, :));
    ylabel(sprintf('Ch %d', channel));
    if channel == 1
        title('Target');
    end
    if channel == num_channels
        xlabel('Time (s)');
    end
    grid on;
    
    % Standard column (column 2)
    subplot(num_channels, 3, (channel-1)*3 + 2);
    plot(standard_data.time, standard_data.avg(channel, :));
    if channel == 1
        title('Standard');
    end
    if channel == num_channels
        xlabel('Time (s)');
    end
    grid on;
    
    % Novelty column (column 3)
    subplot(num_channels, 3, (channel-1)*3 + 3);
    plot(novelty_data.time, novelty_data.avg(channel, :));
    if channel == 1
        title('Novelty');
    end
    if channel == num_channels
        xlabel('Time (s)');
    end
    grid on;
end

% Add main title with subject info
sgtitle(sprintf('ERP Analysis - Subject %d/%d', data.current_subject, data.num_subjects));
end
