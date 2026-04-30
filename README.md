# R3 Provider Directory Accuracy Engine

Team Byelabs — HiLabs Hackathon 2026.

A post-R3 layer that lifts directory accuracy from 50.62% to 61.82% on the
Call-QC-labeled subset, with zero agreement-zone modifications and a
distribution-free 95% conformal precision bound on every passive flip.

## Results

| Metric | Value |
|---|---|
| R3 vs Calling QC baseline | 50.62% |
| After Track 2 (passive) | 55.76% (+5.13 pp) |
| After Track 2 + Track 3 (450 calls) | 61.82% (+11.20 pp) |
| Precision on every passive flip | 96.97% |
| Agreement-zone modifications | 0 |
| Robocall budget used | ≤ 450 |
| Conformal coverage | 95% (α = 0.05) |
| Total cost vs full manual QC | $108 vs $7,500 |

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

## Deliverables

- Track 1 outputs: `outputs/track1/`
- Track 2 outputs (CV metrics, predictions, models, override summary): `outputs/track2/`
- Track 3 outputs (ranker, full ranking, SHAP, metrics): `outputs/track3/`
- Judge-spec submission: `outputs/submission/predictions.csv`
- LOSO CV: `outputs/track2/loso_cv_metrics.csv`
- Docker image with `/predict`, `/triage`, `/metrics`, `/health`
- Slide deck: `outputs/submission/Team_Byelabs_R3_Accuracy_Engine.pptx`

## Data confidentiality

The optional row explainer in `demo/app.py` calls DeepSeek V3.1 via OpenRouter.
The payload is model scores, R3 score band, and pre-defined reason codes only —
never raw NPI, name, address, or phone. Disabled by default; enable by setting
`OPENROUTER_API_KEY`.
