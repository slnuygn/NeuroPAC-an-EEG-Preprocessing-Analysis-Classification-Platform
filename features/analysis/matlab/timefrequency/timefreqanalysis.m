cfg         = [];

cfg.output     = 'pow';
cfg.method     = 'wavelet';

cfg.toi        = [-0.1 1];
cfg.foi        = 1 : 0.5 : 15;

cfg.pad = 8;
cfg.width = 3;

cfg.trials   = (data.trialinfo == S200);
target = ft_selectdata(cfg, data);
freq_target = ft_freqanalysis(cfg, target);

cfg.trials   = (data.trialinfo == S201);
standard = ft_selectdata(cfg, data);
freq_standard = ft_freqanalysis(cfg, standard);

cfg.trials   = (data.trialinfo == S202);
novelty = ft_selectdata(cfg, data);
freq_novelty = ft_freqanalysis(cfg, novelty);

% decomposeu preprocessinge koy, erpden çıkar
% baseline correction stage, time freqten sonra yap
cfg= [];
cfg.baselinetype = 'absolute';
cfg.parameter = 'powspctrm';
cfg.baseline = [-1 -0.5]; % for segment size prestim poststim -2 2, for beta and theta