function freq_out = freqcompute(data, condCode)
% Performs wavelet-based Fourier decomposition for one condition
% data     = FieldTrip preprocessed data
% condCode = event code in data.trialinfo (e.g., 200, 201, 202)

% ---- Shared wavelet/Fourier parameters ----
cfg = [];
cfg.method  = 'wavelet';
cfg.output  = 'fourier';      % required for ITC & coherence
cfg.foi     = 1:0.5:15;       % frequency range
cfg.toi     = -2:0.01:2;      % time range
cfg.width   = 3;
cfg.pad     = 8;

% ---- Select trials belonging to the requested condition ----
cfg.trials = find(data.trialinfo == condCode);

% ---- Run FT wavelet / Fourier analysis ----
freq_out = ft_freqanalysis(cfg, data);

end
