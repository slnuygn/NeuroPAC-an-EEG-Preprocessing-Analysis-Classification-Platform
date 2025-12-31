% Initialize FieldTrip
addpath('C:/FIELDTRIP');  % Replace with your FieldTrip path
ft_defaults;

% Set the directory containing the .set files
data_dir = 'C:/Users/mamam/Desktop/parkinsons';  % Will be updated by the GUI file browser when folder is selected

% Get the preprocessing script directory and add to path
preprocessing_dir = fileparts(mfilename('fullpath'));
addpath(preprocessing_dir);

% Change to data directory to find .set files
cd(data_dir);
files = dir('*.set');


% Define batch size and output file
batch_size = 5;
raw_output_filename = fullfile(data_dir, 'data.mat');
total_processed = 0;

% Load existing data if available for resuming
if exist(raw_output_filename, 'file')
    load(raw_output_filename, 'data');
    total_processed = length(data);
    fprintf('Loaded existing data with %d subjects. Resuming from subject %d...\n', total_processed, total_processed + 1);
else
    data = [];
end

% Loop through each .set file in batches
for i = 1:length(files)
    
    filename = files(i).name;
    fprintf('Processing %s (%d/%d)...\n', filename, i, length(files));
    
    % Load the data
    dataset = fullfile(data_dir, filename);
    
    % Process the data
    processed = preprocess_data(dataset);
    data = [data; processed];
    
    % Save batch every 10 subjects
    if mod(i, batch_size) == 0 || i == length(files)
        save(raw_output_filename, 'data', '-v7.3');
        fprintf('Batch saved! Progress: %d/%d subjects processed.\n', i, length(files));
        clear processed;  % Free memory
    end
    
end

fprintf('Batch processing complete. %d files processed and stored in workspace variable "data"\n', length(data));
fprintf('Preprocessed data saved to: %s\n', raw_output_filename);

% Apply ICA in batches to the preprocessed data
ica_output_filename = fullfile(data_dir, 'data_ICApplied.mat');
total_ica_processed = 0;

% Load existing ICA data if available for resuming
if exist(ica_output_filename, 'file')
    load(ica_output_filename, 'data_ICApplied');
    total_ica_processed = length(data_ICApplied);
    fprintf('Loaded existing ICA data with %d subjects. Resuming from subject %d...\n', total_ica_processed, total_ica_processed + 1);
else
    data_ICApplied = [];
end

% Apply ICA in batches
fprintf('Applying ICA to preprocessed data in batches...\n');
for i = total_ica_processed + 1:length(data)
    
    fprintf('Applying ICA to subject %d/%d...\n', i, length(data));
    
    % Apply ICA to single subject
    ica_processed = applyICA(data(i));
    data_ICApplied = [data_ICApplied; ica_processed];
    
    % Save batch every 10 subjects
    if mod(i, batch_size) == 0 || i == length(data)
        save(ica_output_filename, 'data_ICApplied', '-v7.3');
        fprintf('ICA batch saved! Progress: %d/%d subjects ICA-processed.\n', i, length(data));
        clear ica_processed;  % Free memory
    end
    
end

fprintf('ICA processing complete.\n');

