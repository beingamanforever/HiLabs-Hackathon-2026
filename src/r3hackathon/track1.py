from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .features import build_feature_table
from .settings import CACHE_DIR


# Per-archetype resolution strategy. The PS requires that "each segment should
# suggest a different resolution strategy" — these sentences map every disagreement
# pattern to a concrete downstream action (Track 2 passive flip, Track 3 robocall,
# or hold-out for manual review).
TAXONOMY_RESOLUTION_STRATEGY: dict[str, str] = {
    "false_inaccurate_no_reliable_web_evidence": (
        "Track 2 passive flip — INACCURATE→ACCURATE under conformal org-consensus gate; "
        "no robocall needed because the web evidence is the failure mode, not the address."
    ),
    "false_accurate_stale_org_site": (
        "Track 3 robocall — high-yield outreach segment; conclusivity ≈85%, business gain "
        "high (large org, multi-location, stale website) so the call repays its $0.50 cost."
    ),
    "mid_score_ambiguity": (
        "Track 2 provider-signal mid-score flip when claims state matches and provider "
        "evidence exists; otherwise route to Track 3 with mid-priority budget weight."
    ),
    "behavioral_health_telehealth_floater": (
        "Do not robocall — telehealth providers have no answerable phone line, so "
        "conclusivity falls below 40%. Hold for registry/NPPES lookup or manual review."
    ),
    "large_org_multi_location_confusion": (
        "Track 3 robocall — multi-location org targets are the highest business-gain "
        "segment; rank by org_record_count × address_staleness_score."
    ),
    "other_disagreement": (
        "Track 3 robocall as fallback when budget allows; flag for next R3 retraining "
        "cycle so the pattern can be modelled directly."
    ),
}


def assign_taxonomy(row: pd.Series) -> str:
    if not bool(row["r3_wrong"]):
        return "agreement_zone"

    if row["is_behavioral_health"] and (
        bool(row["telehealth_flag"]) or row["Calling_Label"] == "INCONCLUSIVE"
    ):
        return "behavioral_health_telehealth_floater"

    if (
        row["R3_Label"] == "INACCURATE"
        and row["Calling_Label"] == "ACCURATE"
        and (row["is_low_score"] or row["has_zero_evidence"] or row["evidence_found_total"] == 0)
    ):
        return "false_inaccurate_no_reliable_web_evidence"

    if (
        row["R3_Label"] == "ACCURATE"
        and row["Calling_Label"] == "INACCURATE"
        and row["is_high_score"]
        and row["has_org_found"]
    ):
        return "false_accurate_stale_org_site"

    if row["org_record_count"] >= 10 and (row["has_org_found"] or row["has_org_conflict"]):
        return "large_org_multi_location_confusion"

    if row["R3_Label"] == "INCONCLUSIVE" or row["is_mid_score"]:
        return "mid_score_ambiguity"

    return "other_disagreement"


def build_track1_outputs(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    working = df.copy()
    working["taxonomy"] = working.apply(assign_taxonomy, axis=1)
    disagreements = working[working["r3_wrong"]].copy()

    confusion = pd.crosstab(working["R3_Label"], working["Calling_Label"])
    score_band_summary = (
        working.groupby("score_band", observed=False)
        .agg(
            rows=("Row ID", "count"),
            disagreement_rate=("r3_wrong", "mean"),
            conclusive_rate=("conclusive_call", "mean"),
            median_r3_score=("score_value", "median"),
        )
        .reset_index()
        .sort_values("score_band")
    )
    state_summary = (
        working.groupby("State", observed=False)
        .agg(rows=("Row ID", "count"), disagreement_rate=("r3_wrong", "mean"))
        .query("rows >= 10")
        .sort_values(["disagreement_rate", "rows"], ascending=[False, False])
        .reset_index()
    )
    specialty_summary = (
        working.groupby("Specialty", observed=False)
        .agg(rows=("Row ID", "count"), disagreement_rate=("r3_wrong", "mean"))
        .query("rows >= 10")
        .sort_values(["disagreement_rate", "rows"], ascending=[False, False])
        .reset_index()
    )
    org_summary = (
        disagreements.groupby("OrganizationName", observed=False)
        .agg(
            disagreement_rows=("Row ID", "count"),
            median_r3_score=("score_value", "median"),
            accurate_call_rate=("pf_address_accurate", "mean"),
        )
        .sort_values(["disagreement_rows", "median_r3_score"], ascending=[False, False])
        .head(30)
        .reset_index()
    )
    taxonomy_summary = (
        disagreements.groupby("taxonomy", observed=False)
        .agg(
            rows=("Row ID", "count"),
            median_r3_score=("score_value", "median"),
            claims_zip_match_rate=("claims_zip_match", "mean"),
            telehealth_rate=("telehealth_flag", "mean"),
        )
        .sort_values("rows", ascending=False)
        .reset_index()
    )
    taxonomy_summary["resolution_strategy"] = taxonomy_summary["taxonomy"].map(
        TAXONOMY_RESOLUTION_STRATEGY
    ).fillna("Route to Track 3 robocall queue if business gain justifies the call.")

    keyword_cols = [column for column in working.columns if column.startswith("call_keyword_")]
    keyword_summary = pd.DataFrame(
        [
            {
                "keyword": column.replace("call_keyword_", ""),
                "rows_flagged": int(working[column].sum()),
                "disagreement_rate_when_flagged": float(working.loc[working[column], "r3_wrong"].mean())
                if working[column].any()
                else 0.0,
            }
            for column in keyword_cols
        ]
    ).sort_values("rows_flagged", ascending=False)

    overview = pd.DataFrame(
        [
            {"metric": "total_rows", "value": int(len(working))},
            {"metric": "r3_vs_web_agreement", "value": float((working["R3_Label"] == working["Web_Label"]).mean())},
            {
                "metric": "r3_vs_call_agreement",
                "value": float((working["R3_Label"] == working["Calling_Label"]).mean()),
            },
            {"metric": "disagreement_rows", "value": int(working["r3_wrong"].sum())},
            {
                "metric": "false_inaccurate_rows",
                "value": int(
                    ((working["R3_Label"] == "INACCURATE") & (working["Calling_Label"] == "ACCURATE")).sum()
                ),
            },
            {
                "metric": "false_accurate_rows",
                "value": int(
                    ((working["R3_Label"] == "ACCURATE") & (working["Calling_Label"] == "INACCURATE")).sum()
                ),
            },
        ]
    )

    return {
        "feature_table": working,
        "disagreement_taxonomy": disagreements,
        "overview": overview,
        "confusion_matrix": confusion,
        "score_band_summary": score_band_summary,
        "state_summary": state_summary,
        "specialty_summary": specialty_summary,
        "org_summary": org_summary,
        "taxonomy_summary": taxonomy_summary,
        "keyword_summary": keyword_summary,
    }


def build_track1_markdown(outputs: dict[str, pd.DataFrame]) -> str:
    overview = outputs["overview"].set_index("metric")["value"].to_dict()
    taxonomy = outputs["taxonomy_summary"].head(5)
    states = outputs["state_summary"].head(10)
    specialties = outputs["specialty_summary"].head(10)

    lines = [
        "# Track 1 Summary",
        "",
        "## Overview",
        f"- Total rows analyzed: {int(overview['total_rows'])}",
        f"- R3 vs Web QC agreement: {overview['r3_vs_web_agreement']:.2%}",
        f"- R3 vs Call QC agreement: {overview['r3_vs_call_agreement']:.2%}",
        f"- Total disagreement rows: {int(overview['disagreement_rows'])}",
        f"- False inaccurate rows: {int(overview['false_inaccurate_rows'])}",
        f"- False accurate rows: {int(overview['false_accurate_rows'])}",
        "",
        "## Primary Taxonomy",
    ]

    for row in taxonomy.itertuples(index=False):
        lines.append(
            f"- {row.taxonomy}: {row.rows} rows, median R3 score {row.median_r3_score:.2f}, "
            f"claims ZIP match rate {row.claims_zip_match_rate:.2%}"
        )

    lines.extend(["", "## Highest-Risk States"])
    for row in states.itertuples(index=False):
        lines.append(f"- {row.State}: {row.rows} rows, disagreement rate {row.disagreement_rate:.2%}")

    lines.extend(["", "## Highest-Risk Specialties"])
    for row in specialties.itertuples(index=False):
        lines.append(f"- {row.Specialty}: {row.rows} rows, disagreement rate {row.disagreement_rate:.2%}")

    lines.extend(
        [
            "",
            "## Notes",
            "- Call QC comments are used here for discovery and taxonomy only.",
            "- This output is deck-ready and should feed Track 2 feature design, not holdout inference.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_track1(output_dir: Path) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_table = build_feature_table(cache_dir=CACHE_DIR)
    outputs = build_track1_outputs(feature_table)

    for name, data in outputs.items():
        if name == "feature_table":
            data.to_csv(output_dir / "track1_feature_table.csv", index=False)
            continue
        path = output_dir / f"{name}.csv"
        data.to_csv(path, index=True if name == "confusion_matrix" else False)

    summary_markdown = build_track1_markdown(outputs)
    (output_dir / "track1_summary.md").write_text(summary_markdown, encoding="utf-8")

    metrics = outputs["overview"].set_index("metric")["value"].to_dict()
    (output_dir / "track1_overview.json").write_text(
        json.dumps(metrics, indent=2, default=str),
        encoding="utf-8",
    )
    return outputs
