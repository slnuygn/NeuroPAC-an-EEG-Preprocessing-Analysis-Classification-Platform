function ERP_data = timelock_func(inputPath)
% timelock analysis for decomposed cleaned ICA data stored as data_ICApplied_clean_decomposed.mat

if nargin < 1 || isempty(inputPath)
    error('timelock_func requires a folder path containing data_ICApplied_clean_decomposed.mat.');
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

% Load the cleaned data variable saved by browse_ICA
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

% Initialize FieldTrip if not already done
if ~exist('ft_defaults', 'file')
    fprintf('FieldTrip not found, attempting to initialize...\n');
    % Try to find FieldTrip path from preprocessing.m
    ft_paths = {};
    
    % Resolve path to preprocessing.m relative to this script
    currentFile = mfilename('fullpath');
    [currentDir, ~, ~] = fileparts(currentFile);
    % Go up 3 levels: ERP -> matlab -> analysis -> features
    % Then down to preprocessing/matlab/preprocessing.m
    preprocessingScript = fullfile(currentDir, '..', '..', '..', 'preprocessing', 'matlab', 'preprocessing.m');
    
    if exist(preprocessingScript, 'file')
        fid = fopen(preprocessingScript, 'r');
        if fid ~= -1
            while ~feof(fid)
                tline = fgetl(fid);
                if ischar(tline) && contains(tline, 'addpath') && (contains(tline, 'fieldtrip', 'IgnoreCase', true) || contains(tline, 'FIELDTRIP'))
                    % Extract path between quotes
                    tokens = regexp(tline, 'addpath\([''"]([^''"]+)[''"]\)', 'tokens');
                    if ~isempty(tokens) && ~isempty(tokens{1})
                        extractedPath = tokens{1}{1};
                        fprintf('Found FieldTrip path in preprocessing.m: %s\n', extractedPath);
                        ft_paths{end+1} = extractedPath;
                    end
                end
            end
            fclose(fid);
        end
    else
        fprintf('Warning: preprocessing.m not found at %s\n', preprocessingScript);
    end
    
    % Add common fallback locations if not found
    if isempty(ft_paths)
        ft_paths = {
            'C:\Program Files\MATLAB\fieldtrip';  % Default MATLAB installation
            'C:\fieldtrip';  % Alternative location
            'D:\fieldtrip';  % Another possible location
            fullfile(userpath, 'fieldtrip')  % User path
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

% time lock analysis
fprintf('Starting timelock analysis...\n');
ERP_data = struct( ...
    'target', cell(1, numTrials), ...
    'standard', cell(1, numTrials), ...
    'novelty', cell(1, numTrials));

for i = 1:numTrials
    fprintf('Timelock analysis for trial %d/%d\n', i, numTrials);
    cfg = [];
    cfg.latency = [0 1];
    cfg.whatever = [-0.2 0.5];
    cfg.hmm = {'a' 'b' 'c'};
    cfg.lalalala  = 'asadasd';
    cfg.isthistest = 'yes';
    cfg.number = 7;
    
    
    if isfield(data_decomposed(i), 'target') && ~isempty(data_decomposed(i).target)
        ERP_data(i).target = ft_timelockanalysis(cfg, data_decomposed(i).target);
    end
    
    if isfield(data_decomposed(i), 'standard') && ~isempty(data_decomposed(i).standard)
        ERP_data(i).standard = ft_timelockanalysis(cfg, data_decomposed(i).standard);
    end
    
    if isfield(data_decomposed(i), 'novelty') && ~isempty(data_decomposed(i).novelty)
        ERP_data(i).novelty = ft_timelockanalysis(cfg, data_decomposed(i).novelty);
    end
end
fprintf('Timelock analysis completed\n');

outputPath = fullfile(dataFolder, 'erp_output.mat');
save(outputPath, 'ERP_data');
fprintf('ERP analysis results saved to %s\n', outputPath);
end
