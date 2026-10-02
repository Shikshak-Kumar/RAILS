# Risk Sentinel ML Layer — what each model predicts

Dataset: `/content/HI-Small_Trans.csv` — 5,078,345 rows, 515,080 accounts,
2022-09-01 00:00:00 → 2022-09-18 16:18:00. Dataset version `e9e8c7e0b47a`.
Split (time-based): train ['2022-09-01 00:00:00', '2022-09-06 13:35:00'], validation ['2022-09-06 13:36:00', '2022-09-08 16:11:00'], test ['2022-09-08 16:12:00', '2022-09-18 16:18:00'].

| Component | Predicts / produces | Method | Trained on labels? |
|---|---|---|---|
| fraud_model | Probability that a transaction is `Is Laundering`=1 (dataset label) | LogReg baseline vs LightGBM, isotonic-calibrated | Yes |
| anomaly_model | `anomaly_score` (0-1 percentile vs train behaviour). NOT a probability | IsolationForest | No |
| account_risk_model | Account RISK SCORE from fan-in/out, pass-through, rapid in→out, volume, volatility + IsolationForest | Heuristic scoring (not supervised) | No |
| liquidity_model | Liquidity STRESS SCORE per account/entity | Deterministic rules, policy weights | No |
| credit_model | Default probability — SYNTHETIC data with ASSUMED default mechanism -> pipeline demonstration ONLY, metrics do NOT reflect real-world performance | LogReg vs GBM | SYNTHETIC only |

Regulatory reporting (AML/Basel/local) is NOT an ML problem here: handled by deterministic rules + RAG in the backend.

Test metrics (fraud_model): PR-AUC=0.103, P@100=0.14, R@500=0.03170189098998888

## Limits (read before use)
* Features use only strictly-earlier transactions; see LEAKAGE REGISTER in `risk_sentinel.py`.
* The transaction ledger contains no borrower/loan data → credit model is NOT trained on it.
* No GNN is implemented. Graph features are degree/pair/reciprocity statistics. `build_transaction_features` is the
  extension point for adding embeddings later.
* Risk levels: fraud = validation-derived thresholds on calibrated probability; account/anomaly = rank-based;
  liquidity = fixed policy thresholds {'medium': 0.35, 'high': 0.55, 'critical': 0.75}.
* Online inference needs recent history of the involved accounts from your DB (`history=` argument).
