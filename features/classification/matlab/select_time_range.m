function select_time_range(classifierName, analysisName, dataDir, selectionsPath)
%SELECT_TIME_RANGE Apply per-analysis time windows to FieldTrip data and save.
%   select_time_range(CLASSIFIER, ANALYSIS, DATADIR, SELECTIONSPATH) loads
%   the FieldTrip output for the given ANALYSIS from DATADIR, applies the
%   latency window stored in SELECTIONSPATH (time_window_selections.json),
%   and saves the trimmed data to DATADIR/<analysis>_timeranged/<analysis>_output.mat.

% Ensure FieldTrip is on the path (match preprocessing setup)
if exist('ft_defaults', 'file') ~= 2
    addpath('C:/FIELDTRIP'); % adjust if your FieldTrip path differs
end
if exist('ft_defaults', 'file') == 2
    ft_defaults;
else
    warning('FieldTrip not found on path; ft_selectdata will fail.');
end

% Defaults for optional arguments
if nargin < 3 || isempty(dataDir)
    dataDir = pwd;
end
if nargin < 4 || isempty(selectionsPath)
    % selections file lives at projectRoot/config/time_window_selections.json
    here = fileparts(mfilename('fullpath'));
    projectRoot = fileparts(fileparts(fileparts(here))); % ../../..
    selectionsPath = fullfile(projectRoot, 'config', 'time_window_selections.json');
end

% Build the selection key and fallback
selectionKey = sprintf('%s::%s', classifierName, analysisName);
defaultWindow = [-0.2, 1.0];

% Map analysis display name to the actual base filename used on disk
basename = normalize_analysis_name(analysisName);

% Load time window selections
timeWindow = defaultWindow;
if exist(selectionsPath, 'file')
    try
        txt = fileread(selectionsPath);
        if ~isempty(txt)
            data = jsondecode(txt);
            if isstruct(data) && isfield(data, matlab.lang.makeValidName(selectionKey))
                % jsondecode turns keys into fields; makeValidName to access
                fn = matlab.lang.makeValidName(selectionKey);
                val = data.(fn);
                if isnumeric(val) && numel(val) == 2
                    timeWindow = val(:)';
                end
            elseif isstruct(data) && isfield(data, selectionKey)
                val = data.(selectionKey);
                if isnumeric(val) && numel(val) == 2
                    timeWindow = val(:)';
                end
            elseif isstruct(data)
                % Keys may include colons; iterate to match raw key
                fns = fieldnames(data);
                for k = 1:numel(fns)
                    if strcmp(strrep(fns{k}, '_', ':'), selectionKey) || strcmp(fns{k}, selectionKey)
                        val = data.(fns{k});
                        if isnumeric(val) && numel(val) == 2
                            timeWindow = val(:)';
                        end
                        break;
                    end
                end
            end
        end
    catch err
        warning('select_time_range:json', 'Failed to read selections (%s): %s', selectionsPath, err.message);
    end
else
    warning('select_time_range:file', 'Selections file not found: %s', selectionsPath);
end

% Locate input mat file using normalized basename (handles e.g., timefreq_output.mat)
inputMat = fullfile(dataDir, sprintf('%s_output.mat', basename));
if ~exist(inputMat, 'file')
    error('Input file not found: %s (expected for analysis "%s")', inputMat, analysisName);
end

% Load whole file (v7 files do not support efficient matfile partial load); keep it simple
S = load(inputMat);
if isempty(fieldnames(S))
    error('No variables found in %s', inputMat);
end

% Grab first variable as the analysis data
vars = fieldnames(S);
varName = vars{1};
dataStruct = S.(varName);

if ~isstruct(dataStruct)
    error('Expected struct data in %s; got %s', inputMat, class(dataStruct));
end

outDir = fullfile(dataDir, sprintf('%s_timeranged', basename));
if ~exist(outDir, 'dir')
    mkdir(outDir);
end
outputMat = fullfile(outDir, sprintf('%s_output.mat', basename));
if exist(outputMat, 'file')
    delete(outputMat);
end

cfg = [];
cfg.latency = timeWindow;
conds = {'target', 'standard', 'novelty'};

numEntries = numel(dataStruct);
resultStruct = dataStruct; % preallocate same shape

for idx = 1:numEntries
    analysisEntry = dataStruct(idx);
    if ~isstruct(analysisEntry)
        error('Expected struct data in %s; got %s', inputMat, class(analysisEntry));
    end
    
    for c = 1:numel(conds)
        condName = conds{c};
        if isfield(analysisEntry, condName)
            try
                analysisEntry.(condName) = ft_selectdata(cfg, analysisEntry.(condName));
            catch err
                warning('select_time_range:ft', 'ft_selectdata failed for %s(%d).%s: %s', analysisName, idx, condName, err.message);
            end
        end
    end
    
    resultStruct(idx) = analysisEntry;
end

% Save with -v7.3 to support future partial loading if needed
payload = struct();
payload.(varName) = resultStruct;  % Preserve original variable name (e.g., timefreq_data)
save(outputMat, '-struct', 'payload', '-v7.3');

fprintf('Saved time-ranged data to %s with window [%.3f %.3f]\n', outputMat, timeWindow(1), timeWindow(2));
end

% -------------------------------------------------------------------------
function basename = normalize_analysis_name(analysisName)
%NORMALIZE_ANALYSIS_NAME Map display names to file basenames used on disk.

if nargin < 1 || isempty(analysisName)
    basename = 'analysis';
    return
end

key = lower(strtrim(analysisName));
switch key
    case {'erp analysis', 'erp'}
        basename = 'erp';
    case {'spectral analysis', 'spectral'}
        basename = 'spectral';
    case {'time-frequency analysis', 'time frequency analysis', 'time-frequency'}
        basename = 'timefreq';
    case {'intertrial coherence analysis', 'inter-trial coherence analysis', 'intertrial analysis', 'inter-trial analysis'}
        basename = 'intertrial_coherence';
    case {'channel-wise connectivity analysis', 'channel wise connectivity analysis', 'channel-wise coherence analysis', 'channel wise coherence analysis'}
        basename = 'channelwise_coherence';
    otherwise
        % Fallback: sanitize to a filesystem-friendly token
        basename = regexprep(key, '\s+', '_');
        basename = regexprep(basename, '[^a-z0-9_]+', '');
        if isempty(basename)
            basename = 'analysis';
        end
end
end

