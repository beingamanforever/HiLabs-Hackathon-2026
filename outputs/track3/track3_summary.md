# Track 3 Summary

## Budgeted Triage
- Call budget: 450
- Selected rows for robocall: 450
- Official expected usable verdicts: 180
- Mean p_wrong (selected): 83.04%
- Mean p_conclusive_rank (selected): 83.50%
- Mean business gain (selected): 1.64

## Conformal Calibration (Sprint 2)
- lambda_hat: 0.735294
- uncertain_pool_size: 393
- coverage_guarantee: 95%
- calibration_rows: 425

## Simulation
- Expected accuracy gain (records): 151.1
- Expected accuracy gain (points): 6.06%
- Expected combined accuracy (T2+T3): 61.82%
- Oracle correctable rows in selected 450: 377

## Ranker Quality
- NDCG@50: 0.9844
- NDCG@100: 0.9844
- NDCG@450: 0.9844

## Top Call Targets
- [✓] Rank 1 | Row 1988 | HUDSON IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|telehealth|pf_absent_from_claims|mid_score_band
- [✓] Rank 2 | Row 525 | HUDSON IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: telehealth|pf_absent_from_claims|mid_score_band
- [✓] Rank 3 | Row 1333 | UNIVERSITY MEDICAL CENTER OF SOUTHERN NEVADA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 4 | Row 521 | HUDSON IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|pf_absent_from_claims|mid_score_band
- [✓] Rank 5 | Row 1271 | HUDSON IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|pf_absent_from_claims|mid_score_band
- [✓] Rank 6 | Row 1587 | HUDSON IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|pf_absent_from_claims|mid_score_band
- [✓] Rank 7 | Row 1153 | HUDSON IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|pf_absent_from_claims|mid_score_band
- [✓] Rank 8 | Row 1739 | HMFP AT BIDMC | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 9 | Row 747 | MEDISYS HEALTH NETWORK (JAMAICA HOSPITAL & FLUSHING HOSPITAL) | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|telehealth|pf_absent_from_claims|mid_score_band
- [✓] Rank 10 | Row 1387 | LEE MEMORIAL HEALTH SYSTEM | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 11 | Row 1366 | HUDSON IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 12 | Row 1382 | NORTH SHORE LIJ MEDICAL PC GROUP | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 13 | Row 1279 | HMFP AT BIDMC | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 14 | Row 1764 | HMFP AT BIDMC | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 15 | Row 2143 | HEALTHCARE LA IPA | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|telehealth|pf_absent_from_claims|mid_score_band
- [✓] Rank 16 | Row 2474 | OPTUM MEDICAL CARE PC GROUP | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 17 | Row 2409 | OPTUM MEDICAL CARE PC GROUP | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 18 | Row 327 | MOMDOC LLC | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 19 | Row 543 | ASCENSION MEDICAL GROUP SOUTHEAST WI INC | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 20 | Row 482 | MEMORIAL EMERGENCY PHYSICIANS | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 21 | Row 2245 | HPN - LAKESIDE MEDICAL GROUP | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: provider_page_signal|telehealth|pf_absent_from_claims|mid_score_band
- [✓] Rank 22 | Row 1070 | ROSWELL HOSPITAL CORPORATION | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 23 | Row 535 | UNIVERSITY PROFESSIONAL SVCS_1376709535 | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 24 | Row 1079 | GREAT LAKES BAY HEALTH CENTERS PC - 1972621753 | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band
- [✓] Rank 25 | Row 550 | TRINITY PHARMACY PHYS GROUP | score 1.3200 | p_wrong 95.45% | staleness 1.00 | reasons: pf_absent_from_claims|mid_score_band

## Notes
- The 40% conclusive rate is used in simulation only, not as a hard selection quota.
- Sprint 2: isotonic conformal calibration provides 95% coverage guarantee on uncertain pool.
- Sprint 3: LightGBM lambdarank score used when available (triage_score_lgb).
- ✓ = conformal-uncertain row (model recommends a call with coverage guarantee).
- staleness_score: 0=fresh claims at PF ZIP, 1=no recent claims (maximally stale).

- SHAP top-10 features saved to: outputs/track3/shap_importance.csv
