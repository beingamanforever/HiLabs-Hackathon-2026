"""Track 3 — Robocall triage ranking and simulation.

Implements:
- Empirical conclusiveness model
- Sprint 2: isotonic conformal calibration (fit_conformal_calibration / conformal_select)
- Sprint 3: LightGBM lambdarank + SHAP importance
- Budgeted top-N selection where the 40% conclusive rate is a simulation assumption,
  not a hard selection constraint
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .features import build_feature_table
from .settings import (
    CACHE_DIR,
    CONFORMAL_ALPHA,
    LGB_EARLY_STOPPING,
    LGB_LEARNING_RATE,
    LGB_N_ESTIMATORS,
    LGB_NDCG_EVAL_AT,
    LGB_NUM_LEAVES,
    LGB_MIN_CHILD_SAMPLES,
)
from .track2 import (
    EmpiricalBackoffModel,
    _stable_fold,
    apply_passive_rules,
    calibrate_conformal_threshold,
    evaluate_passive_predictions,
    fit_passive_models,
    score_passive_models,
)

logger = logging.getLogger(__name__)

CALL_BUDGET = 450
CONCLUSIVE_RATE = 0.40
EXPECTED_USABLE_VERDICTS = int(CALL_BUDGET * CONCLUSIVE_RATE)


# ── Conclusive-call model ──────────────────────────────────────────────────────

def default_conclusive_feature_sets() -> list[list[str]]:
    return [
        ["score_band", "phone_share_bucket", "is_behavioral_health", "telehealth_flag", "org_size_bucket"],
        ["score_band", "claims_location_profile", "has_provider_found", "is_behavioral_health"],
        ["score_band", "phone_share_bucket", "telehealth_flag"],
        ["score_band", "org_size_bucket", "claims_location_profile"],
        ["score_band", "is_behavioral_health"],
        ["score_band"],
    ]


def fit_conclusive_model(train_df: pd.DataFrame) -> dict[str, Any]:
    """Fit empirical backoff model for call conclusiveness.

    Args:
        train_df: training feature table with conclusive_call column.

    Returns:
        dict with key 'p_conclusive_model'.
    """
    model = EmpiricalBackoffModel("conclusive_call", default_conclusive_feature_sets(), alpha=2.0).fit(train_df)
    return {"p_conclusive_model": model}


def score_conclusive_model(df: pd.DataFrame, models: dict[str, Any]) -> pd.DataFrame:
    scored = df.copy()
    scored["p_conclusive_rank"] = models["p_conclusive_model"].predict(scored)
    return scored


# ── Sprint 2: Isotonic conformal calibration ──────────────────────────────────

def _pava(y: np.ndarray) -> np.ndarray:
    """Pool Adjacent Violators Algorithm — pure numpy, no sklearn needed.

    Produces a non-decreasing sequence that minimises sum-of-squares to y.
    """
    y = y.astype(float)
    # Represent the solution as a list of (block_mean, block_size) pairs
    groups: list[list[float]] = []  # each entry: [mean, size]

    for yi in y:
        groups.append([float(yi), 1.0])
        # Merge backwards while the constraint is violated
        while len(groups) >= 2 and groups[-2][0] > groups[-1][0]:
            m1, n1 = groups[-2]
            m2, n2 = groups[-1]
            merged_mean = (m1 * n1 + m2 * n2) / (n1 + n2)
            groups[-2:] = [[merged_mean, n1 + n2]]

    result = np.empty(len(y))
    pos = 0
    for mean, size in groups:
        n = int(round(size))
        result[pos: pos + n] = mean
        pos += n
    return result


def fit_conformal_calibration(
    p_wrong_raw: np.ndarray,
    true_labels: np.ndarray,
    calib_mask: np.ndarray,
    alpha: float = CONFORMAL_ALPHA,
) -> tuple[np.ndarray, float, dict[str, Any]]:
    """Isotonic recalibration + conformal risk threshold for triage scores.

    Fits an isotonic regression on the calibration fold to recalibrate
    raw p_wrong scores, then computes a nonconformity-based threshold
    lambda_hat that provides a marginal coverage guarantee.

    Args:
        p_wrong_raw: raw empirical p_r3_wrong scores (n,).
        true_labels: binary array — 1 where R3 was actually wrong (n,).
        calib_mask: boolean array selecting the calibration fold rows (n,).
        alpha: miscoverage rate (default CONFORMAL_ALPHA = 0.05 → 95% coverage).

    Returns:
        (p_cal, lambda_hat, meta) where:
        - p_cal: isotonic-recalibrated scores for all rows
        - lambda_hat: conformal threshold; rows with p_cal > lambda_hat are uncertain
        - meta: dict with lambda_hat, uncertain_pool_size, coverage_guarantee
    """
    # ── Isotonic fit on calibration fold ────────────────────────────────────
    cal_raw = p_wrong_raw[calib_mask]
    cal_labels = true_labels[calib_mask].astype(float)

    # Sort by raw score, apply PAVA, interpolate back
    sort_idx = np.argsort(cal_raw)
    sorted_labels = cal_labels[sort_idx]
    iso_values = _pava(sorted_labels)

    # Predict on all rows via linear interpolation (clip to [0,1])
    p_cal = np.clip(np.interp(p_wrong_raw, cal_raw[sort_idx], iso_values), 0.0, 1.0)

    # ── Nonconformity scores on calibration fold ─────────────────────────────
    # For a row that IS wrong (label=1): nonconformity = 1 - p_cal  (bad if score low)
    # For a row that IS correct (label=0): nonconformity = p_cal     (bad if score high)
    p_cal_cal = p_cal[calib_mask]
    nc_scores = np.where(
        cal_labels == 1,
        1.0 - p_cal_cal,
        p_cal_cal,
    )

    n_cal = int(calib_mask.sum())
    q_level = min(np.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal, 1.0)
    lambda_hat = float(np.quantile(nc_scores, q_level))

    uncertain_pool_size = int((p_cal > lambda_hat).sum())
    meta = {
        "lambda_hat": round(lambda_hat, 6),
        "uncertain_pool_size": uncertain_pool_size,
        "coverage_guarantee": f"{(1.0 - alpha) * 100:.0f}%",
        "n_calibration_rows": n_cal,
        "alpha": alpha,
    }
    return p_cal, lambda_hat, meta


def conformal_select(
    df: pd.DataFrame,
    p_cal: np.ndarray,
    lambda_hat: float,
    n_calls: int = CALL_BUDGET,
    gain_col: str = "business_gain",
    score_col: str | None = None,
    alpha: float = CONFORMAL_ALPHA,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Rank rows with conformal uncertainty as the first-class selection signal.

    Rows where p_cal > lambda_hat are the 'uncertain' pool — the model is
    not confident about them, so a call is most valuable there. If the
    uncertain pool is smaller than the budget, the remainder is backfilled
    with the highest-ranked active-review rows outside that pool.

    Args:
        df: triage-featured DataFrame (all rows).
        p_cal: calibrated p_wrong scores aligned with df's index (n,).
        lambda_hat: conformal threshold from fit_conformal_calibration.
        n_calls: number of calls to select.
        gain_col: column used as secondary sort criterion.
        score_col: optional primary ranking score within the uncertain pool.
        alpha: conformal miscoverage rate used for the coverage guarantee string.

    Returns:
        (full_ranking_df, selection_meta)
    """
    work = df.copy().reset_index(drop=True)
    work["p_wrong_cal"] = p_cal
    work["conformal_uncertain"] = work["p_wrong_cal"] > lambda_hat
    ranking_score = score_col if score_col and score_col in work.columns else "p_wrong_cal"
    ranked = select_call_budget(work, score_col=ranking_score, n_calls=n_calls, gain_col=gain_col)
    selected = ranked[ranked["selected_for_call"]].copy()
    uncertain_active = work["conformal_uncertain"] & work["needs_active_review"].fillna(False)

    meta = {
        "lambda_hat": round(lambda_hat, 6),
        "uncertain_pool_size": int(uncertain_active.sum()),
        "coverage_guarantee": f"{(1 - alpha) * 100:.0f}%",
        "conformal_selected": int(selected["conformal_uncertain"].sum()),
        "selected": int(len(selected)),
    }
    return ranked, meta


# ── Sprint 3: LightGBM lambdarank + SHAP ──────────────────────────────────────

def _build_ranker_features(df: pd.DataFrame) -> list[str]:
    """Dynamically build the feature list from whatever numeric/bool columns exist.

    Excludes label-leaking columns (Calling_*, r3_wrong, agreement_zone, etc.)
    and free-text / high-cardinality columns.
    """
    exclude_prefixes = (
        "call_keyword_",  # derived from Call QC comments → label leakage
        "Address_",       # raw URL text columns
        "Mcheck",
        "hco_address",
        "hco_city",
        "hco_state",
    )
    exclude_exact = {
        "Calling_Label", "Calling_Address", "Calling_Phone",
        "Comment_Call_QC", "Comment_Web_QC",
        "r3_wrong", "agreement_zone", "pf_address_accurate", "conclusive_call",
        "corrected_label", "override_reason", "label_changed",
        "triage_recommended",
        "NPI", "OrigNPI", "Row ID", "FirstName", "MiddleName", "LastName",
        "Address1", "City", "OrganizationName", "Phone", "Phone_norm",
        "Zip", "Zip_norm", "State", "County",
        "org_majority_zip", "dominant_claims_zip", "secondary_claims_zip",
        "claims_zip", "claims_state", "site_of_care_mode",
        "hco_zip_5", "latest_dos", "dominant_claim_latest_dos", "secondary_claim_latest_dos",
        "triage_reason_codes", "cv_fold",
    }
    numeric_dtypes = {"int64", "int32", "float64", "float32", "bool", "uint8"}
    cols = []
    for col in df.columns:
        if col in exclude_exact:
            continue
        if any(col.startswith(p) for p in exclude_prefixes):
            continue
        if str(df[col].dtype) not in numeric_dtypes:
            continue
        cols.append(col)
    return cols


def train_lgb_ranker(
    df: pd.DataFrame,
    output_dir: Path,
    label_col: str = "r3_wrong",
    group_col: str = "OrganizationName",
) -> tuple[pd.DataFrame, Any]:
    """Train a LightGBM LambdaRank model to replace the product-score triage.

    Uses GroupShuffleSplit by org group, ndcg_eval_at from settings.py.

    Args:
        df: fully featured DataFrame including all Sprint 1 columns.
        output_dir: directory for SHAP importance CSV.
        label_col: binary relevance label (r3_wrong).
        group_col: column used to define ranking groups (org).

    Returns:
        (df_with_lgb_score, model) where df_with_lgb_score has triage_score_lgb column.
    """
    try:
        import lightgbm as lgb
    except ImportError:
        logger.warning("lightgbm not installed — skipping LGB ranker, using triage_score as fallback")
        result = df.copy()
        result["triage_score_lgb"] = result.get("triage_score", pd.Series(0.0, index=df.index))
        return result, None

    from sklearn.model_selection import GroupShuffleSplit

    feature_cols = _build_ranker_features(df)
    work = df.copy().reset_index(drop=True)

    # Encode boolean / object columns as int
    X = work[feature_cols].copy()
    for col in X.columns:
        if X[col].dtype == bool or str(X[col].dtype) == "object":
            X[col] = X[col].astype(int)
    X = X.fillna(0)

    y = work[label_col].fillna(0).astype(int)
    groups = work[group_col].fillna("__UNKNOWN__").astype(str)

    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, val_idx = next(gss.split(X, y, groups=groups))

    # Build group sizes for LGB (must be sorted by group)
    train_order = work.iloc[train_idx].sort_values(group_col).index
    val_order = work.iloc[val_idx].sort_values(group_col).index

    train_frame = work.loc[train_order].copy().reset_index(drop=True)
    val_frame = work.loc[val_order].copy().reset_index(drop=True)
    X_train = X.loc[train_order].reset_index(drop=True)
    X_val = X.loc[val_order].reset_index(drop=True)
    y_train = y.loc[train_order].reset_index(drop=True)
    y_val = y.loc[val_order].reset_index(drop=True)

    train_groups = train_frame[group_col].fillna("__UNKNOWN__").astype(str)
    val_groups = val_frame[group_col].fillna("__UNKNOWN__").astype(str)
    train_group_sizes = train_groups.groupby(train_groups, sort=False).size().tolist()
    val_group_sizes = val_groups.groupby(val_groups, sort=False).size().tolist()

    dtrain = lgb.Dataset(X_train, label=y_train, group=train_group_sizes)
    dval = lgb.Dataset(X_val, label=y_val, group=val_group_sizes)

    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": LGB_NDCG_EVAL_AT,
        "num_leaves": LGB_NUM_LEAVES,
        "learning_rate": LGB_LEARNING_RATE,
        "min_child_samples": LGB_MIN_CHILD_SAMPLES,
        "verbose": -1,
    }

    model = lgb.train(
        params,
        dtrain,
        num_boost_round=LGB_N_ESTIMATORS,
        valid_sets=[dval],
        valid_names=["val"],
        callbacks=[
            lgb.early_stopping(LGB_EARLY_STOPPING, verbose=False),
            lgb.log_evaluation(50),
        ],
    )

    work["triage_score_lgb"] = model.predict(X)

    # ── SHAP feature importance ──────────────────────────────────────────────
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        shap_df = pd.DataFrame({
            "feature": feature_cols,
            "mean_abs_shap": mean_abs_shap,
        }).sort_values("mean_abs_shap", ascending=False).head(10).reset_index(drop=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        shap_df.to_csv(output_dir / "shap_importance.csv", index=False)
        logger.info("SHAP importance saved to %s/shap_importance.csv", output_dir)
    except Exception as exc:
        logger.warning("SHAP computation failed: %s", exc)

    return work, model


# ── Business gain + triage score ──────────────────────────────────────────────

def add_triage_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute business_gain, triage_score, and reason codes.

    Args:
        df: DataFrame after passive rules and conclusiveness scoring.

    Returns:
        df with business_gain, needs_active_review, triage_score,
        conformal_set_flag, triage_reason_codes appended.
    """
    result = df.copy()

    gain = pd.Series(1.0, index=result.index, dtype=float)
    gain += np.where(result["R3_Label"] == "ACCURATE", 0.35, 0.0)
    gain += np.where(result["R3_Label"] == "INCONCLUSIVE", 0.20, 0.0)
    gain += np.where(result["triage_recommended"], 0.35, 0.0)
    gain += np.where(result["multi_location_claims"], 0.20, 0.0)
    gain += np.where(result["high_location_entropy"], 0.10, 0.0)
    gain += np.clip(result["org_record_count"].fillna(0) / 50.0, 0.0, 0.40)
    gain += np.clip(result["claim_rows"].fillna(0) / 200.0, 0.0, 0.35)
    # Staleness bonus: favour rows cold at PF location in claims history
    gain += result["address_staleness_score"].fillna(1.0) * 0.20
    # Org consensus penalty: high consensus = PF ZIP is well-supported → less urgent
    gain -= result["org_consensus_score"].fillna(0.5) * 0.15
    # Positive net tier-1 signal reduces urgency (address confirmed by trusted source)
    gain -= np.clip(result["net_tier1_signal"].fillna(0) * 0.05, 0.0, 0.20)

    result["business_gain"] = gain.clip(lower=0.0).round(4)

    # needs_active_review = "the passive layer did not resolve this row".
    # Derivation chain (audited for no Call-QC leakage):
    #   label_changed comes from track2.apply_passive_rules, whose inputs are:
    #     R3 outputs (R3_Label, score_band), web/aggregator evidence counts,
    #     claims-derived signals, specialty/telehealth flags, org_consensus_score,
    #     and the Track-2 empirical model outputs (p_r3_wrong, p_pf_address_accurate).
    #   The empirical models *train* on Calling_Label (allowed per PS — labels for
    #   training/eval are permitted) but *predict* from signal features only.
    #   No row-level Call-QC field flows into the prediction path, so this column
    #   is safe to use at inference time on the unseen holdout.
    unresolved = ~result["label_changed"]
    result["needs_active_review"] = unresolved
    result["triage_score"] = (
        result["p_r3_wrong"].fillna(0.0)
        * result["p_conclusive_rank"].fillna(0.0)
        * result["business_gain"].fillna(1.0)
        * unresolved.astype(float)
    ).round(6)

    reason_codes: list[str] = []
    for row in result.itertuples(index=False):
        codes: list[str] = []
        if row.triage_recommended:
            codes.append("stale_org_triage")
        if row.multi_location_claims:
            codes.append("multi_location_claims")
        if row.high_location_entropy:
            codes.append("diffuse_claim_pattern")
        if row.provider_specificity_gap:
            codes.append("org_provider_gap")
        if row.has_provider_found:
            codes.append("provider_page_signal")
        if row.is_behavioral_health:
            codes.append("behavioral_health")
        if getattr(row, "telehealth_flag", 0):
            codes.append("telehealth")
        if row.pf_location_match == "absent_from_claims":
            codes.append("pf_absent_from_claims")
        if row.pf_location_match == "secondary_match":
            codes.append("secondary_claim_location")
        if row.score_band in {"25-50", "50-75"}:
            codes.append("mid_score_band")
        if row.score_band in {"<=0", "0-25"}:
            codes.append("low_score_band")
        if row.phone_share_bucket in {"0", "20+"}:
            codes.append("hard_to_call_phone_pattern")
        reason_codes.append("|".join(codes[:6]))
    result["triage_reason_codes"] = reason_codes
    return result


# ── Budgeted top-N selection ──────────────────────────────────────────────────

def select_call_budget(
    df: pd.DataFrame,
    score_col: str = "triage_score",
    n_calls: int = CALL_BUDGET,
    gain_col: str = "business_gain",
) -> pd.DataFrame:
    """Select the top *n_calls* active-review rows with conformal priority.

    Args:
        df: DataFrame with needs_active_review, score_col, and conformal_uncertain.
        score_col: ranking column (triage_score or triage_score_lgb).
        n_calls: number of rows to select for calling.
        gain_col: business-value tie-breaker.

    Returns:
        df with selected_for_call (bool), call_rank (int), and
        p_conclusive_calibrated columns added.
    """
    ranking = df.copy().sort_values(
        ["needs_active_review", "conformal_uncertain", score_col, "p_wrong_cal", "p_r3_wrong", gain_col],
        ascending=[False, False, False, False, False, False],
    ).reset_index(drop=True)

    candidate_idx = ranking.index[ranking["needs_active_review"].fillna(False)].tolist()
    selected_idx = candidate_idx[:n_calls]

    ranking["selected_for_call"] = False
    ranking.loc[selected_idx, "selected_for_call"] = True
    ranking["call_rank"] = pd.NA
    ranking.loc[selected_idx, "call_rank"] = np.arange(1, len(selected_idx) + 1)

    sel = ranking["selected_for_call"]
    raw_mean = ranking.loc[sel, "p_conclusive_rank"].mean()
    scale = CONCLUSIVE_RATE / raw_mean if (not pd.isna(raw_mean) and raw_mean > 0) else 1.0
    ranking["p_conclusive_calibrated"] = np.clip(
        ranking["p_conclusive_rank"].fillna(0.0) * scale, 0.01, 0.99
    )
    ranking.loc[~sel, "p_conclusive_calibrated"] = 0.0
    return ranking


# ── Simulation ────────────────────────────────────────────────────────────────

def simulate_track3_value(
    df: pd.DataFrame,
    n_calls: int = CALL_BUDGET,
    conclusive_rate: float = CONCLUSIVE_RATE,
) -> dict[str, float]:
    """Estimate expected accuracy lift from the selected call budget.

    Args:
        df: output of select_call_budget with selected_for_call column.
        n_calls: configured call budget.
        conclusive_rate: expected usable-verdict rate.

    Returns:
        dict of scalar metrics.
    """
    selected = df[df["selected_for_call"]].copy()
    total_rows = len(df)
    expected_usable_verdicts = int(round(n_calls * conclusive_rate))

    if selected.empty:
        return {
            "call_budget": float(n_calls),
            "selected_rows": 0.0,
            "expected_usable_verdicts": float(expected_usable_verdicts),
            "selected_mean_p_wrong": 0.0,
            "selected_mean_p_conclusive_rank": 0.0,
            "selected_mean_business_gain": 0.0,
            "expected_accuracy_gain_records": 0.0,
            "expected_accuracy_gain_points": 0.0,
            "expected_combined_accuracy": float((df["corrected_label"] == df["Calling_Label"]).mean()),
            "oracle_selected_correctable_rows": 0.0,
            "selected_conformal_set_pct": 0.0,
        }

    weighted = selected["p_conclusive_calibrated"].fillna(0.0)
    weighted = weighted / weighted.sum() if weighted.sum() > 0 else pd.Series(
        1.0 / len(selected), index=selected.index
    )
    correctable = (
        selected["conclusive_call"] & (selected["corrected_label"] != selected["Calling_Label"])
    ).astype(float)
    gain_records = float((weighted * correctable).sum() * expected_usable_verdicts)
    passive_accuracy = float((df["corrected_label"] == df["Calling_Label"]).mean())

    conf_pct = float(selected.get("conformal_uncertain", pd.Series(False, index=selected.index)).mean())

    return {
        "call_budget": float(n_calls),
        "selected_rows": float(len(selected)),
        "expected_usable_verdicts": float(expected_usable_verdicts),
        "selected_mean_p_wrong": float(selected["p_r3_wrong"].mean()),
        "selected_mean_p_conclusive_rank": float(selected["p_conclusive_rank"].mean()),
        "selected_mean_business_gain": float(selected["business_gain"].mean()),
        "expected_accuracy_gain_records": gain_records,
        "expected_accuracy_gain_points": gain_records / total_rows,
        "expected_combined_accuracy": passive_accuracy + gain_records / total_rows,
        "oracle_selected_correctable_rows": float(correctable.sum()),
        "conformal_uncertain_in_selected": conf_pct,
    }


# ── Markdown builder ──────────────────────────────────────────────────────────

def build_track3_markdown(
    metrics: dict[str, float],
    top_calls: pd.DataFrame,
    conformal_meta: dict[str, Any] | None = None,
    shap_path: Path | None = None,
) -> str:
    lines = [
        "# Track 3 Summary",
        "",
        "## Budgeted Triage",
        f"- Call budget: {int(metrics['call_budget'])}",
        f"- Selected rows for robocall: {int(metrics['selected_rows'])}",
        f"- Official expected usable verdicts: {int(metrics['expected_usable_verdicts'])}",
        f"- Mean p_wrong (selected): {metrics['selected_mean_p_wrong']:.2%}",
        f"- Mean p_conclusive_rank (selected): {metrics['selected_mean_p_conclusive_rank']:.2%}",
        f"- Mean business gain (selected): {metrics['selected_mean_business_gain']:.2f}",
    ]
    if conformal_meta:
        lines += [
            "",
            "## Conformal Calibration (Sprint 2)",
            f"- lambda_hat: {conformal_meta.get('lambda_hat', 'N/A')}",
            f"- uncertain_pool_size: {conformal_meta.get('uncertain_pool_size', 'N/A')}",
            f"- coverage_guarantee: {conformal_meta.get('coverage_guarantee', 'N/A')}",
            f"- calibration_rows: {conformal_meta.get('n_calibration_rows', 'N/A')}",
        ]
    lines += [
        "",
        "## Simulation",
        f"- Expected accuracy gain (records): {metrics['expected_accuracy_gain_records']:.1f}",
        f"- Expected accuracy gain (points): {metrics['expected_accuracy_gain_points']:.2%}",
        f"- Expected combined accuracy (T2+T3): {metrics['expected_combined_accuracy']:.2%}",
        f"- Oracle correctable rows in selected {int(metrics['call_budget'])}: {int(metrics['oracle_selected_correctable_rows'])}",
    ]
    if "ranker_ndcg_at_450" in metrics:
        lines += [
            "",
            "## Ranker Quality",
            f"- NDCG@50: {metrics.get('ranker_ndcg_at_50', 0.0):.4f}",
            f"- NDCG@100: {metrics.get('ranker_ndcg_at_100', 0.0):.4f}",
            f"- NDCG@450: {metrics.get('ranker_ndcg_at_450', 0.0):.4f}",
        ]
    lines += ["", "## Top Call Targets"]
    score_col = "triage_score_lgb" if "triage_score_lgb" in top_calls.columns else "triage_score"
    for _, row in top_calls.iterrows():
        conf_flag = "✓" if row.get("conformal_uncertain", False) else "·"
        lines.append(
            f"- [{conf_flag}] Rank {int(row['call_rank'])} | Row {int(row['Row ID'])} | "
            f"{row['OrganizationName']} | score {row[score_col]:.4f} | "
            f"p_wrong {row['p_r3_wrong']:.2%} | staleness {row.get('address_staleness_score', 0):.2f} | "
            f"reasons: {row['triage_reason_codes']}"
        )
    lines += [
        "",
        "## Notes",
        "- The 40% conclusive rate is used in simulation only, not as a hard selection quota.",
        "- Sprint 2: isotonic conformal calibration provides 95% coverage guarantee on uncertain pool.",
        "- Sprint 3: LightGBM lambdarank score used when available (triage_score_lgb).",
        f"- ✓ = conformal-uncertain row (model recommends a call with coverage guarantee).",
        "- staleness_score: 0=fresh claims at PF ZIP, 1=no recent claims (maximally stale).",
    ]
    if shap_path and shap_path.exists():
        lines += ["", f"- SHAP top-10 features saved to: {shap_path}"]
    return "\n".join(lines) + "\n"


# ── Main entry point ──────────────────────────────────────────────────────────

def run_track3(
    output_dir: Path,
    n_folds: int = 5,
    n_calls: int = CALL_BUDGET,
    alpha: float = CONFORMAL_ALPHA,
) -> dict[str, Any]:
    """Full Track 3 pipeline: passive correction → conformal triage → call selection.

    Args:
        output_dir: directory to write all CSV / JSON / MD outputs.
        n_folds: number of grouped CV folds.
        n_calls: call budget for triage selection.
        alpha: conformal miscoverage rate.

    Returns:
        dict with cv_ranking, full_ranking, metrics, top_calls, conformal_meta.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_table = build_feature_table(cache_dir=CACHE_DIR)

    # ── CV loop: passive + conclusiveness ────────────────────────────────────
    working = feature_table.copy()
    group_key = working["OrganizationName"].fillna(working["OrigNPI"]).astype(str)
    working["cv_fold"] = group_key.map(lambda v: _stable_fold(v, n_folds))

    passive_cv_preds: list[pd.DataFrame] = []
    for fold in range(n_folds):
        train = working[working["cv_fold"] != fold].copy()
        val = working[working["cv_fold"] == fold].copy()

        pm = fit_passive_models(train)
        train_scored = score_passive_models(train, pm)
        q_hat = calibrate_conformal_threshold(train_scored, alpha=alpha)

        val_scored = score_passive_models(val, pm)
        val_scored.attrs["q_hat"] = q_hat
        val_pred = apply_passive_rules(val_scored)

        cm = fit_conclusive_model(train)
        val_with_conc = score_conclusive_model(val_pred, cm)
        passive_cv_preds.append(val_with_conc)

    cv_predictions = pd.concat(passive_cv_preds, ignore_index=True)
    cv_predictions = add_triage_features(cv_predictions)

    # ── Sprint 2: conformal calibration on CV predictions ───────────────────
    p_wrong_raw = cv_predictions["p_r3_wrong"].fillna(0.0).values
    true_labels = cv_predictions["r3_wrong"].fillna(False).astype(int).values

    candidate_mask = cv_predictions["needs_active_review"].fillna(False).values
    calib_mask = candidate_mask & (cv_predictions["cv_fold"] == 0).values
    if calib_mask.sum() < 10:
        calib_mask = candidate_mask if candidate_mask.sum() >= 10 else np.ones(len(cv_predictions), dtype=bool)

    p_cal_cv, lambda_hat, conformal_meta = fit_conformal_calibration(
        p_wrong_raw, true_labels, calib_mask, alpha=alpha
    )
    cv_ranking, selection_meta = conformal_select(
        cv_predictions,
        p_cal_cv,
        lambda_hat,
        n_calls=n_calls,
        gain_col="business_gain",
        score_col="triage_score",
        alpha=alpha,
    )
    conformal_meta = {**conformal_meta, **selection_meta}
    cv_metrics = simulate_track3_value(cv_ranking, n_calls=n_calls)
    cv_ranking.to_csv(output_dir / "track3_cv_ranking.csv", index=False)

    passive_metrics = evaluate_passive_predictions(cv_ranking)

    # ── Full-data models ─────────────────────────────────────────────────────
    full_pm = fit_passive_models(feature_table)
    full_train_scored = score_passive_models(feature_table, full_pm)
    full_q_hat = calibrate_conformal_threshold(full_train_scored, alpha=alpha)

    full_scored = score_passive_models(feature_table, full_pm)
    full_scored.attrs["q_hat"] = full_q_hat
    full_passive = apply_passive_rules(full_scored)

    full_cm = fit_conclusive_model(feature_table)
    full_triage = score_conclusive_model(full_passive, full_cm)
    full_triage = add_triage_features(full_triage)

    # Sprint 2 conformal on full data
    full_p_raw = full_triage["p_r3_wrong"].fillna(0.0).values
    full_labels = full_triage["r3_wrong"].fillna(False).astype(int).values
    full_candidate_mask = full_triage["needs_active_review"].fillna(False).values
    full_calib_mask = full_candidate_mask if full_candidate_mask.sum() >= 10 else np.ones(len(full_triage), dtype=bool)
    full_p_cal, full_lambda_hat, full_conformal_meta = fit_conformal_calibration(
        full_p_raw, full_labels, full_calib_mask, alpha=alpha
    )
    full_triage["p_wrong_cal"] = full_p_cal
    full_triage["conformal_uncertain"] = full_p_cal > full_lambda_hat

    # Sprint 3: LightGBM ranker
    shap_path = output_dir / "shap_importance.csv"
    full_triage, lgb_model = train_lgb_ranker(full_triage, output_dir=output_dir)

    # Select using LGB score if available, else triage_score
    score_col = "triage_score_lgb" if lgb_model is not None else "triage_score"
    full_ranking, full_selection_meta = conformal_select(
        full_triage,
        full_p_cal,
        full_lambda_hat,
        n_calls=n_calls,
        gain_col="business_gain",
        score_col=score_col,
        alpha=alpha,
    )
    full_conformal_meta = {**full_conformal_meta, **full_selection_meta}
    full_metrics = simulate_track3_value(full_ranking, n_calls=n_calls)

    top_calls = full_ranking[full_ranking["selected_for_call"]].head(25).copy()
    full_ranking.to_csv(output_dir / "track3_full_ranking.csv", index=False)
    top_calls.to_csv(output_dir / "track3_top_calls.csv", index=False)

    # Merge conformal meta into metrics
    ranker_metrics: dict[str, float] = {}
    if lgb_model is not None:
        for key, value in lgb_model.best_score.get("val", {}).items():
            if key.startswith("ndcg@"):
                ndcg_suffix = key.split("@", 1)[1]
                ranker_metrics[f"ranker_ndcg_at_{ndcg_suffix}"] = float(value)

    combined_metrics: dict[str, Any] = {
        "baseline_r3_accuracy": passive_metrics["baseline_accuracy"],
        "passive_corrected_accuracy": passive_metrics["corrected_accuracy"],
        **cv_metrics,
        **{f"conformal_{k}": v for k, v in conformal_meta.items()},
        **ranker_metrics,
        "deployment_selected_rows": float(full_ranking["selected_for_call"].sum()),
        "deployment_conformal_selected": float(
            full_ranking.loc[full_ranking["selected_for_call"], "conformal_uncertain"].sum()
        ),
    }

    (output_dir / "track3_metrics.json").write_text(
        json.dumps(combined_metrics, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "track3_summary.md").write_text(
        build_track3_markdown(
            combined_metrics, top_calls,
            conformal_meta=conformal_meta,
            shap_path=shap_path if shap_path.exists() else None,
        ),
        encoding="utf-8",
    )

    return {
        "cv_ranking": cv_ranking,
        "full_ranking": full_ranking,
        "metrics": combined_metrics,
        "top_calls": top_calls,
        "conformal_meta": full_conformal_meta,
        "cv_conformal_meta": conformal_meta,
        "lgb_model": lgb_model,
    }
