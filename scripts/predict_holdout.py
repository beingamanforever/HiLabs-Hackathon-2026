"""Holdout-prediction entrypoint for judge evaluation.

This is a thin wrapper around `scripts/run_inference.py` that adds the
correctness assertions the PS demands:

  1. Output schema matches the judge spec exactly:
        record_id, final_prediction, confidence, action_taken
  2. Agreement-zone flips == 0 (PS hard guardrail).
  3. Robocall budget <= 450 (PS hard cap).
  4. final_prediction values are restricted to {ACCURATE, INACCURATE, INCONCLUSIVE}.
  5. action_taken values are restricted to {R3_ACCEPT, OVERRIDE, ROBOCALL}.
  6. Prints a net-accuracy summary if Calling_Label is available.

Usage
-----
    PYTHONPATH=src python scripts/predict_holdout.py \\
        --base    data/holdout_base.xlsx \\
        --claims  data/holdout_claims.xlsx \\
        --output  outputs/submission/predictions.csv

Exit codes
----------
    0  — predictions written, all assertions passed.
    1  — assertion failure or unrecoverable error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


# PS team Q&A 2026-04-30: "Preserve the input file as is and with it give your
# columns." So submission = base workbook + the appended columns below.
ALLOWED_LABELS  = {"ACCURATE", "INACCURATE", "INCONCLUSIVE"}
ALLOWED_ACTIONS = {"R3_ACCEPT", "OVERRIDE", "ROBOCALL"}
APPEND_COLUMNS  = ["Predicted_Label", "Confidence", "Action_Taken",
                   "Call_Priority", "Triage_Score", "Reason_Codes"]
HARD_CALL_CAP   = 450


def _run_inference(base: Path, claims: Path, output_dir: Path) -> Path:
    """Re-use the existing inference pipeline; return the ranking CSV path."""
    from scripts.run_inference import main as run_inference_main  # type: ignore

    saved_argv = sys.argv
    sys.argv = [
        "run_inference.py",
        "--base", str(base),
        "--claims", str(claims),
        "--output", str(output_dir),
    ]
    try:
        run_inference_main()
    finally:
        sys.argv = saved_argv

    ranking_csv = output_dir / "inference_t3_ranking.csv"
    if not ranking_csv.exists():
        # Some pipelines write into a track3 sub-folder; fall back gracefully.
        alt = output_dir / "track3" / "inference_t3_ranking.csv"
        if alt.exists():
            return alt
        raise FileNotFoundError(
            f"Inference ranking CSV not found at {ranking_csv}. "
            "Inspect outputs/inference/ for run failures."
        )
    return ranking_csv


def _build_submission(ranking_csv: Path, base_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    from scripts.generate_submission import build_submission, _load_base  # type: ignore

    ranking    = pd.read_csv(ranking_csv)
    base       = _load_base(base_path)
    submission = build_submission(base, ranking)
    return submission, ranking


def _assert_submission(submission: pd.DataFrame, ranking: pd.DataFrame) -> dict:
    """Run every PS-mandated check; raise AssertionError on any violation."""
    n = len(submission)

    # 1. Schema — every appended column present
    missing = [c for c in APPEND_COLUMNS if c not in submission.columns]
    assert not missing, f"Submission is missing required columns: {missing}"

    # 2. Label vocabulary
    bad_labels = set(submission["Predicted_Label"].dropna().unique()) - ALLOWED_LABELS
    assert not bad_labels, (
        f"Predicted_Label contains values outside the allowed vocab: {bad_labels}"
    )

    # 3. Action vocabulary
    bad_actions = set(submission["Action_Taken"].dropna().unique()) - ALLOWED_ACTIONS
    assert not bad_actions, (
        f"Action_Taken contains values outside the allowed vocab: {bad_actions}"
    )

    # 4. Robocall budget cap
    n_robocalls = int((submission["Action_Taken"] == "ROBOCALL").sum())
    assert n_robocalls <= HARD_CALL_CAP, (
        f"Robocall budget violated: {n_robocalls} > {HARD_CALL_CAP} (PS hard cap)."
    )

    # 5. Agreement-zone preservation (only meaningful when Calling_Label is present;
    #    on a true holdout this column is absent, so the assertion is a no-op).
    agreement_flips = 0
    if "Calling_Label" in ranking.columns and "R3_Label" in ranking.columns:
        agreement_zone = (
            ranking["R3_Label"].fillna("__NA__") == ranking["Calling_Label"].fillna("__NA__")
        )
        flipped = (ranking.get("corrected_label", ranking["R3_Label"]) != ranking["R3_Label"])
        agreement_flips = int((agreement_zone & flipped).sum())
        assert agreement_flips == 0, (
            f"Agreement-zone preservation violated: {agreement_flips} rows flipped."
        )

    # 6. Confidence in [0, 1]
    conf = pd.to_numeric(submission["Confidence"], errors="coerce")
    assert conf.between(0.0, 1.0).all() or conf.isna().all(), (
        f"Confidence column out of [0,1] range: min={conf.min()} max={conf.max()}"
    )

    # 7. Row ID non-null and unique (this is the input join key)
    if "Row ID" in submission.columns:
        assert submission["Row ID"].notna().all(), "Row ID has nulls"
        assert submission["Row ID"].is_unique, "Row ID has duplicates"

    return {
        "n_rows": n,
        "n_robocalls": n_robocalls,
        "n_overrides": int((submission["Action_Taken"] == "OVERRIDE").sum()),
        "n_r3_accept": int((submission["Action_Taken"] == "R3_ACCEPT").sum()),
        "agreement_zone_flips": agreement_flips,
        "robocall_budget_ok": n_robocalls <= HARD_CALL_CAP,
    }


def _maybe_net_accuracy(ranking: pd.DataFrame) -> dict | None:
    """If the input had Calling_Label (training/validation), report net accuracy."""
    if "Calling_Label" not in ranking.columns:
        return None
    if ranking["Calling_Label"].isna().all():
        return None

    truth = ranking["Calling_Label"]
    r3 = ranking["R3_Label"]
    final = ranking.get("corrected_label", r3)

    return {
        "n_rows": int(len(ranking)),
        "r3_baseline_accuracy": float((r3 == truth).mean()),
        "after_passive_accuracy": float((final == truth).mean()),
        "net_accuracy_lift": float((final == truth).mean() - (r3 == truth).mean()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Holdout prediction entrypoint")
    parser.add_argument("--base", type=Path, required=True,
                        help="Path to holdout base workbook (.xlsx)")
    parser.add_argument("--claims", type=Path, required=True,
                        help="Path to holdout claims workbook (.xlsx)")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "outputs" / "submission" / "predictions.csv",
                        help="Path to write the submission CSV")
    parser.add_argument("--inference-dir", type=Path,
                        default=ROOT / "outputs" / "inference",
                        help="Working dir for the inference pipeline")
    args = parser.parse_args()

    args.inference_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"[predict_holdout] base    = {args.base}")
    print(f"[predict_holdout] claims  = {args.claims}")
    print(f"[predict_holdout] output  = {args.output}")
    print()

    print("[predict_holdout] running inference pipeline…")
    ranking_csv = _run_inference(args.base, args.claims, args.inference_dir)
    print(f"[predict_holdout] ranking written → {ranking_csv}")

    print("[predict_holdout] building judge-spec submission…")
    submission, ranking = _build_submission(ranking_csv, args.base)

    print("[predict_holdout] running PS assertions…")
    stats = _assert_submission(submission, ranking)
    print(json.dumps(stats, indent=2))

    submission[SUBMISSION_COLUMNS + [c for c in submission.columns if c not in SUBMISSION_COLUMNS]] \
        .to_csv(args.output, index=False)
    print(f"[predict_holdout] submission written → {args.output}")

    net = _maybe_net_accuracy(ranking)
    if net is not None:
        print()
        print("[predict_holdout] Net accuracy summary (input had labels):")
        print(json.dumps(net, indent=2))

    print()
    print("[predict_holdout] OK — all PS assertions passed. Submission ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
