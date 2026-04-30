# Track 2 Summary

## Evaluation
- Baseline R3 accuracy: 50.62%
- Passive corrected accuracy: 55.76%
- Net accuracy gain: 5.13%
- Agreement-zone preservation: 100.00%
- Agreement-zone changes: 0
- Disagreement-zone recovery rate: 10.40%
- Rows changed by passive engine: 132
- Precision on changed rows: 96.97%

## Override Reasons
- keep_r3: 2253 rows, accuracy 53.48%, average confidence 0.66
- conformal_org_consensus_flip: 111 rows, accuracy 100.00%, average confidence 0.63
- keep_r3_triage_candidate: 108 rows, accuracy 52.78%, average confidence 0.57
- provider_signal_midscore_flip: 21 rows, accuracy 80.95%, average confidence 0.81

## Guardrails
- Flip eligibility is gated by a per-fold conformal threshold (alpha=0.05) on p_pf_address_accurate.
- Org consensus (>= 0.5) and low claim entropy (< 0.9) are required for INACCURATE → ACCURATE flips.
- State-level heuristic removed; conformal guard provides a distribution-free precision guarantee.
- Call QC labels and comments are used only for training labels and evaluation, not inference features.
