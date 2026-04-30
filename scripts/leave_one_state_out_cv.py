"""Leave-One-State-Out (LOSO) cross-validation for Track 2 passive rules.

Why this exists
---------------
The PS warns: "Solutions that overfit to the 1,500 records will not transfer."
The earliest version of Track 2 used a state-based heuristic (AL/MI/NJ) that
made any state-distribution shift a generalization risk. We replaced it with
the conformal org-consensus gate, but a judge can still ask: "How do we know
this transfers?"

LOSO CV simulates exactly that scenario: hold out one state at a time, fit the
passive model on the rest, calibrate conformal q_hat on the rest, then apply
the rules to the held-out state and measure accuracy. If any state's accuracy
collapses, that state is a leakage point.

Usage
-----
    PYTHONPATH=src python3 scripts/leave_one_state_out_cv.py

Outputs
-------
    outputs/track2/loso_cv_metrics.csv  — per-state baseline / corrected / delta
    outputs/track2/loso_cv_summary.json — aggregate min / mean / worst-state
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from r3hackathon.features import build_feature_table  # noqa: E402
from r3hackathon.track2 import (  # noqa: E402
    apply_passive_rules,
    calibrate_conformal_threshold,
    fit_passive_models,
    score_passive_models,
)

# Accuracy floor below which we flag the fold as a generalization risk.
ACCURACY_FLOOR = 0.53
MIN_FOLD_ROWS = 25  # smaller states are too noisy to evaluate alone


def _safe_acc(pred: pd.Series, truth: pd.Series) -> float:
    if len(pred) == 0:
        return float("nan")
    return float((pred == truth).mean())


def loso_cv(df: pd.DataFrame) -> pd.DataFrame:
    """Run leave-one-state-out CV; return per-state metrics."""
    states = (
        df["State"]
        .dropna()
        .astype(str)
        .value_counts()
        .loc[lambda s: s >= MIN_FOLD_ROWS]
        .index.tolist()
    )
    print(f"[LOSO] evaluating {len(states)} states (≥{MIN_FOLD_ROWS} rows each)")

    rows = []
    for state in states:
        test_mask = df["State"].astype(str) == state
        train = df[~test_mask].copy()
        test = df[test_mask].copy()

        # Train empirical backoff models on every other state, then calibrate
        # the conformal threshold on the same training fold.
        models = fit_passive_models(train)
        train_scored = score_passive_models(train, models)
        q_hat = calibrate_conformal_threshold(train_scored, alpha=0.05)

        # Score and rule-apply on the held-out state only.
        test_scored = score_passive_models(test, models)
        test_scored.attrs["q_hat"] = q_hat
        test_pred = apply_passive_rules(test_scored)

        baseline = _safe_acc(test_pred["R3_Label"], test_pred["Calling_Label"])
        corrected = _safe_acc(test_pred["corrected_label"], test_pred["Calling_Label"])
        flips = int(test_pred["label_changed"].sum())
        agreement_flips = int(
            (test_pred["agreement_zone"] & test_pred["label_changed"]).sum()
        )

        rows.append(
            {
                "state": state,
                "test_rows": int(len(test_pred)),
                "baseline_accuracy": baseline,
                "corrected_accuracy": corrected,
                "delta": corrected - baseline,
                "flips": flips,
                "agreement_zone_violations": agreement_flips,
                "q_hat": q_hat,
                "below_floor": bool(corrected < ACCURACY_FLOOR),
            }
        )
        print(
            f"  [{state}] n={len(test_pred):4d}  base={baseline:.3f}  "
            f"corr={corrected:.3f}  Δ={corrected-baseline:+.3f}  flips={flips:3d}"
            + ("  *** BELOW FLOOR ***" if corrected < ACCURACY_FLOOR else "")
        )

    return pd.DataFrame(rows).sort_values("corrected_accuracy")


def main() -> None:
    print("[LOSO] building feature table…")
    df = build_feature_table()
    print(f"[LOSO] feature table: {len(df):,} rows · {df['State'].nunique()} unique states")

    metrics = loso_cv(df)

    out_dir = ROOT / "outputs" / "track2"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "loso_cv_metrics.csv"
    metrics.to_csv(csv_path, index=False)

    summary = {
        "n_states_evaluated": int(len(metrics)),
        "min_corrected_accuracy": float(metrics["corrected_accuracy"].min()),
        "mean_corrected_accuracy": float(metrics["corrected_accuracy"].mean()),
        "median_corrected_accuracy": float(metrics["corrected_accuracy"].median()),
        "states_below_floor": metrics.loc[metrics["below_floor"], "state"].tolist(),
        "accuracy_floor": ACCURACY_FLOOR,
        "agreement_zone_violations_total": int(
            metrics["agreement_zone_violations"].sum()
        ),
        "worst_state": metrics.iloc[0].to_dict() if len(metrics) else None,
    }
    summary_path = out_dir / "loso_cv_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))

    print()
    print("=" * 60)
    print(f"[LOSO] wrote {csv_path}")
    print(f"[LOSO] wrote {summary_path}")
    print(f"[LOSO] mean corrected accuracy: {summary['mean_corrected_accuracy']:.3f}")
    print(f"[LOSO] min  corrected accuracy: {summary['min_corrected_accuracy']:.3f}")
    if summary["states_below_floor"]:
        print(
            f"[LOSO] WARNING: {len(summary['states_below_floor'])} state(s) below "
            f"{ACCURACY_FLOOR:.0%} floor: {summary['states_below_floor']}"
        )
    else:
        print(f"[LOSO] all states ≥ {ACCURACY_FLOOR:.0%} floor — generalization OK")
    if summary["agreement_zone_violations_total"] > 0:
        raise SystemExit(
            f"[LOSO] FATAL: {summary['agreement_zone_violations_total']} agreement-zone "
            "violations across folds — passive rules are touching protected rows."
        )


if __name__ == "__main__":
    main()
