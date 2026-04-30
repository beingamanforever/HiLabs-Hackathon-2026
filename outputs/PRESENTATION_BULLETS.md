# Presentation Bullets

- We built a three-track provider-directory accuracy engine that explains disagreement, fixes high-confidence errors passively, and prioritizes the highest-value outbound calls.
- Track 1 shows that R3 agrees with Call QC on only 50.62% of the 2,493-row dataset, which gives a large and measurable opportunity for post-R3 improvement.
- Track 2 raises grouped-CV accuracy from 53.07% to 55.76% after the sprint upgrades, while preserving zero agreement-zone changes.
- The strongest passive rule is now `conformal_org_consensus_flip`, which changed 111 rows at 100% precision on the current evaluation set.
- Org-consensus features replaced the brittle state heuristic with a generalizable signal based on shared ZIP behavior inside the same organization.
- Continuous address staleness beats a hard recency cutoff by distinguishing slightly stale providers from providers that have gone fully silent at the PF location.
- Conformal calibration adds a formal 95% coverage guarantee and yields a `lambda_hat` of 0.735294 with a 393-row uncertain pool.
- The Track 3 selector now uses the full 450-call budget instead of stopping early, which lifts simulated combined accuracy to 61.82%.
- The LightGBM LambdaRank model directly optimizes ranking quality and reached an NDCG@450 of 0.9844 on the validation split.
- The interactive demo and API are both working locally, with the Streamlit app reading the generated outputs and the FastAPI `/triage` endpoint returning live ranked targets.
