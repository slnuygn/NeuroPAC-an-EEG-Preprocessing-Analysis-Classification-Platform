function itc_data = intertrialcoherenceanalysis(inputPath)
% Inter-trial coherence analysis for decomposed cleaned ICA data stored as data_ICApplied_clean_decomposed.mat

if nargin < 1 || isempty(inputPath)
    error('intertrialcoherenceanalysis requires a folder path containing data_ICApplied_clean_decomposed.mat.');
end

% Resolve folder and target file
if isfolder(inputPath)
    dataFolder = inputPath;
else
    [dataFolder, fileName, fileExt] = fileparts(inputPath);
    if isempty(dataFolder)
        dataFolder = pwd;
    end
    if ~strcmpi([fileName fileExt], 'data_ICApplied_clean_decomposed.mat')
        fprintf('Input path is a file (%s %s). Using containing folder: %s\n', fileName, fileExt, dataFolder);
    end
end

matFilePath = fullfile(dataFolder, 'data_ICApplied_clean_decomposed.mat');
fprintf('Loading data from: %s\n', matFilePath);

if ~exist(matFilePath, 'file')
    error('Required file data_ICApplied_clean_decomposed.mat not found in %s', dataFolder);
end

% Load the cleaned data
try
    loadedData = load(matFilePath, 'clean_data_decomposed');
catch loadErr
    error('Failed to load data_ICApplied_clean_decomposed.mat: %s', loadErr.message);
end

if ~isfield(loadedData, 'clean_data_decomposed')
    error('Variable "clean_data_decomposed" not found inside data_ICApplied_clean_decomposed.mat.');
end

data_decomposed = loadedData.clean_data_decomposed;
fprintf('Successfully loaded clean_data_decomposed\n');

numTrials = numel(data_decomposed);
fprintf('Number of trials/subjects: %d\n', numTrials);

% Define configuration for frequency computation (from freqcompute.m)
cfg = [];
cfg.method = 'wavelet';
cfg.output = 'fourier';
cfg.foi = 1:0.5:15;
cfg.toi = -2:0.01:2;
cfg.width = 3;
cfg.pad = 8;

% Initialize output structure
itc_data = struct( ...
    'target', cell(1, numTrials), ...
    'standard', cell(1, numTrials), ...
    'novelty', cell(1, numTrials));

fprintf('Starting inter-trial coherence analysis...\n');
for i = 1:numTrials
    fprintf('Inter-trial coherence analysis for trial %d/%d\n', i, numTrials);
    
    % Process target condition
    if isfield(data_decomposed(i), 'target') && ~isempty(data_decomposed(i).target)
        cfg.trials = 1:length(data_decomposed(i).target.trial);
        freq_target = ft_freqanalysis(cfg, data_decomposed(i).target);
        itc_target = compute_itc(freq_target);
        itc_data(i).target = itc_target;
    end
    
    % Process standard condition
    if isfield(data_decomposed(i), 'standard') && ~isempty(data_decomposed(i).standard)
        cfg.trials = 1:length(data_decomposed(i).standard.trial);
        freq_standard = ft_freqanalysis(cfg, data_decomposed(i).standard);
        itc_standard = compute_itc(freq_standard);
        itc_data(i).standard = itc_standard;
    end
    
    % Process novelty condition
    if isfield(data_decomposed(i), 'novelty') && ~isempty(data_decomposed(i).novelty)
        cfg.trials = 1:length(data_decomposed(i).novelty.trial);
        freq_novelty = ft_freqanalysis(cfg, data_decomposed(i).novelty);
        itc_novelty = compute_itc(freq_novelty);
        itc_data(i).novelty = itc_novelty;
    end
end
fprintf('Inter-trial coherence analysis completed\n');

% Save results
outputPath = fullfile(dataFolder, 'intertrial_coherence_output.mat');
save(outputPath, 'itc_data');
fprintf('Inter-trial coherence analysis results saved to %s\n', outputPath);
end