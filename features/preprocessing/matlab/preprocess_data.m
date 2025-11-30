function [prepped_data] = preprocess_data(data, selected_channels)

cfg= [];
cfg.dataset = data;
cfg.headerfile = ft_read_header(cfg.dataset);
event = ft_read_event(cfg.dataset, 'header', cfg.headerfile);

cfg.trialfun             = 'ft_trialfun_general'; % it will call your function and pass the cfg
cfg.trialdef.eventtype  = 'Stimulus';
cfg.trialdef.eventvalue = {'S200' 'S201' 'S202'}; % read all conditions at once
cfg.trialdef.prestim    = -2.0; % in seconds
cfg.trialdef.poststim   = 2.0; % in seconds

cfg.demean = 'yes';
cfg.baselinewindow = [-2 1];

cfg.dftfilter = 'yes';
cfg.dftfreq = [50 60];
cfg.channel = selected_channels;


prepped_data= ft_preprocessing(cfg);

end

