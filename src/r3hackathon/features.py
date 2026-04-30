"""Feature engineering for the R3 hackathon pipeline.

All functions operate on DataFrames and return DataFrames.  No column names,
thresholds, or domain strings are hardcoded here — everything is imported from
settings.py so a single change there propagates everywhere.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .data import aggregate_claims_for_base, load_base_data
from .nppes import load_nppes_extract, merge_nppes_features
from .settings import (
    BASE_DATA_FILE,
    BEHAVIORAL_HEALTH_KEYWORDS,
    CACHE_DIR,
    CLAIMS_DATA_FILE,
    COMMENT_PATTERNS,
    CONCLUSIVE_LABELS,
    NPPES_DATA_FILE,
    STALENESS_HALF_LIFE_DAYS,
    TIER1_PATTERNS,
    TIER3_PATTERNS,
    URL_EVIDENCE_COLUMNS,
)


# ── Label helpers ──────────────────────────────────────────────────────────────

def normalize_validation_label(value: object) -> str:
    """Map raw label text to one of ACCURATE / INACCURATE / INCONCLUSIVE / UNKNOWN."""
    if pd.isna(value):
        return "UNKNOWN"
    text = str(value).strip().upper()
    if text.startswith("ACCURATE"):
        return "ACCURATE"
    if text.startswith("INACCURATE"):
        return "INACCURATE"
    if text.startswith("INCONCLUSIVE"):
        return "INCONCLUSIVE"
    return text or "UNKNOWN"


def parse_r3_label(value: object) -> str:
    return normalize_validation_label(value)


def normalize_zip(value: object) -> str | None:
    """Normalise ZIP to a plain 5-digit string, or None."""
    if pd.isna(value):
        return None
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        text = str(value).strip()
        return text if text else None


def normalize_phone(value: object) -> str | None:
    """Strip non-digit characters from phone numbers."""
    if pd.isna(value):
        return None
    digits = re.sub(r"\D+", "", str(value))
    return digits or None


def score_band(score: object) -> str:
    """Bin a raw R3 score into a labelled band."""
    if pd.isna(score):
        return "UNKNOWN"
    try:
        v = float(score)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if v <= 0:
        return "<=0"
    if v <= 25:
        return "0-25"
    if v <= 50:
        return "25-50"
    if v <= 75:
        return "50-75"
    return "75-100"


def count_urls(value: object) -> int:
    """Count HTTP/HTTPS URLs in a cell value (pipe-separated)."""
    if pd.isna(value):
        return 0
    return len(re.findall(r"https?://", str(value), flags=re.IGNORECASE))


def is_behavioral_health(specialty: object) -> bool:
    if pd.isna(specialty):
        return False
    specialty_upper = str(specialty).upper()
    return any(kw in specialty_upper for kw in BEHAVIORAL_HEALTH_KEYWORDS)


# ── Sprint 1a: Org consensus anchor ───────────────────────────────────────────

def compute_org_consensus(df: pd.DataFrame) -> pd.DataFrame:
    """Add org-level consensus features based on shared PF ZIP across co-org providers.

    Args:
        df: DataFrame that already contains Zip_norm, OrganizationName,
            Final_R3_Score_Address, and OrigNPI columns.

    Returns:
        df with four new columns:
        - org_majority_zip     : modal PF ZIP for this provider's organisation
        - org_npi_count        : number of NPIs in the same organisation
        - org_consensus_match  : 1 if this row's PF ZIP matches org_majority_zip, else 0
        - org_consensus_score  : share of org NPI-weight at majority ZIP,
                                 weighted by Final_R3_Score_Address
    """
    result = df.copy()
    org_key = result["OrganizationName"].fillna("__UNKNOWN__").astype(str)
    zip_col = result["Zip_norm"].fillna("")
    score_col = pd.to_numeric(result["Final_R3_Score_Address"], errors="coerce").fillna(0.0)

    # Majority ZIP per org
    majority_zip = org_key.map(
        df.assign(_org=org_key, _zip=zip_col)
        .groupby("_org")["_zip"]
        .agg(lambda x: x.value_counts().index[0] if len(x) > 0 else "")
    )

    # NPI count per org
    org_npi_count = org_key.map(org_key.value_counts())

    # Boolean match
    consensus_match = (zip_col == majority_zip).astype(int)

    # Weighted score: sum of R3 scores for matching ZIPs / total R3 score in org
    def _weighted_score(grp_df: pd.DataFrame) -> float:
        total_w = grp_df["_score"].sum()
        if total_w == 0:
            return 0.5
        mode_zip = grp_df["_zip"].value_counts().index[0]
        match_w = grp_df.loc[grp_df["_zip"] == mode_zip, "_score"].sum()
        return float(match_w / total_w)

    score_map = (
        df.assign(_org=org_key, _zip=zip_col, _score=score_col)
        .groupby("_org")
        .apply(_weighted_score)
    )
    consensus_score = org_key.map(score_map).fillna(0.5)

    result["org_majority_zip"] = majority_zip
    result["org_npi_count"] = org_npi_count.fillna(1).astype(int)
    result["org_consensus_match"] = consensus_match
    result["org_consensus_score"] = consensus_score.round(4)
    return result


# ── Sprint 1b: Continuous staleness score ─────────────────────────────────────

def compute_staleness(
    df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Add exponential-decay staleness features for the PF address.

    The decay uses half-life STALENESS_HALF_LIFE_DAYS from settings.py.
    Rows where the PF ZIP is the dominant claims ZIP get a meaningful decay;
    all other rows receive maximum staleness (1.0).

    Args:
        df: merged feature table; requires dominant_claim_latest_dos,
            dominant_claims_zip_match, claim_rows, dominant_claim_share.
        reference_date: baseline for age computation. Defaults to max(latest_dos).

    Returns:
        df with two new columns:
        - address_staleness_score  : 0 (fresh) → 1 (maximally stale)
        - staleness_weighted       : staleness × log1p(claims_volume_at_pf_zip)
    """
    result = df.copy()

    if reference_date is None:
        reference_date = pd.to_datetime(result["latest_dos"]).max()
        if pd.isna(reference_date):
            result["address_staleness_score"] = 1.0
            result["staleness_weighted"] = 0.0
            return result

    lam = math.log(2) / STALENESS_HALF_LIFE_DAYS

    # Days since last claim at the PF ZIP (dominant match only)
    dom_dos = pd.to_datetime(result.get("dominant_claim_latest_dos"), errors="coerce")
    days_at_pf = (reference_date - dom_dos).dt.days.clip(lower=0)

    is_pf_dominant = result.get("dominant_claims_zip_match", pd.Series(False, index=result.index))

    staleness = np.where(
        is_pf_dominant.fillna(False),
        np.clip(1.0 - np.exp(-lam * days_at_pf.fillna(999)), 0.0, 1.0),
        1.0,  # no claims at PF location → maximally stale
    )

    # Volume at PF ZIP: dominant_claim_share × claim_rows
    claim_rows = result.get("claim_rows", pd.Series(0.0, index=result.index)).fillna(0)
    dom_share = result.get("dominant_claim_share", pd.Series(0.0, index=result.index)).fillna(0)
    volume_at_pf = np.where(is_pf_dominant.fillna(False), dom_share * claim_rows, 0.0)

    result["address_staleness_score"] = np.round(staleness, 4)
    result["staleness_weighted"] = np.round(staleness * np.log1p(volume_at_pf), 4)
    return result


# ── Sprint 1c: Source credibility tiers ───────────────────────────────────────

def _classify_url_tier(url: str) -> int:
    """Return 1, 2, or 3 for a single URL string using patterns from settings.py.

    Tier 1 = government / hospital / health-system owned (high trust)
    Tier 2 = provider-owned pages or group/plan directories (medium trust)
    Tier 3 = consumer aggregators / lead-gen (low trust)
    """
    lower = url.lower()
    # Tier 3 checked first to avoid misclassifying aggregators
    if any(p in lower for p in TIER3_PATTERNS):
        return 3
    if any(p in lower for p in TIER1_PATTERNS):
        return 1
    return 2


def _count_tier1_in_cell(cell_value: object) -> int:
    """Count Tier-1 URLs in a pipe-separated cell."""
    if pd.isna(cell_value):
        return 0
    urls = re.findall(r"https?://[^\s|]+", str(cell_value), flags=re.IGNORECASE)
    return sum(1 for u in urls if _classify_url_tier(u) == 1)


def compute_source_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """Add domain-tier credibility signals from URL evidence columns.

    Pattern lists (TIER1_PATTERNS, TIER3_PATTERNS) come from settings.py.
    Tier 2 is the implicit middle bucket — everything not matched by Tier 1 or Tier 3.

    Args:
        df: DataFrame with the 12 URL evidence columns from URL_EVIDENCE_COLUMNS.

    Returns:
        df with three new columns:
        - tier1_confirmation_count  : Tier-1 URLs in "found" columns (address confirmed)
        - tier1_contradiction_count : Tier-1 URLs in "not_found" columns (address denied)
        - net_tier1_signal          : confirmation - contradiction (signed credibility score)
    """
    result = df.copy()

    found_cols = [c for c in URL_EVIDENCE_COLUMNS if "_found_" in c and "_not_found_" not in c]
    not_found_cols = [c for c in URL_EVIDENCE_COLUMNS if "_not_found_" in c]

    tier1_confirm = sum(
        result[col].map(_count_tier1_in_cell) for col in found_cols if col in result.columns
    )
    tier1_contradict = sum(
        result[col].map(_count_tier1_in_cell) for col in not_found_cols if col in result.columns
    )

    result["tier1_confirmation_count"] = tier1_confirm.astype(int)
    result["tier1_contradiction_count"] = tier1_contradict.astype(int)
    result["net_tier1_signal"] = (tier1_confirm - tier1_contradict).astype(int)
    return result


# ── Core feature engineering ───────────────────────────────────────────────────

def engineer_base_features(base_df: pd.DataFrame) -> pd.DataFrame:
    """Apply all label normalisation, score binning, and evidence feature engineering.

    Args:
        base_df: raw workbook DataFrame from load_base_data().

    Returns:
        DataFrame with all engineered columns appended.
    """
    df = base_df.copy()

    df["R3_Label"] = df["Final_R3_Reco_Address"].map(parse_r3_label)
    df["Web_Label"] = df["Manual_ Address"].map(normalize_validation_label)
    df["Calling_Label"] = df["Calling_Address"].map(normalize_validation_label)
    df["score_band"] = df["Final_R3_Score_Address"].map(score_band)
    df["score_value"] = pd.to_numeric(df["Final_R3_Score_Address"], errors="coerce")
    df["is_low_score"] = df["score_band"].isin({"<=0", "0-25"})
    df["is_mid_score"] = df["score_band"].isin({"25-50", "50-75"})
    df["is_high_score"] = df["score_band"].isin({"75-100"})

    df["Zip_norm"] = df["Zip"].map(normalize_zip)
    df["Phone_norm"] = df["Phone"].map(normalize_phone)
    phone_counts = df["Phone_norm"].value_counts(dropna=False)
    df["phone_shared_count"] = df["Phone_norm"].map(phone_counts).fillna(0).astype(int)

    organization_counts = df["OrganizationName"].fillna("UNKNOWN").astype(str).value_counts()
    df["org_record_count"] = (
        df["OrganizationName"].fillna("UNKNOWN").astype(str).map(organization_counts).fillna(0).astype(int)
    )

    for col in URL_EVIDENCE_COLUMNS:
        df[f"{col}__count"] = df[col].map(count_urls)

    found_cols_count = [f"{c}__count" for c in URL_EVIDENCE_COLUMNS if "_found_" in c and "_not_found_" not in c]
    not_found_cols_count = [f"{c}__count" for c in URL_EVIDENCE_COLUMNS if "_not_found_" in c]

    df["evidence_found_total"] = df[found_cols_count].sum(axis=1)
    df["evidence_not_found_total"] = df[not_found_cols_count].sum(axis=1)
    df["evidence_total"] = df["evidence_found_total"] + df["evidence_not_found_total"]
    df["has_zero_evidence"] = df["evidence_total"].eq(0)

    df["org_found_count"] = (
        df["Address_ProviderView_found_in_websites_URLS_Orgwebsite__count"]
        + df["Address_OrgView_found_in_websites_URLS_Orgwebsite__count"]
    )
    df["provider_found_count"] = (
        df["Address_ProviderView_found_in_websites_URLS_Providerwebsite__count"]
        + df["Address_OrgView_found_in_websites_URLS_Providerwebsite__count"]
    )
    df["aggregator_found_count"] = (
        df["Address_ProviderView_found_in_websites_URLS_Aggregator__count"]
        + df["Address_OrgView_found_in_websites_URLS_Aggregator__count"]
    )
    df["org_conflict_count"] = (
        df["Address_ProviderView_not_found_in_websites_URLS_Orgwebsite__count"]
        + df["Address_OrgView_not_found_in_websites_URLS_Orgwebsite__count"]
    )
    df["provider_conflict_count"] = (
        df["Address_ProviderView_not_found_in_websites_URLS_Providerwebsite__count"]
        + df["Address_OrgView_not_found_in_websites_URLS_Providerwebsite__count"]
    )
    df["aggregator_conflict_count"] = (
        df["Address_ProviderView_not_found_in_websites_URLS_Aggregator__count"]
        + df["Address_OrgView_not_found_in_websites_URLS_Aggregator__count"]
    )

    # Column-structure tier signals (fast, using column name encoding)
    df["net_tier1_signal"] = df["org_found_count"] - df["org_conflict_count"]
    df["net_tier2_signal"] = df["provider_found_count"] - df["provider_conflict_count"]
    df["net_tier3_signal"] = df["aggregator_found_count"] - df["aggregator_conflict_count"]

    df["has_org_found"] = df["org_found_count"].gt(0)
    df["has_provider_found"] = df["provider_found_count"].gt(0)
    df["provider_specificity_gap"] = df["has_org_found"] & ~df["has_provider_found"]
    df["has_org_conflict"] = df["org_conflict_count"].gt(0)
    df["provider_in_org_flag"] = df["Provider_in_Organization"].notna()
    df["org_validation_norm"] = df["Org_Validation"].map(normalize_validation_label)
    df["is_behavioral_health"] = df["Specialty"].map(is_behavioral_health)

    comments = df["Comment_Call_QC"].fillna("").astype(str).str.upper()
    for key, pattern in COMMENT_PATTERNS.items():
        df[f"call_keyword_{key}"] = comments.str.contains(pattern, regex=True, na=False)

    df["agreement_zone"] = df["R3_Label"] == df["Calling_Label"]
    df["r3_wrong"] = df["R3_Label"] != df["Calling_Label"]
    df["pf_address_accurate"] = df["Calling_Label"] == "ACCURATE"
    df["conclusive_call"] = df["Calling_Label"].isin(CONCLUSIVE_LABELS)

    # Sprint 1a: org consensus anchor
    df = compute_org_consensus(df)

    # Sprint 1c: domain-tier URL signals (richer than column-structure counts)
    df = compute_source_tiers(df)

    return df


def merge_claim_features(base_features: pd.DataFrame, claims_agg: pd.DataFrame) -> pd.DataFrame:
    """Merge per-NPI claims aggregates into the base feature table and derive location features.

    Args:
        base_features: output of engineer_base_features().
        claims_agg: output of aggregate_claims_for_base().

    Returns:
        Merged DataFrame with claims location, recency, and multi-location columns.
    """
    claims = claims_agg.copy()
    claims["OrigNPI"] = pd.to_numeric(claims["OrigNPI"], errors="coerce")

    merged = base_features.copy()
    merged["OrigNPI"] = pd.to_numeric(merged["OrigNPI"], errors="coerce")
    merged = merged.merge(claims, on="OrigNPI", how="left")

    merged["has_claims"] = merged["claim_rows"].notna()
    for col in ["latest_dos", "dominant_claim_latest_dos", "secondary_claim_latest_dos"]:
        if col in merged.columns:
            merged[col] = pd.to_datetime(merged[col], errors="coerce")

    merged["claims_zip_match"] = merged["has_claims"] & (merged["Zip_norm"] == merged["claims_zip"])
    merged["claims_state_match"] = merged["has_claims"] & (
        merged["State"].fillna("").astype(str) == merged["claims_state"].fillna("").astype(str)
    )
    merged["dominant_claims_zip_match"] = merged["has_claims"] & (
        merged["Zip_norm"] == merged["dominant_claims_zip"]
    )
    merged["secondary_claims_zip_match"] = merged["has_claims"] & (
        merged["Zip_norm"] == merged["secondary_claims_zip"]
    )
    merged["dominant_claims_state_match"] = merged["has_claims"] & (
        merged["State"].fillna("").astype(str) == merged["dominant_claims_state"].fillna("").astype(str)
    )
    merged["hco_zip_match"] = merged["Zip_norm"] == merged["hco_zip_5"]

    latest_claim_date = merged["latest_dos"].max()
    if pd.isna(latest_claim_date):
        merged["days_since_latest_claim"] = pd.NA
        merged["days_since_dominant_claim"] = pd.NA
        merged["days_since_secondary_claim"] = pd.NA
    else:
        merged["days_since_latest_claim"] = (latest_claim_date - merged["latest_dos"]).dt.days
        merged["days_since_dominant_claim"] = (latest_claim_date - merged["dominant_claim_latest_dos"]).dt.days
        merged["days_since_secondary_claim"] = (latest_claim_date - merged["secondary_claim_latest_dos"]).dt.days

    merged["recent_claim_90d"] = merged["days_since_latest_claim"].le(90).fillna(False)
    merged["recent_claim_180d"] = merged["days_since_latest_claim"].le(180).fillna(False)
    merged["recent_claim_365d"] = merged["days_since_latest_claim"].le(365).fillna(False)
    merged["dominant_claim_recent_90d"] = merged["days_since_dominant_claim"].le(90).fillna(False)
    merged["secondary_claim_recent_180d"] = merged["days_since_secondary_claim"].le(180).fillna(False)
    merged["claims_zip_mismatch"] = merged["has_claims"] & ~merged["claims_zip_match"]
    merged["claims_state_mismatch"] = merged["has_claims"] & ~merged["claims_state_match"]

    merged["pf_location_match"] = "no_claims"
    merged.loc[merged["has_claims"], "pf_location_match"] = "absent_from_claims"
    merged.loc[merged["dominant_claims_zip_match"], "pf_location_match"] = "dominant_match"
    merged.loc[
        merged["secondary_claims_zip_match"] & ~merged["dominant_claims_zip_match"],
        "pf_location_match",
    ] = "secondary_match"

    merged["multi_location_claims"] = merged["n_claim_zip_locations"].fillna(0).ge(2)
    merged["high_location_entropy"] = merged["claims_location_entropy"].fillna(0).ge(1.0)
    merged["claims_location_profile"] = "single_site"
    merged.loc[merged["multi_location_claims"], "claims_location_profile"] = "multi_site"
    merged.loc[
        merged["multi_location_claims"] & merged["high_location_entropy"],
        "claims_location_profile",
    ] = "diffuse_multi_site"
    merged.loc[
        merged["multi_location_claims"] & merged["dominant_claim_share"].fillna(0).ge(0.7),
        "claims_location_profile",
    ] = "dominant_plus_satellite"

    merged["claim_activity_bucket"] = pd.cut(
        merged["claim_rows"].fillna(0),
        bins=[-1, 0, 5, 25, 100, float("inf")],
        labels=["0", "1-5", "6-25", "26-100", "100+"],
    ).astype(str)
    merged["org_size_bucket"] = pd.cut(
        merged["org_record_count"].fillna(0),
        bins=[-1, 1, 5, 20, 100, float("inf")],
        labels=["1", "2-5", "6-20", "21-100", "100+"],
    ).astype(str)
    merged["phone_share_bucket"] = pd.cut(
        merged["phone_shared_count"].fillna(0),
        bins=[-1, 0, 1, 5, 20, float("inf")],
        labels=["0", "1", "2-5", "6-20", "20+"],
    ).astype(str)

    # Sprint 1b: continuous staleness score (uses half-life from settings)
    merged = compute_staleness(merged)

    return merged


def build_feature_table(
    base_path: Path | str = BASE_DATA_FILE,
    claims_path: Path | str = CLAIMS_DATA_FILE,
    cache_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Build the full feature table, optionally reading from a parquet cache.

    Args:
        base_path: path to the base workbook.
        claims_path: path to the claims workbook.
        cache_dir: directory for parquet caching. None = no cache.

    Returns:
        Fully engineered feature DataFrame.
    """
    base_path = Path(base_path)
    claims_path = Path(claims_path)

    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "feature_table.parquet"
        mtime_file = cache_dir / "feature_table_mtimes.json"

        current_mtimes = {
            "base": base_path.stat().st_mtime if base_path.exists() else 0.0,
            "claims": claims_path.stat().st_mtime if claims_path.exists() else 0.0,
            "nppes": Path(NPPES_DATA_FILE).stat().st_mtime if Path(NPPES_DATA_FILE).exists() else 0.0,
        }

        if cache_file.exists() and mtime_file.exists():
            try:
                saved = json.loads(mtime_file.read_text())
                if saved == current_mtimes:
                    return pd.read_parquet(cache_file)
            except Exception:
                pass

        df = _build_feature_table_uncached(base_path, claims_path)
        try:
            df.to_parquet(cache_file, index=False)
            mtime_file.write_text(json.dumps(current_mtimes))
        except Exception:
            pass
        return df

    return _build_feature_table_uncached(base_path, claims_path)


def _build_feature_table_uncached(base_path: Path, claims_path: Path) -> pd.DataFrame:
    base_df = load_base_data(base_path)
    base_features = engineer_base_features(base_df)
    claims_agg = aggregate_claims_for_base(base_df, claims_path)
    merged = merge_claim_features(base_features, claims_agg)

    npi_source = merged["NPI"] if "NPI" in merged.columns else merged["OrigNPI"]
    npi_universe = (
        pd.Series(npi_source)
        .dropna()
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .unique()
        .tolist()
    )
    nppes_df = load_nppes_extract(npi_universe=npi_universe)
    return merge_nppes_features(merged, nppes_df)
