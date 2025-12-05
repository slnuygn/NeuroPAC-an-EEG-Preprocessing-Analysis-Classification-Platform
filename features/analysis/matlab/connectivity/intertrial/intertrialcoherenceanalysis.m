freq_target_intertrial = freqcompute(data, 200);
freq_standard_intertrial = freqcompute(data, 201);
freq_novelty_intertrial = freqcompute(data, 202);

itc_target  = compute_itc(freq_target_intertrial);
itc_standard = compute_itc(freq_standard_intertrial);
itc_novelty  = compute_itc(freq_novelty_intertrial);

%region extraction before ml
% single plot tfrla visualize et