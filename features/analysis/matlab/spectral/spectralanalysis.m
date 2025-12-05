% 2. Define the configuration for spectral analysis (inspired by Part II)
cfg = [];
cfg.output = 'fourier'; % We want to compute the power spectrum
cfg.method = 'wavelet'; % Specify 'mtmfft' for spectral analysis (FFT)
cfg.taper = 'hanning'; % Use a Hanning taper (a good single taper, as used in Part II)
cfg.foi = 1:0.5:15; % Frequencies of interest (e.g., 1 to 30 Hz in 1 Hz steps)

% 3. Run the spectral analysis on the task data variables
% This will compute the average power spectrum across all trials
cfg.trials   = (data.trialinfo == S200);
target = ft_selectdata(cfg, data);
spectr_target = ft_freqanalysis(cfg, target);

cfg.trials   = (data.trialinfo == S201);
standard = ft_selectdata(cfg, data);
spectr_standard = ft_freqanalysis(cfg, standard);

cfg.trials   = (data.trialinfo == S202);
novelty = ft_selectdata(cfg, data);
spectr_novelty = ft_freqanalysis(cfg, novelty);
