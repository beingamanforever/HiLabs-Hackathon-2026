"""Generate the judge-spec submission CSV.

Schema (per hackathon spec):
    record_id | final_prediction | confidence | action_taken

Where action_taken ∈ {"R3_ACCEPT", "OVERRIDE", "ROBOCALL"}.

Usage (after running tracks 1-3):
    PYTHONPATH=src python scripts/generate_submission.py
    PYTHONPATH=src python scripts/generate_submission.py --input outputs/inference/inference_t3_ranking.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_submission(ranking: pd.DataFrame) -> pd.DataFrame:
    """Convert a full Track-3 ranking dataframe into the required submission format."""
    def _action(row) -> str:
        if bool(row.get("selected_for_call", False)):
            return "ROBOCALL"
        if row.get("corrected_label") != row.get("R3_Label"):
            return "OVERRIDE"
        return "R3_ACCEPT"

    def _final(row) -> str:
        # Robocall rows are pending — return R3 label (will be replaced by call verdict in production)
        if bool(row.get("selected_for_call", False)):
            return row["R3_Label"]
        return row.get("corrected_label", row["R3_Label"])

    submission = pd.DataFrame({
        "record_id": ranking["Row ID"],
        "final_prediction": ranking.apply(_final, axis=1),
        "confidence": ranking["confidence"].round(4) if "confidence" in ranking.columns else 0.5,
        "action_taken": ranking.apply(_action, axis=1),
    })

    # Diagnostic columns
    submission["r3_original"]   = ranking["R3_Label"]
    submission["org_name"]      = ranking.get("OrganizationName", pd.NA)
    submission["orig_npi"]      = ranking.get("OrigNPI", pd.NA)
    submission["p_r3_wrong"]    = ranking["p_r3_wrong"].round(4) if "p_r3_wrong" in ranking.columns else 0.0
    score = ranking.get("triage_score_lgb", ranking.get("triage_score", 0.0))
    submission["triage_score"]  = pd.to_numeric(score, errors="coerce").round(4)
    return submission


def main() -> None:
    parser = argparse.ArgumentParser(description="Build judge-spec submission CSV")
    parser.add_argument("--input",  default="outputs/track3/track3_full_ranking.csv",
                        help="Track-3 ranking CSV (default: outputs/track3/track3_full_ranking.csv)")
    parser.add_argument("--output", default="outputs/submission/predictions.csv",
                        help="Output submission CSV (default: outputs/submission/predictions.csv)")
    args = parser.parse_args()

    in_path  = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ranking = pd.read_csv(in_path)
    submission = build_submission(ranking)
    submission.to_csv(out_path, index=False)

    print(f"Total rows:       {len(submission)}")
    print(f"Action breakdown:")
    print(submission["action_taken"].value_counts().to_string())
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
