"""Sprint 4 — NPPES bulk data enrichment.

Streams the NPPES bulk provider file, filters to the NPI universe in the base
workbook, caches to Parquet, and merges three corroborating features:
  - nppes_zip_match   : PF ZIP agrees with NPPES practice-location ZIP
  - nppes_state_match : PF state agrees with NPPES state
  - nppes_active      : provider has no NPI deactivation date
  - triple_mismatch   : PF ≠ NPPES AND PF absent/secondary from claims AND active

If the NPPES bulk CSV is not present the functions log a warning and return
None / the unchanged DataFrame so the rest of the pipeline is unaffected.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Collection

import pandas as pd

from .settings import CACHE_DIR, NPPES_COLUMN_MAP, NPPES_DATA_FILE

logger = logging.getLogger(__name__)

# ZIPs / states absent from dominant claims matches
_ABSENT_LOCATION_VALUES = {"absent_from_claims", "secondary_match", "no_claims"}


def load_nppes_extract(
    npi_universe: Collection[str],
    cache_path: Path | None = None,
    source_path: Path | None = None,
) -> pd.DataFrame | None:
    """Stream the NPPES bulk CSV and return a filtered DataFrame.

    Only rows whose NPI is in *npi_universe* are retained.
    The result is cached at *cache_path* as Parquet for fast re-use.

    Args:
        npi_universe: iterable of NPI strings to keep.
        cache_path: where to write / read the Parquet cache.
                    Defaults to CACHE_DIR / "nppes_extract.parquet".
        source_path: path to the NPPES bulk CSV file.
                     Defaults to settings.NPPES_DATA_FILE.

    Returns:
        DataFrame with columns NPI, nppes_address, nppes_zip5,
        nppes_state, nppes_active, or None if the source file is absent.
    """
    if cache_path is None:
        cache_path = Path(CACHE_DIR) / "nppes_extract.parquet"
    if source_path is None:
        source_path = Path(NPPES_DATA_FILE)

    if cache_path.exists():
        logger.info("Loading NPPES extract from cache: %s", cache_path)
        return pd.read_parquet(cache_path)

    if not source_path.exists():
        logger.warning(
            "NPPES bulk file not found at %s — skipping NPPES enrichment. "
            "Download npidata_pfile.csv from https://download.cms.gov/nppes/NPI_Files.html "
            "and place it at that path to enable this feature.",
            source_path,
        )
        return None

    logger.info("Streaming NPPES bulk file from %s (this may take a few minutes)", source_path)
    npi_set = {str(n) for n in npi_universe}

    required_cols = list(NPPES_COLUMN_MAP.keys())
    chunks = pd.read_csv(
        source_path,
        usecols=required_cols,
        chunksize=50_000,
        dtype=str,
        low_memory=False,
    )
    filtered_parts: list[pd.DataFrame] = []
    for chunk in chunks:
        mask = chunk["NPI"].isin(npi_set)
        if mask.any():
            filtered_parts.append(chunk[mask].rename(columns=NPPES_COLUMN_MAP))

    if not filtered_parts:
        logger.warning("No matching NPIs found in NPPES file — enrichment will be empty.")
        return pd.DataFrame(columns=["NPI", "nppes_address", "nppes_zip5", "nppes_state", "nppes_active"])

    filtered = pd.concat(filtered_parts, ignore_index=True)
    filtered["nppes_zip5"] = filtered["nppes_zip_raw"].str[:5]
    filtered["nppes_active"] = filtered["nppes_deactivation_date"].isna().astype(int)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        filtered.to_parquet(cache_path, index=False)
        logger.info("NPPES extract cached to %s (%d rows)", cache_path, len(filtered))
    except Exception as exc:
        logger.warning("Could not cache NPPES extract: %s", exc)

    return filtered


def merge_nppes_features(
    base_df: pd.DataFrame,
    nppes_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Merge NPPES enrichment columns into the feature table.

    If *nppes_df* is None (NPPES file absent) the base DataFrame is returned
    unchanged so the rest of the pipeline continues without NPPES features.

    Args:
        base_df: fully engineered feature table (must have NPI, Zip_norm, State,
                 and pf_location_match columns).
        nppes_df: output of load_nppes_extract(), or None.

    Returns:
        base_df with up to four new columns:
        - nppes_zip_match    : 1 if PF ZIP == NPPES ZIP, else 0
        - nppes_state_match  : 1 if PF state == NPPES state, else 0
        - nppes_active       : 1 if provider has no NPPES deactivation date
        - triple_mismatch    : PF ≠ NPPES AND PF absent/secondary from claims AND active
    """
    if nppes_df is None or nppes_df.empty:
        logger.info("Skipping NPPES merge — no enrichment data available.")
        return base_df

    merged = base_df.merge(
        nppes_df[["NPI", "nppes_zip5", "nppes_state", "nppes_active"]].drop_duplicates("NPI"),
        on="NPI",
        how="left",
    )

    merged["nppes_zip_match"] = (
        merged["Zip_norm"].fillna("") == merged["nppes_zip5"].fillna("")
    ).astype(int)
    merged["nppes_state_match"] = (
        merged["State"].fillna("").astype(str) == merged["nppes_state"].fillna("").astype(str)
    ).astype(int)
    merged["nppes_active"] = merged["nppes_active"].fillna(0).astype(int)

    # Triple mismatch: PF differs from federal registry AND is not the dominant
    # claims location AND provider is still listed as active — strong signal of stale data
    pf_not_in_dominant = merged["pf_location_match"].isin(_ABSENT_LOCATION_VALUES)
    merged["triple_mismatch"] = (
        (merged["nppes_zip_match"] == 0)
        & pf_not_in_dominant
        & (merged["nppes_active"] == 1)
    ).astype(int)

    logger.info(
        "NPPES merge complete: %d rows with nppes_zip_match, %d triple_mismatch rows",
        merged["nppes_zip_match"].sum(),
        merged["triple_mismatch"].sum(),
    )
    return merged
