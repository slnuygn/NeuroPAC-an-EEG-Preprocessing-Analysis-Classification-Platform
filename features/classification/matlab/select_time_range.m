function select_time_range(classifierName, analysisName, dataDir, selectionsPath)
%SELECT_TIME_RANGE Apply per-analysis time windows to FieldTrip data and save.
%   select_time_range(CLASSIFIER, ANALYSIS, DATADIR, SELECTIONSPATH) loads
%   the FieldTrip output for the given ANALYSIS from DATADIR, applies the
%   latency window stored in SELECTIONSPATH (time_window_selections.json),
%   and saves the trimmed data to DATADIR/<analysis>_timeranged/<analysis>_output.mat.

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

% Locate input mat file
inputMat = fullfile(dataDir, sprintf('%s_output.mat', analysisName));
if ~exist(inputMat, 'file')
    error('Input file not found: %s', inputMat);
end

% Discover variable name without loading everything into memory
varsInfo = whos('-file', inputMat);
if isempty(varsInfo)
    error('No variables found in %s', inputMat);
end
varName = varsInfo(1).name;

% Prepare output folder and matfile for incremental writes
outDir = fullfile(dataDir, sprintf('%s_timeranged', analysisName));
if ~exist(outDir, 'dir')
    mkdir(outDir);
end
outputMat = fullfile(outDir, sprintf('%s_output.mat', analysisName));
if exist(outputMat, 'file')
    delete(outputMat);
end

inMat = matfile(inputMat, 'Writable', false);
outMat = matfile(outputMat, 'Writable', true);

cfg = [];
cfg.latency = timeWindow;
conds = {'target', 'standard', 'novelty'};

% Determine number of entries without loading all data
dataSize = size(inMat, varName);
numEntries = prod(dataSize);

for i = 1:numEntries
    % Pull one element at a time to limit memory
    analysisEntry = inMat.(varName)(i);
    
    if ~isstruct(analysisEntry)
        error('Expected struct data in %s; got %s', inputMat, class(analysisEntry));
    end
    
    for c = 1:numel(conds)
        condName = conds{c};
        if isfield(analysisEntry, condName)
            try
                analysisEntry.(condName) = ft_selectdata(cfg, analysisEntry.(condName));
            catch err
                warning('select_time_range:ft', 'ft_selectdata failed for %s(%d).%s: %s', analysisName, i, condName, err.message);
            end
        end
    end
    
    % Incrementally write the processed entry to output
    outMat.(varName)(i,1) = analysisEntry; %#ok<NASGU>
end

fprintf('Saved time-ranged data to %s with window [%.3f %.3f]\n', outputMat, timeWindow(1), timeWindow(2));
end

