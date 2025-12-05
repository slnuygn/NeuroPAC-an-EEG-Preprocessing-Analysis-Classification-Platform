function itc = compute_itc(freq)
itc              = [];
itc.label        = freq.label;
itc.freq         = freq.freq;
itc.time         = freq.time;
itc.dimord       = 'chan_freq_time';

F = freq.fourierspctrm;   % trials × chan × freq × time
N = size(F,1);            % number of trials

% ------ ITPC ------
itc_itpc = F ./ abs(F);     % normalize to unit vectors
itc_itpc = sum(itc_itpc,1); % sum over trials
itc_itpc = abs(itc_itpc) / N;
itc.itpc = squeeze(itc_itpc); % -> chan × freq × time

% ------ ITLC ------
itc_itlc = sum(F,1) ./ (sqrt(N * sum(abs(F).^2,1)));
itc.itlc = squeeze(abs(itc_itlc));
end
