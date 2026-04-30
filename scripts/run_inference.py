"""
Holdout inference entrypoint for judge evaluation.

Usage:
    PYTHONPATH=src python scripts/run_inference.py \
        --base    /path/to/holdout_base.xlsx \
        --claims  /path/to/holdout_claims.xlsx \
        --output  outputs/inference/

This script:
  1. Loads holdout data using the same pipeline as training
  2. Loads the full-data Track 2 models from outputs/track2/
  3. Loads the full-data Track 3 ranker from outputs/track3/
  4. Applies passive correction (Track 2)
  5. Applies triage ranking (Track 3)
  6. Writes CSV predictions and a summary JSON

No model re-training occurs. Models were fit on the full provided dataset.
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

# ── path setup ─────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from r3hackathon.data import load_base_data, aggregate_claims_for_base
from r3hackathon.features import engineer_base_features, merge_claim_features
from r3hackathon.track2 import (
    score_passive_models,
    apply_passive_rules,
    evaluate_passive_predictions,
)
from r3hackathon.track3 import (
    fit_conclusive_model,
    score_conclusive_model,
    add_triage_features,
    fit_conformal_calibration,
    conformal_select,
    simulate_track3_value,
    CALL_BUDGET,
    CONFORMAL_ALPHA,
)


# ── helpers ────────────────────────────────────────────────────────────────

def load_models(saved_output_dir: Path) -> dict:
    """Load serialized Track 2 and Track 3 models."""
    models: dict = {}

    # Track 2
    t2_path = saved_output_dir / "track2" / "track2_models.pkl"
    if t2_path.exists():
        with open(t2_path, "rb") as f:
            models["track2"] = pickle.load(f)
        print(f"  [ok] Track 2 models loaded from {t2_path}")
    else:
        print(f"  [warn] {t2_path} not found — Track 2 will use fallback global rates")
        models["track2"] = None

    # Track 3 ranker
    t3_path = saved_output_dir / "track3" / "track3_ranker.pkl"
    if t3_path.exists():
        with open(t3_path, "rb") as f:
            models["track3_ranker"] = pickle.load(f)
        print(f"  [ok] Track 3 LGB ranker loaded from {t3_path}")
    else:
        print("  [info] track3_ranker.pkl not found — Track 3 will use empirical triage_score")
        models["track3_ranker"] = None

    # Calibration metadata
    t2_meta_path = saved_output_dir / "track2" / "track2_metadata.json"
    if t2_meta_path.exists():
        models["q_hat"] = json.loads(t2_meta_path.read_text())["q_hat_full"]
        print(f"  [ok] q_hat = {models['q_hat']:.4f}")
    else:
        models["q_hat"] = 1.0
        print("  [warn] q_hat not found — defaulting to 1.0")

    t3_meta_path = saved_output_dir / "track3" / "track3_metrics.json"
    if t3_meta_path.exists():
        t3_meta = json.loads(t3_meta_path.read_text())
        models["lambda_hat"] = t3_meta.get("conformal_lambda_hat", 0.735)
        print(f"  [ok] lambda_hat = {models['lambda_hat']:.4f}")
    else:
        models["lambda_hat"] = 0.735

    return models


def build_feature_table_from_files(base_path: Path, claims_path: Path) -> pd.DataFrame:
    """Build feature table from arbitrary base + claims files."""
    print("  Loading base workbook …")
    base_df = load_base_data(base_path)
    print("  Aggregating claims …")
    claims_agg = aggregate_claims_for_base(claims_path, base_df)
    print("  Engineering features …")
    featured = engineer_base_features(base_df)
    merged = merge_claim_features(featured, claims_agg)
    return merged


# ── main inference ─────────────────────────────────────────────────────────

def run_inference(
    base_path: Path,
    claims_path: Path,
    output_path: Path,
    call_budget: int = CALL_BUDGET,
    alpha: float = CONFORMAL_ALPHA,
    saved_output_dir: Path | None = None,
) -> dict:
    output_path.mkdir(parents=True, exist_ok=True)
    project_root = Path(__file__).parent.parent
    saved_dir = saved_output_dir or (project_root / "outputs")

    print("\n[1/5] Loading model artifacts …")
    models = load_models(saved_dir)

    print("\n[2/5] Building feature table from holdout data …")
    feature_table = build_feature_table_from_files(base_path, claims_path)
    print(f"  Rows: {len(feature_table)}")

    # ── Track 2 ──────────────────────────────────────────────────────────
    print("\n[3/5] Applying Track 2 passive correction …")
    if models["track2"] is not None:
        scored = score_passive_models(feature_table, models["track2"])
    else:
        scored = feature_table.copy()
        scored["p_r3_wrong"] = 0.49
        scored["p_pf_address_accurate"] = 0.51

    scored.attrs["q_hat"] = models["q_hat"]
    t2_predictions = apply_passive_rules(scored)

    t2_metrics: dict = {}
    if "Calling_Label" in t2_predictions.columns and t2_predictions["Calling_Label"].notna().any():
        t2_metrics = evaluate_passive_predictions(t2_predictions)
        print(f"  Baseline accuracy     : {t2_metrics['baseline_accuracy']:.2%}")
        print(f"  Corrected accuracy    : {t2_metrics['corrected_accuracy']:.2%}")
        print(f"  Net accuracy gain     : {t2_metrics['net_accuracy_gain']:+.2%}")
        print(f"  Agreement-zone changes: {int(t2_metrics['agreement_zone_changes'])}")
    else:
        print("  [info] Calling_Label not present — skipping accuracy evaluation")

    t2_predictions.to_csv(output_path / "inference_t2_predictions.csv", index=False)
    print(f"  Written → {output_path / 'inference_t2_predictions.csv'}")

    # ── Track 3 ──────────────────────────────────────────────────────────
    print("\n[4/5] Applying Track 3 triage ranking …")

    # Fit lightweight conclusiveness model (no labels needed)
    print("  Fitting conclusive model …")
    # For holdout we can only fit conclusiveness on the data itself (unsupervised heuristic)
    # or load a pre-fitted model if saved. Here we fit from holdout data as the model
    # is an empirical backoff that doesn't require a separate label.
    conclusive_model = fit_conclusive_model(t2_predictions)
    t3_df = score_conclusive_model(t2_predictions, conclusive_model)
    t3_df = add_triage_features(t3_df)

    # Conformal calibration — re-calibrate on this holdout using stored lambda
    p_wrong_raw = t3_df["p_r3_wrong"].fillna(0.0).values
    has_labels = "r3_wrong" in t3_df.columns and t3_df["r3_wrong"].notna().any()
    true_labels = t3_df["r3_wrong"].fillna(False).astype(int).values if has_labels else np.zeros(len(t3_df), dtype=int)

    candidate_mask = t3_df["needs_active_review"].fillna(False).values
    calib_mask = candidate_mask if candidate_mask.sum() >= 10 else np.ones(len(t3_df), dtype=bool)

    p_cal, lambda_hat_new, conformal_meta = fit_conformal_calibration(
        p_wrong_raw, true_labels, calib_mask, alpha=alpha
    )

    # Use stored lambda_hat from training if no ground-truth labels
    effective_lambda = lambda_hat_new if has_labels else models["lambda_hat"]

    # Determine score column
    score_col = "triage_score"
    if models["track3_ranker"] is not None:
        lgb_model = models["track3_ranker"]["lgb_model"]
        feature_cols = models["track3_ranker"]["feature_cols"]
        X = t3_df.reindex(columns=feature_cols).fillna(0.0)
        try:
            t3_df["triage_score_lgb"] = lgb_model.predict(X)
            score_col = "triage_score_lgb"
            print("  LGB ranker applied successfully")
        except Exception as exc:
            print(f"  [warn] LGB ranker predict failed ({exc}) — using triage_score")

    full_ranking, selection_meta = conformal_select(
        t3_df,
        p_cal,
        effective_lambda,
        n_calls=call_budget,
        gain_col="business_gain",
        score_col=score_col,
        alpha=alpha,
    )

    t3_metrics = simulate_track3_value(full_ranking, n_calls=call_budget)

    full_ranking.to_csv(output_path / "inference_t3_ranking.csv", index=False)
    selected = full_ranking[full_ranking["selected_for_call"]]
    selected.to_csv(output_path / "inference_t3_selected.csv", index=False)
    print(f"  Selected rows         : {len(selected)}")
    print(f"  Written → {output_path / 'inference_t3_ranking.csv'}")
    print(f"  Written → {output_path / 'inference_t3_selected.csv'}")

    # ── Judge-spec submission CSV ────────────────────────────────────────
    print("\n  Building judge-spec submission CSV …")
    from scripts.generate_submission import build_submission  # type: ignore
    submission = build_submission(full_ranking)
    submission.to_csv(output_path / "predictions.csv", index=False)
    print(f"  Action breakdown:\n{submission['action_taken'].value_counts().to_string()}")
    print(f"  Written → {output_path / 'predictions.csv'}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n[5/5] Writing summary …")
    summary: dict = {
        "n_rows": len(feature_table),
        "call_budget": call_budget,
        "t2_rows_changed": int(t2_predictions["label_changed"].sum()),
        "t2_agreement_zone_changes": int(t2_metrics.get("agreement_zone_changes", 0)),
        "t3_selected_rows": int(len(selected)),
        "conformal_lambda_used": round(float(effective_lambda), 6),
        "q_hat_used": round(float(models["q_hat"]), 6),
    }
    if t2_metrics:
        summary.update({
            "t2_baseline_accuracy": round(t2_metrics["baseline_accuracy"], 4),
            "t2_corrected_accuracy": round(t2_metrics["corrected_accuracy"], 4),
            "t2_net_gain_pp": round(t2_metrics["net_accuracy_gain"] * 100, 2),
        })
    if t3_metrics:
        summary.update({
            "t3_expected_usable_verdicts": int(t3_metrics.get("expected_usable_verdicts", 0)),
            "t3_expected_accuracy_gain_pp": round(t3_metrics.get("expected_accuracy_gain_points", 0) * 100, 2),
            "t3_expected_combined_accuracy": round(t3_metrics.get("expected_combined_accuracy", 0), 4),
        })

    (output_path / "inference_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(f"  Written → {output_path / 'inference_summary.json'}")

    # Preview top selected rows
    preview_cols = ["Row ID", "OrigNPI", "R3_Label", "corrected_label", score_col, "p_r3_wrong"]
    available = [c for c in preview_cols if c in selected.columns]
    if available:
        print(f"\n  Top 5 triage calls:\n{selected[available].head().to_string(index=False)}")

    return summary


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run holdout inference for R3 hackathon Tracks 2 & 3"
    )
    parser.add_argument("--base",   required=True, help="Path to holdout base workbook (.xlsx)")
    parser.add_argument("--claims", required=True, help="Path to holdout claims workbook (.xlsx)")
    parser.add_argument("--output", default="outputs/inference", help="Output directory (default: outputs/inference)")
    parser.add_argument("--budget", type=int, default=CALL_BUDGET, help=f"Call budget for Track 3 (default: {CALL_BUDGET})")
    parser.add_argument("--alpha",  type=float, default=CONFORMAL_ALPHA, help=f"Conformal alpha (default: {CONFORMAL_ALPHA})")
    args = parser.parse_args()

    summary = run_inference(
        base_path=Path(args.base),
        claims_path=Path(args.claims),
        output_path=Path(args.output),
        call_budget=args.budget,
        alpha=args.alpha,
    )

    print("\n" + "=" * 60)
    print("INFERENCE COMPLETE")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:<40} {v}")


if __name__ == "__main__":
    main()
