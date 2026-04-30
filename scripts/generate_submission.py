"""Generate the judge-spec submission file.

Format (clarified by the PS team in Q&A on 2026-04-30):
    "Preserve the input file as is and with it give your columns."

So the submission is the original base workbook, every column intact, with
these appended columns:

    Predicted_Label   ACCURATE | INACCURATE | INCONCLUSIVE
    Confidence        float in [0, 1]
    Action_Taken      R3_ACCEPT | OVERRIDE | ROBOCALL
    Call_Priority     int rank for ROBOCALL rows (1 = call first), blank otherwise
    Triage_Score      float, calibrated triage score
    Reason_Codes      pipe-separated reason codes (or empty)

Robocall budget cap (450) is asserted before the file is written.

Usage:
    PYTHONPATH=src python scripts/generate_submission.py
    PYTHONPATH=src python scripts/generate_submission.py \\
        --base outputs/inference/inference_base.xlsx \\
        --ranking outputs/inference/inference_t3_ranking.csv \\
        --output outputs/submission/predictions.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

LABEL_VOCAB   = {"ACCURATE", "INACCURATE", "INCONCLUSIVE"}
ACTION_VOCAB  = {"R3_ACCEPT", "OVERRIDE", "ROBOCALL"}
APPEND_COLS   = ["Predicted_Label", "Confidence", "Action_Taken",
                 "Call_Priority", "Triage_Score", "Reason_Codes"]
ROBOCALL_CAP  = 450


def _load_base(path: Path) -> pd.DataFrame:
    """Load the base workbook with the same header offset as data.load_base_data."""
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=1)
    return pd.read_csv(path)


def _action(row) -> str:
    if bool(row.get("selected_for_call", False)):
        return "ROBOCALL"
    if row.get("corrected_label") != row.get("R3_Label"):
        return "OVERRIDE"
    return "R3_ACCEPT"


def _final(row) -> str:
    if bool(row.get("selected_for_call", False)):
        return row["R3_Label"]
    return row.get("corrected_label", row["R3_Label"])


def build_submission(base: pd.DataFrame, ranking: pd.DataFrame) -> pd.DataFrame:
    if "Row ID" not in ranking.columns or "Row ID" not in base.columns:
        raise ValueError("Both base and ranking must carry 'Row ID' for the join.")

    score_col = "triage_score_lgb" if "triage_score_lgb" in ranking.columns else "triage_score"
    rk = ranking.copy()
    rk["Predicted_Label"] = rk.apply(_final, axis=1)
    rk["Action_Taken"]    = rk.apply(_action, axis=1)
    rk["Confidence"]      = pd.to_numeric(rk.get("confidence", 0.5), errors="coerce").round(4)
    rk["Triage_Score"]    = pd.to_numeric(rk.get(score_col, 0.0), errors="coerce").round(4)
    rk["Reason_Codes"]    = rk.get("triage_reason_codes", "").fillna("")

    if "call_rank" in rk.columns:
        rk["Call_Priority"] = pd.to_numeric(rk["call_rank"], errors="coerce").astype("Int64")
    else:
        rk["Call_Priority"] = pd.Series([pd.NA] * len(rk), dtype="Int64")

    keep = ["Row ID"] + APPEND_COLS
    out  = base.merge(rk[keep], on="Row ID", how="left")

    out["Predicted_Label"] = out["Predicted_Label"].fillna(out.get("R3_Label", "INCONCLUSIVE"))
    out["Action_Taken"]    = out["Action_Taken"].fillna("R3_ACCEPT")
    out["Confidence"]      = out["Confidence"].fillna(0.0)
    out["Triage_Score"]    = out["Triage_Score"].fillna(0.0)
    out["Reason_Codes"]    = out["Reason_Codes"].fillna("")
    return out


def validate(df: pd.DataFrame) -> None:
    missing = [c for c in APPEND_COLS if c not in df.columns]
    assert not missing, f"submission missing required columns: {missing}"

    bad_labels = set(df["Predicted_Label"].dropna().unique()) - LABEL_VOCAB
    assert not bad_labels, f"unexpected Predicted_Label values: {bad_labels}"

    bad_actions = set(df["Action_Taken"].dropna().unique()) - ACTION_VOCAB
    assert not bad_actions, f"unexpected Action_Taken values: {bad_actions}"

    n_calls = int((df["Action_Taken"] == "ROBOCALL").sum())
    assert n_calls <= ROBOCALL_CAP, f"robocall budget exceeded: {n_calls} > {ROBOCALL_CAP}"

    conf = pd.to_numeric(df["Confidence"], errors="coerce")
    assert conf.between(0.0, 1.0).all(), "Confidence values must be in [0, 1]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build judge-spec submission")
    parser.add_argument("--base",    default="Base data_hackathon.xlsx",
                        help="Original base workbook (preserved as-is in the output)")
    parser.add_argument("--ranking", default="outputs/track3/track3_full_ranking.csv",
                        help="Track-3 ranking CSV")
    parser.add_argument("--output",  default="outputs/submission/predictions.csv",
                        help="Output submission CSV")
    args = parser.parse_args()

    base    = _load_base(Path(args.base))
    ranking = pd.read_csv(args.ranking)

    submission = build_submission(base, ranking)
    validate(submission)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(out_path, index=False)

    n_calls = int((submission["Action_Taken"] == "ROBOCALL").sum())
    print(f"Rows:             {len(submission)} (input preserved)")
    print(f"Appended columns: {', '.join(APPEND_COLS)}")
    print(f"Action breakdown:")
    print(submission["Action_Taken"].value_counts().to_string())
    print(f"Validation:       labels OK · actions OK · "
          f"robocalls {n_calls} ≤ {ROBOCALL_CAP} · Confidence in [0,1]")
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
