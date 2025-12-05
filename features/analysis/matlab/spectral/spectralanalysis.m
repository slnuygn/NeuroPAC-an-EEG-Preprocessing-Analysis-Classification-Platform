function spectral_data = spectralanalysis(inputPath)
% Spectral analysis for decomposed cleaned ICA data stored as data_ICApplied_clean_decomposed.mat

if nargin < 1 || isempty(inputPath)
    error('spectralanalysis requires a folder path containing data_ICApplied_clean_decomposed.mat.');
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

% Define configuration for spectral analysis
cfg = [];
cfg.output = 'fourier';
cfg.method = 'mtmfft';
cfg.taper = 'hanning';
cfg.foi = 1:0.5:15;

% Initialize output structure
spectral_data = struct( ...
    'target', cell(1, numTrials), ...
    'standard', cell(1, numTrials), ...
    'novelty', cell(1, numTrials));

fprintf('Starting spectral analysis...\n');
for i = 1:numTrials
    fprintf('Spectral analysis for trial %d/%d\n', i, numTrials);
    
    if isfield(data_decomposed(i), 'target') && ~isempty(data_decomposed(i).target)
        spectr_target = ft_freqanalysis(cfg, data_decomposed(i).target);
        spectral_data(i).target = spectr_target;
    end
    
    if isfield(data_decomposed(i), 'standard') && ~isempty(data_decomposed(i).standard)
        spectr_standard = ft_freqanalysis(cfg, data_decomposed(i).standard);
        spectral_data(i).standard = spectr_standard;
    end
    
    if isfield(data_decomposed(i), 'novelty') && ~isempty(data_decomposed(i).novelty)
        spectr_novelty = ft_freqanalysis(cfg, data_decomposed(i).novelty);
        spectral_data(i).novelty = spectr_novelty;
    end
end
fprintf('Spectral analysis completed\n');

% Save results
outputPath = fullfile(dataFolder, 'spectral_output.mat');
save(outputPath, 'spectral_data');
fprintf('Spectral analysis results saved to %s\n', outputPath);
end
