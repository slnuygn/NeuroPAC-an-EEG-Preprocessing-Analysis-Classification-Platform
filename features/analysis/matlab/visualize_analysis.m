function visualize_analysis(analysis_results)
% VISUALIZE_ANALYSIS Visualizes the results of the analysis.
%
%   visualize_analysis(analysis_results) takes the results from an
%   analysis and generates appropriate visualizations.
%
%   Input:
%       analysis_results - A structure containing the results of the
%                          analysis to be visualized.
%
%   Example:
%       results = perform_analysis(data);
%       visualize_analysis(results);

% Determine the type of analysis results
if isfield(analysis_results, 'timefreq_output')
    analysis_type = 'timefreq_output';
    num_subjects = size(analysis_results.timefreq_output, 1);
elseif isfield(analysis_results, 'spectral_output')
    analysis_type = 'spectral_output';
    num_subjects = size(analysis_results.spectral_output, 1);
elseif isfield(analysis_results, 'erp_output')
    analysis_type = 'erp_output';
    num_subjects = size(analysis_results.erp_output, 1);
elseif isfield(analysis_results, 'channelwise_coherence_output')
    analysis_type = 'channelwise_coherence_output';
    num_subjects = size(analysis_results.channelwise_coherence_output, 1);
elseif isfield(analysis_results, 'intertrial_coherence_output')
    analysis_type = 'intertrial_coherence_output';
    num_subjects = size(analysis_results.intertrial_coherence_output, 1);
else
    error('Unknown analysis result type. Cannot determine visualization method.');
end

% Create figure with 2x2 grid
fig = figure('Name', 'Analysis Visualization', 'NumberTitle', 'off', ...
    'Position', [100, 100, 1200, 800]);

% Create data structure to store current state
data.analysis_results = analysis_results;
data.analysis_type = analysis_type;
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

% Create 2x2 grid of subplots
subplot(2, 2, 1);
% Plot 1 content will go here
title(sprintf('Plot 1 - Subject %d', data.current_subject));

subplot(2, 2, 2);
% Plot 2 content will go here
title(sprintf('Plot 2 - Subject %d', data.current_subject));

subplot(2, 2, 3);
% Plot 3 content will go here
title(sprintf('Plot 3 - Subject %d', data.current_subject));

subplot(2, 2, 4);
% Plot 4 content will go here
title(sprintf('Plot 4 - Subject %d', data.current_subject));

% Now fill in plots based on analysis type
switch data.analysis_type
    case 'timefreq_output'
        plot_timefreq(data);
        
    case 'spectral_output'
        plot_spectral(data);
        
    case 'erp_output'
        plot_erp(data);
        
    case 'channelwise_coherence_output'
        plot_channelwise_coherence(data);
        
    case 'intertrial_coherence_output'
        plot_intertrial_coherence(data);
end
end

% Specific plotting functions for each analysis type
function plot_timefreq(data)
% Time-frequency specific plotting
subject_data = data.analysis_results.timefreq_output(data.current_subject, :);

subplot(2, 2, 1);
% Add time-frequency plot 1 here
text(0.5, 0.5, 'Time-Frequency Plot 1', 'HorizontalAlignment', 'center');

subplot(2, 2, 2);
% Add time-frequency plot 2 here
text(0.5, 0.5, 'Time-Frequency Plot 2', 'HorizontalAlignment', 'center');

subplot(2, 2, 3);
% Add time-frequency plot 3 here
text(0.5, 0.5, 'Time-Frequency Plot 3', 'HorizontalAlignment', 'center');

subplot(2, 2, 4);
% Add time-frequency plot 4 here
text(0.5, 0.5, 'Time-Frequency Plot 4', 'HorizontalAlignment', 'center');
end

function plot_spectral(data)
% Spectral specific plotting
subject_data = data.analysis_results.spectral_output(data.current_subject, :);

subplot(2, 2, 1);
% Add spectral plot 1 here
text(0.5, 0.5, 'Spectral Plot 1', 'HorizontalAlignment', 'center');

subplot(2, 2, 2);
% Add spectral plot 2 here
text(0.5, 0.5, 'Spectral Plot 2', 'HorizontalAlignment', 'center');

subplot(2, 2, 3);
% Add spectral plot 3 here
text(0.5, 0.5, 'Spectral Plot 3', 'HorizontalAlignment', 'center');

subplot(2, 2, 4);
% Add spectral plot 4 here
text(0.5, 0.5, 'Spectral Plot 4', 'HorizontalAlignment', 'center');
end

function plot_erp(data)
% ERP specific plotting
subject_data = data.analysis_results.erp_output(data.current_subject, :);

subplot(2, 2, 1);
% Add ERP plot 1 here
text(0.5, 0.5, 'ERP Plot 1', 'HorizontalAlignment', 'center');

subplot(2, 2, 2);
% Add ERP plot 2 here
text(0.5, 0.5, 'ERP Plot 2', 'HorizontalAlignment', 'center');

subplot(2, 2, 3);
% Add ERP plot 3 here
text(0.5, 0.5, 'ERP Plot 3', 'HorizontalAlignment', 'center');

subplot(2, 2, 4);
% Add ERP plot 4 here
text(0.5, 0.5, 'ERP Plot 4', 'HorizontalAlignment', 'center');
end

function plot_channelwise_coherence(data)
% Channelwise coherence specific plotting
subject_data = data.analysis_results.channelwise_coherence_output(data.current_subject, :);

subplot(2, 2, 1);
% Add channelwise coherence plot 1 here
text(0.5, 0.5, 'Channelwise Coherence Plot 1', 'HorizontalAlignment', 'center');

subplot(2, 2, 2);
% Add channelwise coherence plot 2 here
text(0.5, 0.5, 'Channelwise Coherence Plot 2', 'HorizontalAlignment', 'center');

subplot(2, 2, 3);
% Add channelwise coherence plot 3 here
text(0.5, 0.5, 'Channelwise Coherence Plot 3', 'HorizontalAlignment', 'center');

subplot(2, 2, 4);
% Add channelwise coherence plot 4 here
text(0.5, 0.5, 'Channelwise Coherence Plot 4', 'HorizontalAlignment', 'center');
end

function plot_intertrial_coherence(data)
% Intertrial coherence specific plotting
subject_data = data.analysis_results.intertrial_coherence_output(data.current_subject, :);

subplot(2, 2, 1);
% Add intertrial coherence plot 1 here
text(0.5, 0.5, 'Intertrial Coherence Plot 1', 'HorizontalAlignment', 'center');

subplot(2, 2, 2);
% Add intertrial coherence plot 2 here
text(0.5, 0.5, 'Intertrial Coherence Plot 2', 'HorizontalAlignment', 'center');

subplot(2, 2, 3);
% Add intertrial coherence plot 3 here
text(0.5, 0.5, 'Intertrial Coherence Plot 3', 'HorizontalAlignment', 'center');

subplot(2, 2, 4);
% Add intertrial coherence plot 4 here
text(0.5, 0.5, 'Intertrial Coherence Plot 4', 'HorizontalAlignment', 'center');
end