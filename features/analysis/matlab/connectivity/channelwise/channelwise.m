freq_target_channelwise = freqcompute(data, 200);
freq_standard_channelwise = freqcompute(data, 201);
freq_novelty_channelwise = freqcompute(data, 202);

cfg_select = [];
cfg_select.latency = [0 1];
freq_target_channelwise = ft_selectdata(cfg_select, freq_target_channelwise);
freq_standard_channelwise = ft_selectdata(cfg_select, freq_standard_channelwise);
freq_novelty_channelwise = ft_selectdata(cfg_select, freq_novelty_channelwise);
cfgC = [];
cfgC.method = 'coh';

coh_target   = ft_connectivityanalysis(cfgC, freq_target_channelwise);
coh_standard = ft_connectivityanalysis(cfgC, freq_standard_channelwise);
coh_novelty  = ft_connectivityanalysis(cfgC, freq_novelty_channelwise);