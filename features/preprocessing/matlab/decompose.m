function [target, standard, novelty] =  decompose(data)

    cfg= [];
      

    cfg.trials = (data.trialinfo==200);
    target = ft_selectdata(cfg, data);

    cfg.trials = (data.trialinfo==201);
    standard = ft_selectdata(cfg, data);

    cfg.trials = (data.trialinfo==202);
    novelty = ft_selectdata(cfg, data);

end