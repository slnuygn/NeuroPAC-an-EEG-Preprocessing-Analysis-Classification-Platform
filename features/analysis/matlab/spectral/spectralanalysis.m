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

% Initialize FieldTrip if not already done (reuse preprocessing.m path hint)
if ~exist('ft_defaults', 'file')
    fprintf('FieldTrip not found, attempting to initialize...\n');
    ft_paths = {};
    currentFile = mfilename('fullpath');
    [currentDir, ~, ~] = fileparts(currentFile);
    preprocessingScript = fullfile(currentDir, '..', '..', '..', 'preprocessing', 'matlab', 'preprocessing.m');
    
    if exist(preprocessingScript, 'file')
        fid = fopen(preprocessingScript, 'r');
        if fid ~= -1
            while ~feof(fid)
                tline = fgetl(fid);
                if ischar(tline) && contains(tline, 'addpath') && (contains(tline, 'fieldtrip', 'IgnoreCase', true) || contains(tline, 'FIELDTRIP'))
                    tokens = regexp(tline, 'addpath\([''\"]([^''\"]+)[''\"]\)', 'tokens');
                    if ~isempty(tokens) && ~isempty(tokens{1})
                        extractedPath = tokens{1}{1};
                        fprintf('Found FieldTrip path in preprocessing.m: %s\n', extractedPath);
                        ft_paths{end+1} = extractedPath; %#ok<AGROW>
                    end
                end
            end
            fclose(fid);
        end
    else
        fprintf('Warning: preprocessing.m not found at %s\n', preprocessingScript);
    end
    
    if isempty(ft_paths)
        ft_paths = {
            'C:\Program Files\MATLAB\fieldtrip';
            'C:\fieldtrip';
            'D:\fieldtrip';
            fullfile(userpath, 'fieldtrip')
            };
    end
    
    ft_found = false;
    for i = 1:length(ft_paths)
        ft_path = ft_paths{i};
        if exist(ft_path, 'dir')
            fprintf('Found FieldTrip at: %s\n', ft_path);
            addpath(ft_path);
            try
                ft_defaults;
                fprintf('FieldTrip initialized successfully\n');
                ft_found = true;
                break;
            catch
                fprintf('Failed to initialize FieldTrip from: %s\n', ft_path);
                rmpath(ft_path);
            end
        end
    end
    
    if ~ft_found
        error(['FieldTrip not found. Please install FieldTrip and ensure it is on MATLAB path.\n' ...
            'Common installation locations:\n' ...
            '- C:\\Program Files\\MATLAB\\fieldtrip\n' ...
            '- C:\\fieldtrip\n' ...
            '- Your MATLAB userpath/fieldtrip\n' ...
            'Or add FieldTrip to MATLAB path manually.']);
    end
else
    fprintf('FieldTrip already initialized\n');
end

% Inspect structure and normalize to subjects x conditions
dataSize = size(data_decomposed);
hasTarget = isstruct(data_decomposed) && any(isfield(data_decomposed, 'target'));
hasTargetData = isstruct(data_decomposed) && any(isfield(data_decomposed, 'target_data'));
conditionNames = {'target', 'standard', 'novelty'};

fprintf('\n=== Data Structure Debug ===\n');
fprintf('Class: %s\n', class(data_decomposed));
fprintf('Size: %s\n', mat2str(dataSize));
if isstruct(data_decomposed)
    fprintf('Fields (union): %s\n', strjoin(fieldnames(data_decomposed).', ', '));
end
fprintf('=== End Debug ===\n\n');

if hasTargetData || hasTarget
    numSubjects = numel(data_decomposed);
    subjectData = repmat(struct('target', [], 'standard', [], 'novelty', []), 1, numSubjects);
    for s = 1:numSubjects
        for c = 1:3
            baseName = conditionNames{c};
            if hasTargetData
                fieldName = [baseName '_data'];
            else
                fieldName = baseName;
            end
            if isfield(data_decomposed(s), fieldName)
                subjectData(s).(baseName) = data_decomposed(s).(fieldName);
            end
        end
    end
elseif ismatrix(data_decomposed) && numel(dataSize) == 2 && dataSize(2) == 3
    numSubjects = dataSize(1);
    subjectData = repmat(struct('target', [], 'standard', [], 'novelty', []), 1, numSubjects);
    for s = 1:numSubjects
        for c = 1:3
            subjectData(s).(conditionNames{c}) = data_decomposed(s, c);
        end
    end
else
    error('Unsupported data_decomposed layout. Expect fields target/_data or a subjects x 3 matrix.');
end

fprintf('Number of subjects: %d\n', numSubjects);

% Define configuration for spectral analysis
cfg = [];
cfg.output = 'fourier';
cfg.method = 'mtmfft';
cfg.taper = 'hanning';
cfg.foi = 1:0.5:15;

% Initialize output structures
spectral_data = repmat(struct('target', [], 'standard', [], 'novelty', []), 1, numSubjects);
% Use cells for spectral_records to accommodate FieldTrip outputs with dynamic fields
spectral_records = cell(numSubjects, 3);

fprintf('Starting spectral analysis...\n');
for s = 1:numSubjects
    fprintf('Spectral analysis for subject %d/%d\n', s, numSubjects);
    for c = 1:3
        condName = conditionNames{c};
        condData = subjectData(s).(condName);
        if ~isempty(condData)
            spectr_out = ft_freqanalysis(cfg, condData);
            spectral_data(s).(condName) = spectr_out;
            spectral_records{s, c} = spectr_out;
        end
    end
end
fprintf('Spectral analysis completed\n');

% Save results
outputPath = fullfile(dataFolder, 'spectral_output.mat');
save(outputPath, 'spectral_data', 'spectral_records');
fprintf('Spectral analysis results saved to %s\n', outputPath);
end