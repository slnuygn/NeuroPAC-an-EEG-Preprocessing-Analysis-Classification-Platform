function timefreq_data = timefreqanalysis(inputPath)
% Time-frequency analysis for decomposed cleaned ICA data stored as data_ICApplied_clean_decomposed.mat

if nargin < 1 || isempty(inputPath)
    error('timefreqanalysis requires a folder path containing data_ICApplied_clean_decomposed.mat.');
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

% Define configuration for time-frequency analysis
cfg = [];
cfg.output = 'pow';
cfg.method = 'wavelet';
cfg.toi = -2:0.01:2;
cfg.foi = 1:0.5:15;
cfg.pad = 8;
cfg.width = 3;

% Initialize output structure
timefreq_data = struct( ...
    'target', cell(1, numTrials), ...
    'standard', cell(1, numTrials), ...
    'novelty', cell(1, numTrials));

fprintf('Starting time-frequency analysis...\n');
for i = 1:numTrials
    fprintf('Time-frequency analysis for trial %d/%d\n', i, numTrials);
    
    if isfield(data_decomposed(i), 'target') && ~isempty(data_decomposed(i).target)
        freq_target = ft_freqanalysis(cfg, data_decomposed(i).target);
        timefreq_data(i).target = freq_target;
    end
    
    if isfield(data_decomposed(i), 'standard') && ~isempty(data_decomposed(i).standard)
        freq_standard = ft_freqanalysis(cfg, data_decomposed(i).standard);
        timefreq_data(i).standard = freq_standard;
    end
    
    if isfield(data_decomposed(i), 'novelty') && ~isempty(data_decomposed(i).novelty)
        freq_novelty = ft_freqanalysis(cfg, data_decomposed(i).novelty);
        timefreq_data(i).novelty = freq_novelty;
    end
end
fprintf('Time-frequency analysis completed\n');

% Apply baseline correction
fprintf('Applying baseline correction...\n');
cfg_baseline = [];
cfg_baseline.baselinetype = 'absolute';
cfg_baseline.parameter = 'powspctrm';
cfg_baseline.baseline = [-1 -0.5];

for i = 1:numTrials
    if ~isempty(timefreq_data(i).target)
        timefreq_data(i).target = ft_freqbaseline(cfg_baseline, timefreq_data(i).target);
    end
    if ~isempty(timefreq_data(i).standard)
        timefreq_data(i).standard = ft_freqbaseline(cfg_baseline, timefreq_data(i).standard);
    end
    if ~isempty(timefreq_data(i).novelty)
        timefreq_data(i).novelty = ft_freqbaseline(cfg_baseline, timefreq_data(i).novelty);
    end
end
fprintf('Baseline correction completed\n');

% Save results
outputPath = fullfile(dataFolder, 'timefreq_output.mat');
save(outputPath, 'timefreq_data');
fprintf('Time-frequency analysis results saved to %s\n', outputPath);
end