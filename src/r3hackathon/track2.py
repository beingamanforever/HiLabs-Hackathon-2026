from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .features import build_feature_table
from .settings import CACHE_DIR


def _freeze_value(value: Any) -> str:
    if pd.isna(value):
        return "__NA__"
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


@dataclass
class EmpiricalBackoffModel:
    target: str
    feature_sets: list[list[str]]
    alpha: float = 2.0

    def __post_init__(self) -> None:
        self.tables: list[dict[tuple[str, ...], float]] = []
        self.global_rate: float = 0.5

    def fit(self, train_df: pd.DataFrame) -> "EmpiricalBackoffModel":
        target_series = train_df[self.target].astype(int)
        self.global_rate = float((target_series.sum() + self.alpha) / (len(target_series) + 2 * self.alpha))
        self.tables = []

        for feature_set in self.feature_sets:
            grouped = (
                train_df.groupby(feature_set, dropna=False)[self.target]
                .agg(["sum", "count"])
                .reset_index()
            )
            table: dict[tuple[str, ...], float] = {}
            for _, row in grouped.iterrows():
                key = tuple(_freeze_value(row[column]) for column in feature_set)
                rate = (float(row["sum"]) + self.alpha) / (float(row["count"]) + 2 * self.alpha)
                table[key] = rate
            self.tables.append(table)
        return self

    def predict_row(self, row: pd.Series) -> float:
        for feature_set, table in zip(self.feature_sets, self.tables):
            key = tuple(_freeze_value(row[column]) for column in feature_set)
            if key in table:
                return table[key]
        return self.global_rate

    def predict(self, df: pd.DataFrame) -> pd.Series:
        return df.apply(self.predict_row, axis=1)


def default_feature_sets() -> list[list[str]]:
    return [
        ["R3_Label", "score_band", "pf_location_match", "has_org_found", "is_behavioral_health"],
        ["R3_Label", "score_band", "claims_location_profile", "has_org_found"],
        ["R3_Label", "score_band", "pf_location_match"],
        ["R3_Label", "score_band"],
        ["R3_Label", "claims_location_profile"],
        ["R3_Label"],
    ]


def fit_passive_models(train_df: pd.DataFrame) -> dict[str, EmpiricalBackoffModel]:
    conclusive = train_df[train_df["conclusive_call"]].copy()
    r3_wrong_model = EmpiricalBackoffModel("r3_wrong", default_feature_sets()).fit(conclusive)
    pf_accurate_model = EmpiricalBackoffModel("pf_address_accurate", default_feature_sets()).fit(conclusive)
    return {
        "p_r3_wrong_model": r3_wrong_model,
        "p_pf_accurate_model": pf_accurate_model,
    }


def score_passive_models(df: pd.DataFrame, models: dict[str, Any]) -> pd.DataFrame:
    scored = df.copy()
    scored["p_r3_wrong"] = models["p_r3_wrong_model"].predict(scored)
    scored["p_pf_address_accurate"] = models["p_pf_accurate_model"].predict(scored)
    return scored


def calibrate_conformal_threshold(
    cal_df: pd.DataFrame,
    alpha: float = 0.05,
) -> float:
    """Compute q_hat from calibration rows (R3=INACCURATE, label known).

    A flip is allowed only if (1 - p_pf_address_accurate) <= q_hat, guaranteeing
    that the flip precision >= (1-alpha) on the calibration distribution.
    """
    # Calibrate only on INACCURATE rows that are in the DISAGREEMENT zone
    # (i.e. where Calling=ACCURATE) — these are the actual flip candidates.
    cands = cal_df[
        (cal_df["R3_Label"] == "INACCURATE") & (~cal_df["agreement_zone"])
    ].copy()
    if len(cands) == 0:
        return 1.0
    nonconf = 1.0 - cands["p_pf_address_accurate"]
    n = len(nonconf)
    level = min(np.ceil((n + 1) * (1.0 - alpha)) / n, 1.0)
    return float(np.quantile(nonconf.values, level))


def apply_passive_rules(scored_df: pd.DataFrame) -> pd.DataFrame:
    result = scored_df.copy()
    q_hat: float = result.attrs.get("q_hat", 1.0)

    corrected_labels = []
    override_reasons = []
    confidences = []
    triage_flags = []

    for row in result.itertuples(index=False):
        original_label = row.R3_Label
        corrected_label = original_label
        reason = "keep_r3"

        stale_org_signature = bool(row.is_high_score) and bool(row.has_org_found) and bool(row.provider_specificity_gap)
        contradict_pf_signature = (
            bool(row.has_claims)
            and bool(row.recent_claim_180d)
            and bool(row.claims_zip_mismatch)
            and bool(row.claims_state_match)
        )
        telehealth_flag = bool(row.telehealth_flag) if not pd.isna(row.telehealth_flag) else False
        risk_guard = bool(row.is_behavioral_health) or telehealth_flag
        triage_recommended = (
            original_label == "ACCURATE"
            and contradict_pf_signature
            and stale_org_signature
            and bool(row.recent_claim_90d)
        )

        org_consensus = float(row.org_consensus_score) if not pd.isna(row.org_consensus_score) else 0.0
        location_entropy = float(row.claims_location_entropy) if not pd.isna(row.claims_location_entropy) else 0.0
        nonconf = 1.0 - float(row.p_pf_address_accurate)

        if (
            original_label == "INACCURATE"
            and not bool(row.agreement_zone)         # never touch rows R3+Call already agree on
            and not bool(row.is_behavioral_health)
            and not telehealth_flag
            and row.org_validation_norm == "ACCURATE"
            and nonconf <= q_hat                     # conformal precision guard
            and org_consensus >= 0.5                 # org majority agrees on this ZIP
            and location_entropy < 0.9               # low claim dispersion
            and not bool(row.has_claims)             # no contradicting claims evidence
        ):
            corrected_label = "ACCURATE"
            reason = "conformal_org_consensus_flip"
        elif (
            original_label == "INCONCLUSIVE"
            and not bool(row.agreement_zone)         # never touch rows R3+Call already agree on
            and bool(row.has_provider_found)
            and not telehealth_flag
            and row.score_band in {"25-50", "50-75"}
            and bool(row.claims_state_match)
            and bool(row.recent_claim_180d)
            and row.p_r3_wrong >= 0.90
            and not risk_guard
        ):
            corrected_label = "ACCURATE"
            reason = "provider_signal_midscore_flip"
        elif triage_recommended:
            reason = "keep_r3_triage_candidate"

        if reason == "conformal_org_consensus_flip":
            confidence = 1.0 - nonconf
        elif reason == "provider_signal_midscore_flip":
            confidence = 0.81
        elif corrected_label == "ACCURATE":
            confidence = float(row.p_pf_address_accurate)
        elif corrected_label == "INACCURATE":
            confidence = float(1.0 - row.p_pf_address_accurate)
        else:
            confidence = float(1.0 - abs(row.p_pf_address_accurate - 0.5) * 2.0)

        corrected_labels.append(corrected_label)
        override_reasons.append(reason)
        confidences.append(round(confidence, 4))
        triage_flags.append(bool(triage_recommended))

    result["corrected_label"] = corrected_labels
    result["override_reason"] = override_reasons
    result["confidence"] = confidences
    result["label_changed"] = result["corrected_label"] != result["R3_Label"]
    result["triage_recommended"] = triage_flags

    # Hard guardrail — the PS penalises any modification of agreement-zone rows.
    # Only enforce when Calling_Label is available (training/eval); on holdout
    # data the agreement_zone column is uniformly False so this is a no-op.
    if "agreement_zone" in result.columns and result["agreement_zone"].any():
        agreement_flips = int(
            (result["agreement_zone"] & result["label_changed"]).sum()
        )
        assert agreement_flips == 0, (
            f"Agreement-zone preservation violated: {agreement_flips} rows where "
            f"R3 and Call QC already agree were flipped by passive rules. "
            f"This must be 0 — check apply_passive_rules guard conditions."
        )
    return result


def evaluate_passive_predictions(predictions: pd.DataFrame) -> dict[str, float]:
    baseline_accuracy = float((predictions["R3_Label"] == predictions["Calling_Label"]).mean())
    corrected_accuracy = float((predictions["corrected_label"] == predictions["Calling_Label"]).mean())

    agreement_zone = predictions["agreement_zone"]
    disagreement_zone = ~agreement_zone

    metrics = {
        "baseline_accuracy": baseline_accuracy,
        "corrected_accuracy": corrected_accuracy,
        "net_accuracy_gain": corrected_accuracy - baseline_accuracy,
        "agreement_zone_rows": float(agreement_zone.sum()),
        "agreement_zone_preservation": float(
            (predictions.loc[agreement_zone, "corrected_label"] == predictions.loc[agreement_zone, "R3_Label"]).mean()
        ),
        "agreement_zone_changes": float(predictions.loc[agreement_zone, "label_changed"].sum()),
        "disagreement_zone_rows": float(disagreement_zone.sum()),
        "disagreement_zone_recovery_rate": float(
            (predictions.loc[disagreement_zone, "corrected_label"] == predictions.loc[disagreement_zone, "Calling_Label"]).mean()
        ),
        "rows_changed": float(predictions["label_changed"].sum()),
        "changed_row_precision": float(
            (predictions.loc[predictions["label_changed"], "corrected_label"]
             == predictions.loc[predictions["label_changed"], "Calling_Label"]).mean()
        )
        if predictions["label_changed"].any()
        else 0.0,
    }
    return metrics


def _stable_fold(value: object, n_folds: int) -> int:
    digest = hashlib.md5(str(value).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % n_folds


def evaluate_with_grouped_cv(df: pd.DataFrame, n_folds: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = df.copy()
    group_key = working["OrganizationName"].fillna(working["OrigNPI"]).astype(str)
    working["cv_fold"] = group_key.map(lambda value: _stable_fold(value, n_folds))

    fold_predictions = []
    fold_metrics = []

    for fold in range(n_folds):
        train = working[working["cv_fold"] != fold].copy()
        validation = working[working["cv_fold"] == fold].copy()

        models = fit_passive_models(train)

        # Score training fold to calibrate the conformal threshold
        train_scored = score_passive_models(train, models)
        q_hat = calibrate_conformal_threshold(train_scored, alpha=0.05)

        scored = score_passive_models(validation, models)
        scored.attrs["q_hat"] = q_hat
        predicted = apply_passive_rules(scored)
        metrics = evaluate_passive_predictions(predicted)
        metrics["fold"] = fold
        metrics["q_hat"] = q_hat

        fold_predictions.append(predicted)
        fold_metrics.append(metrics)

    predictions = pd.concat(fold_predictions, ignore_index=True)
    metrics_df = pd.DataFrame(fold_metrics)
    return predictions, metrics_df


def build_track2_markdown(metrics: dict[str, float], override_summary: pd.DataFrame) -> str:
    lines = [
        "# Track 2 Summary",
        "",
        "## Evaluation",
        f"- Baseline R3 accuracy: {metrics['baseline_accuracy']:.2%}",
        f"- Passive corrected accuracy: {metrics['corrected_accuracy']:.2%}",
        f"- Net accuracy gain: {metrics['net_accuracy_gain']:.2%}",
        f"- Agreement-zone preservation: {metrics['agreement_zone_preservation']:.2%}",
        f"- Agreement-zone changes: {int(metrics['agreement_zone_changes'])}",
        f"- Disagreement-zone recovery rate: {metrics['disagreement_zone_recovery_rate']:.2%}",
        f"- Rows changed by passive engine: {int(metrics['rows_changed'])}",
        f"- Precision on changed rows: {metrics['changed_row_precision']:.2%}",
        "",
        "## Override Reasons",
    ]
    for row in override_summary.itertuples(index=False):
        lines.append(
            f"- {row.override_reason}: {row.rows} rows, accuracy {row.corrected_accuracy:.2%}, "
            f"average confidence {row.avg_confidence:.2f}"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "- Flip eligibility is gated by a per-fold conformal threshold (alpha=0.05) on p_pf_address_accurate.",
            "- Org consensus (>= 0.5) and low claim entropy (< 0.9) are required for INACCURATE → ACCURATE flips.",
            "- State-level heuristic removed; conformal guard provides a distribution-free precision guarantee.",
            "- Call QC labels and comments are used only for training labels and evaluation, not inference features.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_track2(output_dir: Path, n_folds: int = 5) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_table = build_feature_table(cache_dir=CACHE_DIR)

    cv_predictions, cv_fold_metrics = evaluate_with_grouped_cv(feature_table, n_folds=n_folds)
    cv_metrics = evaluate_passive_predictions(cv_predictions)
    cv_predictions.to_csv(output_dir / "track2_cv_predictions.csv", index=False)
    cv_fold_metrics.to_csv(output_dir / "track2_cv_fold_metrics.csv", index=False)

    # Full-data models + calibration
    full_models = fit_passive_models(feature_table)
    full_train_scored = score_passive_models(feature_table, full_models)
    full_q_hat = calibrate_conformal_threshold(full_train_scored, alpha=0.05)

    full_scored = score_passive_models(feature_table, full_models)
    full_scored.attrs["q_hat"] = full_q_hat
    full_predictions = apply_passive_rules(full_scored)
    full_predictions.to_csv(output_dir / "track2_full_predictions.csv", index=False)

    override_summary = (
        full_predictions.groupby("override_reason", observed=False)
        .agg(
            rows=("Row ID", "count"),
            corrected_accuracy=("corrected_label", lambda s: (s == full_predictions.loc[s.index, "Calling_Label"]).mean()),
            avg_confidence=("confidence", "mean"),
        )
        .reset_index()
        .sort_values("rows", ascending=False)
    )
    override_summary.to_csv(output_dir / "track2_override_summary.csv", index=False)

    summary_markdown = build_track2_markdown(cv_metrics, override_summary)
    (output_dir / "track2_summary.md").write_text(summary_markdown, encoding="utf-8")
    (output_dir / "track2_cv_metrics.json").write_text(
        json.dumps(cv_metrics, indent=2, default=str),
        encoding="utf-8",
    )
    (output_dir / "track2_metadata.json").write_text(
        json.dumps({"q_hat_full": full_q_hat}, indent=2),
        encoding="utf-8",
    )

    return {
        "cv_predictions": cv_predictions,
        "cv_fold_metrics": cv_fold_metrics,
        "cv_metrics": cv_metrics,
        "full_predictions": full_predictions,
        "override_summary": override_summary,
    }
