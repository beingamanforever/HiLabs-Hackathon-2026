# Results Summary

| metric | before | after | delta |
|---|---:|---:|---:|
| baseline_accuracy | 50.62% | 50.62% | 0.00 pts |
| corrected_accuracy | 53.07% | 55.76% | +2.69 pts |
| net_accuracy_gain | +2.45% | +5.13% | +2.68 pts |
| agreement_zone_changes | 0 | 0 | 0 |
| changed_row_precision | 93.85% | 96.97% | +3.12 pts |
| selected_rows | 411 | 450 | +39 |
| expected_accuracy_gain_points | +0.82% | +6.06% | +5.24 pts |
| expected_combined_accuracy | 58.91% | 61.82% | +2.91 pts |
| conformal_lambda_hat | N/A | 0.735294 | new |
| uncertain_pool_size | N/A | 393 | new |
| NDCG@450 | N/A | 0.9844 | new |

## Notes

- Track 2 now preserves the agreement zone completely while improving changed-row precision to 96.97%.
- Track 3 no longer wastes budget on the old hard conclusive cap; it fills the full 450-call budget and improves the simulated combined accuracy to 61.82%.
- NPPES enrichment is implemented but currently skipped because `data/npidata_pfile.csv` is not present.
