function coherence_data = channelwise(inputPath)
% Channel-wise coherence analysis for decomposed cleaned ICA data stored as data_ICApplied_clean_decomposed.mat

if nargin < 1 || isempty(inputPath)
    error('channelwise requires a folder path containing data_ICApplied_clean_decomposed.mat.');
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

% Define configuration for time selection
cfg_select = [];
cfg_select.latency = [0 1];

% Define configuration for coherence analysis
cfgC = [];
cfgC.method = 'coh';

% Initialize output structure
coherence_data = struct( ...
    'target', cell(1, numTrials), ...
    'standard', cell(1, numTrials), ...
    'novelty', cell(1, numTrials));

fprintf('Starting channel-wise coherence analysis...\n');
for i = 1:numTrials
    fprintf('Channel-wise coherence analysis for trial %d/%d\n', i, numTrials);
    
    % Process target condition
    if isfield(data_decomposed(i), 'target') && ~isempty(data_decomposed(i).target)
        cfg.trials = 1:length(data_decomposed(i).target.trial);
        freq_target = ft_freqanalysis(cfg, data_decomposed(i).target);
        freq_target_selected = ft_selectdata(cfg_select, freq_target);
        coh_target = ft_connectivityanalysis(cfgC, freq_target_selected);
        coherence_data(i).target = coh_target;
    end
    
    % Process standard condition
    if isfield(data_decomposed(i), 'standard') && ~isempty(data_decomposed(i).standard)
        cfg.trials = 1:length(data_decomposed(i).standard.trial);
        freq_standard = ft_freqanalysis(cfg, data_decomposed(i).standard);
        freq_standard_selected = ft_selectdata(cfg_select, freq_standard);
        coh_standard = ft_connectivityanalysis(cfgC, freq_standard_selected);
        coherence_data(i).standard = coh_standard;
    end
    
    % Process novelty condition
    if isfield(data_decomposed(i), 'novelty') && ~isempty(data_decomposed(i).novelty)
        cfg.trials = 1:length(data_decomposed(i).novelty.trial);
        freq_novelty = ft_freqanalysis(cfg, data_decomposed(i).novelty);
        freq_novelty_selected = ft_selectdata(cfg_select, freq_novelty);
        coh_novelty = ft_connectivityanalysis(cfgC, freq_novelty_selected);
        coherence_data(i).novelty = coh_novelty;
    end
end
fprintf('Channel-wise coherence analysis completed\n');

% Save results
outputPath = fullfile(dataFolder, 'channelwise_coherence_output.mat');
save(outputPath, 'coherence_data');
fprintf('Channel-wise coherence analysis results saved to %s\n', outputPath);
end