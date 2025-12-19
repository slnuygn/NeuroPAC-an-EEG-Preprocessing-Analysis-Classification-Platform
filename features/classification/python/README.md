## Recommended Models for Different Analysis Types

| Analysis Type     | Recommended Models | Why?                                                               |
| :---------------- | :----------------- | :----------------------------------------------------------------- |
| ERP (Time-domain) | CNN, LSTM, RNN     | Captures the temporal morphology and peaks.                        |
| Spectral (Power)  | SVM, KNN, DBN      | Usually lower dimension; works well with simple feature vectors.   |
| Time-Frequency    | CNN (2D/3D)        | Treats the spectrogram like an image to find patterns.             |
| Connectivity      | SVM, CNN           | Connectivity matrices (Graph-like) work well as structured inputs. |
| Inter-trial Phase | CNN, DBN           | Phase information is highly non-linear and spatial.                |
