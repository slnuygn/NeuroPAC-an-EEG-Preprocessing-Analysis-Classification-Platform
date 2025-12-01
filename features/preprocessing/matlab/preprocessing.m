% Initialize FieldTrip
addpath('C:/FIELDTRIP');  % Replace with your FieldTrip path
ft_defaults;

% Set the directory containing the .set files
data_dir = 'C:/Users/mamam/Desktop/data';  % Will be updated by the GUI file browser when folder is selected

% Get the preprocessing script directory and add to path
preprocessing_dir = fileparts(mfilename('fullpath'));
addpath(preprocessing_dir);

% Change to data directory to find .set files
cd(data_dir);
files = dir('*.set');


% Loop through each .set file
for i = 1:length(files)
    
    filename = files(i).name;
    fprintf('Processing %s...\n', filename);
    
    % Load the data
    dataset = fullfile(data_dir, filename);
    
    % Process the data - this automatically stores in MATLAB workspace
    data(i) = preprocess_data(dataset);
    
end

fprintf('Batch processing complete. %d files processed and stored in workspace variable "data"\n', length(data));

% Save the preprocessed data prior to ICA for reproducibility
raw_output_filename = fullfile(data_dir, 'data.mat');
save(raw_output_filename, 'data', '-v7.3');
fprintf('Preprocessed data saved to: %s\n', raw_output_filename);

% Apply ICA to the preprocessed data
fprintf('Applying ICA to preprocessed data...\n');
data_ICApplied = applyICA(data);
fprintf('ICA processing complete.\n');

% Save the final ICA-processed data
ica_output_filename = fullfile(data_dir, 'data_ICApplied.mat');
save(ica_output_filename, 'data_ICApplied', '-v7.3');
fprintf('Final ICA-processed data saved to: %s\n', ica_output_filename);

