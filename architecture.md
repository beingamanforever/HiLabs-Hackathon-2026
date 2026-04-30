# Architecture

## Components

| Stage | Module | Responsibility |
|---|---|---|
| Ingest | `src/r3hackathon/data.py` | Load base workbook (header row 1) and stream the claims workbook in read-only `openpyxl` mode. Aggregate claims to provider level. Row-count agnostic — honours `eval_set_flag` if present. |
| Features | `src/r3hackathon/features.py` | Normalise R3 / Web / Call labels. Score-band binning. URL evidence counts. Org consensus + source-tier features. Claims-derived ZIP / state match flags, multi-location entropy, recency (90 / 180 / 365 d), staleness. |
| Track 1 | `src/r3hackathon/track1.py` | Disagreement taxonomy (6 buckets) + confusion matrix + per-state / per-specialty / per-org / per-keyword summaries. |
| Track 2 | `src/r3hackathon/track2.py` | Two empirical backoff models (`p_r3_wrong`, `p_pf_accurate`). Conformal threshold `q̂` calibrated per CV fold. Two narrowly scoped passive flips. Hard `assert` on agreement-zone preservation. |
| Track 3 | `src/r3hackathon/track3.py` | LightGBM LambdaRank over the active-review pool. Conformal filter, business-gain weighting, budget cap. |
| Submission | `scripts/generate_submission.py` | Writes the judge-spec CSV. Per PS Q&A (2026-04-30) the format is the original base workbook preserved as-is, with `Predicted_Label`, `Confidence`, `Action_Taken`, `Call_Priority`, `Triage_Score`, `Reason_Codes` appended. Asserts schema, label / action vocab, robocall ≤ 450, and `Confidence ∈ [0, 1]` after writing. |
| API | `main.py` | FastAPI: `/health`, `/metrics`, `/metrics/all`, `/predict`, `/triage`. |
| Docker | `Dockerfile`, `entrypoint.sh` | Assumes IAM role when `AWS_ROLE_ARN` is set (OIDC or static creds), falls back to local-dev mode. |

## Data flow

1. `data.load_base_data` reads the base workbook into a DataFrame.
2. `data.aggregate_claims_for_base` streams the claims workbook and groups by NPI.
3. `features.engineer_base_features` produces the per-provider feature row.
4. `features.merge_claim_features` joins claims-derived signals.
5. The resulting feature table feeds Track 1 (analysis only), Track 2 (passive
   layer), and Track 3 (active triage).
6. `generate_submission.py` consumes Track 2 + Track 3 outputs and writes
   `outputs/submission/predictions.csv`.

The feature table is the single shared artifact. Tracks do not share state
through pickled intermediate caches; each track re-derives what it needs from
the feature table or from the prior track's CSV outputs.

## Track 2 passive layer

Two flips, both conditional on a conformal precision gate.

- `conformal_org_consensus_flip` — INACCURATE → ACCURATE.
  Fires only when:
  1. Nonconformity score `1 − p_pf_address_accurate` ≤ `q̂` (per-fold CV
     quantile at coverage `1 − α`, α = 0.05).
  2. Org consensus on the plan-file ZIP ≥ 50%.
  3. Claim ZIP entropy below the low-entropy band.
  4. No contradicting recent claims.

- `provider_signal_midscore_flip` — INCONCLUSIVE → ACCURATE.
  Fires only when:
  1. R3 score in the mid band (40–65).
  2. Provider-page web evidence present.
  3. Recent claim ZIP matches plan-file ZIP.
  4. Telehealth flag absent.

`apply_passive_rules` reads the agreement-zone flag (R3 INACCURATE ∧
Call QC INACCURATE) and asserts zero changes inside that subset before returning.

## Track 3 ranker

- Inputs: `p_r3_wrong`, `p_conclusive_rank`, `business_gain`, plus the live
  feature table.
- Loss: LambdaRank with NDCG@450 as the eval objective.
- Filter: rows must be in the conformally-uncertain pool (`p_wrong_cal > λ̂`).
- Output: top-N selection where N = min(450, |uncertain pool|).

## Two baselines

The PS team confirmed (Q&A 2026-04-30) that the provided 2,493-row dataset was
deliberately seeded at ~50% R3-vs-Calling-QC accuracy to discriminate between
submissions. The stratified-population R3 baseline is ~75%, and the unseen
holdout will sample from that population. The system reports lift against
both:

- 50.62% → 61.82% on this dataset (+11.20 pp).
- The Track 2 conformal gate is dataset-agnostic; `q̂` is recalibrated per
  fold from nonconformity scores, so the precision bound transfers regardless
  of which baseline the holdout starts from.

## Generalisation safeguards

- All inference features are signal-based. No Call QC label leakage.
- 5-fold CV recomputes `q̂` per fold; the precision bound is held-out evidence.
- LOSO CV: holding out each state individually (24 states with ≥ 25 rows),
  Track 2 delta is non-negative in 24/24 — positive in 10, neutral in 14,
  negative in 0. Mean corrected accuracy 59.2%, median 60.0%. Worst absolute
  state (AL, corrected 37.7%) still gets +31.6 pp over its 6.1% baseline.
- Agreement-zone violations across all 24 LOSO folds: 0. The guardrail holds
  by construction.

## Cost model

Per-row prices: R3 $0.035, robocall $0.50 (40% conclusive), manual QC $5.00.

Naive baseline — robocall every disagreement:

```
1,231 disagreements × $0.50 = $615.50
× 40% = 492 verdicts
$1.25 per verdict, 492 / 1,231 = 40% of disagreements resolved
```

Ours — Track 2 then budgeted Track 3:

```
Track 2: 132 corrections × $0 = $0
Track 3: 337 calls × $0.50 = $168.50, × 40% = 135 verdicts
267 resolved, $168.50 spend, $0.63 per resolved disagreement
```

Per-verdict efficiency: $1.25 / $0.63 ≈ 2.0×. Coverage-adjusted: 54% of naive's
verdicts at 27% of naive's spend, with a 95% conformal precision bound on every
flip that naive does not carry. Versus full manual QC ($7,500 for 1,231 rows),
the system is 98.6% cheaper.
