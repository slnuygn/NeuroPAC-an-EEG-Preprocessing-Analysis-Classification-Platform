function [prepped_data] = preprocess_data(data, selected_channels)

cfg= [];
cfg.dataset = data;
cfg.headerfile = ft_read_header(cfg.dataset);
event = ft_read_event(cfg.dataset, 'header', cfg.headerfile);

cfg.trialfun             = 'ft_trialfun_general'; % it will call your function and pass the cfg
cfg.trialdef.eventtype  = 'Stimulus';
cfg.trialdef.eventvalue = {'S200' 'S201' 'S202'}; % read all conditions at once
cfg.trialdef.prestim    = -2.0; % in seconds
cfg.trialdef.poststim   = 1.4; % in seconds

cfg.demean = 'yes';
cfg.baselinewindow = [-0.2 0.0];

cfg.dftfilter = 'yes';
cfg.dftfreq = [50 60];
cfg.channel = selected_channels;
cfg.accepted_channels = {'F4' 'Fz' 'C3' 'Pz' 'P3' 'O1' 'Oz' 'O2' 'P4' 'Cz' 'C4' 'F3'};


prepped_data= ft_preprocessing(cfg);

end

