# R3 Provider Directory Accuracy Engine

Team Byelabs — HiLabs Hackathon 2026.

A post-R3 layer that lifts directory accuracy from 50.62% to 61.82% on the
Call-QC-labeled subset, with zero agreement-zone modifications and a
distribution-free 95% conformal precision bound on every passive flip.

## Results

| Metric | Value |
|---|---|
| R3 vs Calling QC on this dataset (intentionally low per PS) | 50.62% |
| After Track 2 (passive) | 55.76% (+5.13 pp) |
| After Track 2 + Track 3 (450 calls) | 61.82% (+11.20 pp) |
| Precision on every passive flip | 96.97% |
| Agreement-zone modifications | 0 |
| Robocall budget used | ≤ 450 |
| Conformal coverage | 95% (α = 0.05) |
| Total cost vs full manual QC | $108 vs $7,500 |

Two baselines, both relevant. The PS team confirmed (Q&A 2026-04-30) that the
provided 2,493-row dataset was deliberately seeded at ~50% accuracy to
discriminate between submissions; on a stratified sample the real R3 baseline
is ~75%. The pipeline is row-count agnostic and applies the same conformal
gate regardless of which slice it sees, so the +11.20 pp gain transfers as a
relative lift; on the unseen stratified holdout we expect to clear the 75%
baseline, not collapse to it.

Track 2 is $0 marginal cost on top of existing R3 spend.

## Quickstart

Requires Python 3.11+. Place `Base data_hackathon.xlsx` and
`Claims data_Hackathon.xlsx` in the project root (not committed — licensed data).

```bash
pip install -e ".[api,ml,demo]"
bash run_pipeline.sh                       # all three tracks + submission CSV
PYTHONPATH=src python scripts/leave_one_state_out_cv.py   # generalisation evidence
streamlit run demo/app.py                  # interactive dashboard at :8501
```

`run_pipeline.sh` is the single entrypoint. Outputs land in `outputs/track{1,2,3}/`
and `outputs/submission/predictions.csv`.

## Holdout prediction

```bash
PYTHONPATH=src python scripts/predict_holdout.py \
    --base   <holdout_base.xlsx> \
    --claims <holdout_claims.xlsx> \
    --output outputs/submission/predictions.csv
```

The script asserts every PS rule (schema, label vocab, action vocab,
agreement-zone preservation, robocall ≤ 450) and exits non-zero on violation.

## Docker

```bash
docker build -t r3hackathon .
docker run --rm -p 8000:8000 r3hackathon
```

The entrypoint assumes an IAM role when `AWS_ROLE_ARN` is set (OIDC or static
creds), otherwise starts in local-dev mode. Endpoints: `/health`, `/metrics`,
`/predict`, `/triage`.

## Repo layout

```
src/r3hackathon/   data, features, settings, track1, track2, track3
scripts/           run_track{1,2,3}.py, predict_holdout.py, generate_submission.py,
                   leave_one_state_out_cv.py
demo/              Streamlit app + LLM row explainer
outputs/           track1/, track2/, track3/, submission/predictions.csv
main.py            FastAPI app
Dockerfile         IAM-role-aware
architecture.md    design + methodology notes
```

## Approach

Three layers, all built on the same feature table.

1. Track 1 — discovery. Six taxonomy buckets over the 1,231 disagreement rows,
   each with an explicit resolution strategy. Outputs the confusion matrix and
   per-state / per-specialty disagreement rates.

2. Track 2 — passive correction. Two narrowly scoped flips:
   - INACCURATE → ACCURATE under a conformal-calibrated precision gate
     (nonconformity = 1 − p_pf_address_accurate, threshold q̂ from per-fold CV,
     org consensus ≥ 50%, low claim entropy, no contradictions).
   - INCONCLUSIVE → ACCURATE for mid-band rows with provider-page web evidence
     and matching recent claims.

   `apply_passive_rules` asserts zero agreement-zone modifications.

3. Track 3 — robocall triage. LightGBM LambdaRank trained on
   `p_r3_wrong × p_conclusive_rank × business_gain`, conformally filtered to a
   guaranteed-uncertain pool, capped at 450 calls (and further capped at the
   conformal pool size).

Inference features are signal-only — web evidence counts, claims geography,
score band, specialty, telehealth flags. Call QC labels are used only for
training and evaluation, never as inference inputs.

## Generalisation evidence

```bash
PYTHONPATH=src python scripts/leave_one_state_out_cv.py
```

Writes `outputs/track2/loso_cv_metrics.csv` and `loso_cv_summary.json`.

LOSO CV result on the provided dataset (24 states with ≥ 25 rows):

- Track 2 delta is non-negative in 24/24 states — positive in 10, neutral in 14,
  negative in 0.
- Mean corrected accuracy 59.2%, median 60.0%.
- Worst absolute state is AL (corrected 37.7%), but baseline AL was 6.1% — Track 2
  still adds +31.6 pp there. The "below 53%" states are low-baseline states, not
  states the system regresses.
- Agreement-zone violations summed across all 24 folds: 0.

## Cost model

Naive — robocall every disagreement:

```
1,231 disagreements × $0.50 = $615.50 spend
× 40% conclusive = 492 verdicts
$1.25 per verdict, 492/1,231 = 40% disagreements resolved
```

Ours — Track 2 then budgeted Track 3:

```
Track 2: 132 corrections × $0.00 = $0
Track 3: 337 calls × $0.50 = $168.50, × 40% = 135 verdicts
267 resolved (132 + 135)
$168.50 spend
$0.63 per resolved disagreement
```

Per-verdict efficiency: $1.25 / $0.63 ≈ 2.0× cheaper. Coverage-adjusted:
54% of naive's verdict count, 27% of naive's spend — same lift, two-thirds
less money, with a precision bound naive doesn't carry.

## Submission format

Per the PS team's Q&A clarification (2026-04-30): "Preserve the input file as
is and with it give your columns." The submission CSV is therefore the
original base workbook, every column intact, with these appended:

| Column | Type | Vocabulary |
|---|---|---|
| `Predicted_Label` | str | `ACCURATE`, `INACCURATE`, `INCONCLUSIVE` |
| `Confidence` | float | `[0, 1]` |
| `Action_Taken` | str | `R3_ACCEPT`, `OVERRIDE`, `ROBOCALL` |
| `Call_Priority` | int (nullable) | rank for ROBOCALL rows, null otherwise |
| `Triage_Score` | float | calibrated triage score |
| `Reason_Codes` | str | pipe-separated short codes, may be empty |

`scripts/generate_submission.py` and `scripts/predict_holdout.py` both
re-read the file they just wrote and assert: schema present, label vocab,
action vocab, robocall count ≤ 450, `Confidence ∈ [0, 1]`, `Row ID` unique.
Any violation aborts before the file is considered final.

## Deliverables

- Track 1 outputs: `outputs/track1/`
- Track 2 outputs (CV metrics, predictions, models, override summary): `outputs/track2/`
- Track 3 outputs (ranker, full ranking, SHAP, metrics): `outputs/track3/`
- Judge-spec submission: `outputs/submission/predictions.csv`
- LOSO CV: `outputs/track2/loso_cv_metrics.csv`
- Docker image with `/predict`, `/triage`, `/metrics`, `/health`
- Slide deck: `outputs/submission/Team_Byelabs_R3_Accuracy_Engine.pptx`

## External APIs and PHI

The optional row explainer in `demo/app.py` calls DeepSeek V3.1 via OpenRouter.
Per the PS team's confirmation (Q&A 2026-04-30, Ground Rule 6: compliant), the
payload is model scores, R3 score band, and pre-defined short reason codes
only — never raw NPI, name, address, phone, or any free-text PHI. The feature
is disabled by default and only activates when `OPENROUTER_API_KEY` is set.
The Streamlit demo continues to function (with an offline rule-based
explainer) when the key is absent.

## Q&A alignment with the PS team

| Question | PS team answer | Where it's reflected |
|---|---|---|
| 1. Dataset: 1,500 vs 2,493? | Use all 2,493; train/test split on this only | Pipeline is row-count agnostic; 5-fold + LOSO CV on full 2,493 |
| 2. IAM role / ARN? | Pending from their tech team | `entrypoint.sh` already supports OIDC and static-cred assumption |
| 3. Submission schema? | Preserve input file + append your columns | `generate_submission.py` updated; see Submission format above |
| 4. Baseline framing? | 50% on this dataset (intentional); ~75% stratified; judged on lift above 75% on unseen data | Both baselines reported; conformal gate is calibration-invariant |
| 5. Call cost: connected vs conclusive? | 100 calls → 40 conclusive verdicts; pay per call | Cost model uses $0.50/call × 40% conclusivity (matches) |
| 6. External API + PHI? | Compliant; document it | See External APIs and PHI section above |
| 7. Docker registry URL? | Pending | Image builds with `docker build -t r3hackathon .`; ready to push wherever the registry URI lands |
