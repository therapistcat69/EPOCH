# Model selection

> All numbers below are measured on the **synthetic development dataset** (`synthetic_v1`). They compare models on a generated world and are not evidence of real-world YouTube retention accuracy.

**Selected primary model:** `xgb_delta` with features `hand+emb` (segment size 15 s, embeddings `all-MiniLM-L6-v2`).

## Rule (validation data only)

1. Candidates: trained models at the default segmentation/embedding (naive baselines excluded).
2. Similar-performance set: validation MAE within max(0.5 pts, 5 %) = **0.50** of the best (3.87).
3. Within that set: higher validation **position-adjusted** top-3 risk hit (absolute top-k is dominated by the steep early-video decline, which position alone already finds), then lower inference cost, then simpler/more interpretable family (tree < MLP < BiLSTM < Transformer).
4. A deep model that beats the other families by more than the tolerance is selected outright.

## Why this model

The best tree model (xgb_delta, val MAE 3.87) and the best sequence model (transformer_emb_mt_multitask, val MAE 4.18) differ by +0.31 MAE points (tolerance 0.50). The sequence models did **not** improve meaningfully over the simpler model, so the simpler/cheaper model was kept.

## Candidates (validation | test)

| Model | Features | Val MAE | Test MAE | Test RMSE | Test R² | Pearson | Curve-shape corr | Excess-risk top-3 (chance) | Excess-risk lift | Params | s / video |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xgb_delta | hand | 3.87 | 4.55 | 5.79 | 0.804 | 0.899 | 0.993 | 0.91 (0.27) | 6.43 | - | 0.000 |
| xgb_delta **(selected)** | hand+emb | 4.03 | 4.82 | 5.99 | 0.790 | 0.890 | 0.993 | 0.94 (0.27) | 6.20 | - | 0.001 |
| transformer_emb_mt_multitask | hand+emb | 4.18 | 5.72 | 7.16 | 0.701 | 0.851 | 0.984 | 0.88 (0.27) | 5.55 | 322818 | 0.001 |
| transformer_emb | hand+emb | 4.27 | 5.22 | 6.57 | 0.748 | 0.867 | 0.984 | 0.75 (0.27) | 4.35 | 1169665 | 0.002 |
| transformer_emb_loss_huber | hand+emb | 4.35 | 5.71 | 7.09 | 0.706 | 0.850 | 0.983 | 0.68 (0.27) | 2.48 | 322689 | 0.001 |
| transformer_emb_loss_mae+curve | hand+emb | 4.37 | 5.64 | 7.08 | 0.707 | 0.850 | 0.987 | 0.81 (0.27) | 4.73 | 322689 | 0.001 |
| xgb | hand+tfidf | 4.37 | 5.59 | 6.93 | 0.719 | 0.854 | 0.986 | 0.79 (0.27) | 5.52 | - | 0.012 |
| xgb | hand+tfidf | 4.37 | 5.59 | 6.93 | 0.719 | 0.854 | 0.986 | 0.79 (0.27) | 5.52 | - | 0.013 |
| transformer_emb_single | hand+emb | 4.41 | 5.58 | 6.89 | 0.723 | 0.853 | 0.979 | 0.71 (0.27) | 2.93 | 322689 | 0.004 |
| transformer_emb_loss_mae | hand+emb | 4.41 | 5.58 | 6.89 | 0.723 | 0.853 | 0.979 | 0.71 (0.27) | 2.93 | 322689 | 0.001 |
| transformer_emb | hand+emb | 4.41 | 5.58 | 6.89 | 0.723 | 0.853 | 0.979 | 0.71 (0.27) | 2.93 | 322689 | 0.001 |
| transformer_emb | hand+emb | 4.41 | 5.58 | 6.89 | 0.723 | 0.853 | 0.979 | 0.71 (0.27) | 2.93 | 322689 | 0.001 |
| transformer_emb_loss_mse | hand+emb | 4.48 | 5.90 | 7.38 | 0.682 | 0.839 | 0.980 | 0.60 (0.27) | 3.69 | 322689 | 0.001 |
| rf | hand+tfidf | 4.49 | 5.73 | 7.02 | 0.712 | 0.847 | 0.981 | 0.81 (0.27) | 3.13 | - | 0.016 |
| rf | hand+tfidf | 4.49 | 5.73 | 7.02 | 0.712 | 0.847 | 0.981 | 0.81 (0.27) | 3.13 | - | 0.017 |
| xgb | hand | 4.56 | 5.66 | 6.99 | 0.715 | 0.851 | 0.987 | 0.84 (0.27) | 4.38 | - | 0.000 |
| xgb | hand+emb | 4.57 | 5.68 | 6.97 | 0.716 | 0.851 | 0.987 | 0.81 (0.27) | 4.93 | - | 0.001 |
| xgb | hand+emb | 4.57 | 5.68 | 6.97 | 0.716 | 0.851 | 0.987 | 0.81 (0.27) | 4.93 | - | 0.001 |
| xgb | hand+emb | 4.57 | 5.68 | 6.97 | 0.716 | 0.851 | 0.987 | 0.81 (0.27) | 4.93 | - | 0.000 |
| xgb | hand+emb | 4.57 | 5.68 | 6.97 | 0.716 | 0.851 | 0.987 | 0.81 (0.27) | 4.93 | - | 0.000 |
| xgb | hand+emb | 4.57 | 5.68 | 6.97 | 0.716 | 0.851 | 0.987 | 0.81 (0.27) | 4.93 | - | 0.000 |
| xgb | hand+emb+ctx | 4.58 | 5.69 | 6.97 | 0.716 | 0.851 | 0.987 | 0.84 (0.27) | 4.59 | - | 0.001 |
| bilstm_emb_mt_multitask | hand+emb | 4.58 | 5.89 | 7.37 | 0.683 | 0.839 | 0.982 | 0.91 (0.27) | 6.03 | 717570 | 0.002 |
| rf | hand+emb | 4.62 | 5.77 | 7.06 | 0.709 | 0.846 | 0.979 | 0.81 (0.27) | 2.67 | - | 0.003 |
| bilstm_emb | hand+emb | 4.64 | 5.80 | 7.14 | 0.702 | 0.842 | 0.980 | 0.74 (0.27) | 3.54 | 717313 | 0.004 |

## Caveat

Because the data are synthetic, differences between models may reflect how easily each family inverts the generator rather than real predictive ability. Selection must be repeated on real creator-authorised retention data before any real-world claim (see README, 'Real data strategy').
