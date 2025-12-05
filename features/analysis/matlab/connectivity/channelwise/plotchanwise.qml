chan1 = 'C3';
chan2 = 'C4';

i1 = find(strcmp(coh_target.label, chan1));
i2 = find(strcmp(coh_target.label, chan2));

pair = squeeze(coh_target.cohspctrm(i1,i2,:,:)); % freq x time

tfr_plot = freq_target_fourier;
tfr_plot.powspctrm = reshape(pair,[1 size(pair)]);
tfr_plot.label = {[chan1 '-' chan2]};

cfg = [];
cfg.channel = tfr_plot.label{1};
cfg.xlim = [-0.2 0.8];
cfg.ylim = [1 15];
cfg.zlim = [0 1];

figure; ft_singleplotTFR(cfg, tfr_plot);
title([chan1 '-' chan2 ' coherence (target)']);
