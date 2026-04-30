#!/usr/bin/env bash
# End-to-end pipeline runner.
#
# Runs Track 1 → Track 2 → Track 3 → submission CSV generation.
# Outputs land in outputs/{track1,track2,track3,submission}/.
#
# Usage:
#   ./run_pipeline.sh                       # train on bundled data
#   ./run_pipeline.sh --base PATH --claims PATH --output DIR  # holdout inference

set -euo pipefail

PYTHON="${PYTHON:-python3}"
export PYTHONPATH="${PYTHONPATH:-src}"

if [[ "$#" -eq 0 ]]; then
  echo "[1/4] Track 1 — disagreement discovery …"
  $PYTHON scripts/run_track1.py
  echo "[2/4] Track 2 — passive correction …"
  $PYTHON scripts/run_track2.py
  echo "[3/4] Track 3 — call triage …"
  $PYTHON scripts/run_track3.py
  echo "[4/4] Building submission CSV …"
  $PYTHON scripts/generate_submission.py
  echo
  echo "Done. Submission at outputs/submission/predictions.csv"
else
  echo "Holdout inference mode"
  $PYTHON scripts/run_inference.py "$@"
fi
