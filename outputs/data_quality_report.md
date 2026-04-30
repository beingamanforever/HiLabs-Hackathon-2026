# Data Quality Report

_Generated from `Base data_hackathon.xlsx` and `Claims data_Hackathon.xlsx`_

## Dataset Summary

- **Total provider records**: 2,493
- **Unique organizations**: 846
- **Unique NPIs**: 1,949
- **Unique states**: 52
- **Date range covered (claims)**: latest claim signal embedded as `recent_claim_*` flags

## Label Distributions

### R3_Label
- INACCURATE: 1,673 (67.1%)
- ACCURATE: 517 (20.7%)
- INCONCLUSIVE: 303 (12.2%)

### Web_Label
- INACCURATE: 1,861 (74.6%)
- ACCURATE: 632 (25.4%)

### Calling_Label
- INACCURATE: 1,481 (59.4%)
- ACCURATE: 765 (30.7%)
- INCONCLUSIVE: 247 (9.9%)

## Inter-Rater Agreement

- R3 vs Calling QC: **50.62%** (this is the gap we close)
- R3 vs Web QC:    **79.86%**
- Web vs Calling QC: **57.76%**

## Missingness (key fields)

- `Final_R3_Score_Address`: 0 missing (0.0%)
- `Phone`: 0 missing (0.0%)
- `City`: 0 missing (0.0%)
- `State`: 0 missing (0.0%)
- `Zip`: 0 missing (0.0%)

## Claims Coverage

- Records with any claim: **1,632** (65.5%)
- Records with claim ≤180d: **1,632**
- Records with claim ≤90d: **1,623**
- Claims ZIP matches profile ZIP: **276**
- Claims ZIP mismatches profile ZIP: **1,356**

## Risk Segments

- Behavioral health: **779**
- Telehealth flag: **617**

## Score-Band Distribution (R3 score)

- 0-25: 421
- 25-50: 93
- 50-75: 142
- 75-100: 516
- <=0: 1,321

## Known Quality Issues

- Some `Phone` values are shared by ≥3 providers (`phone_shared_count` flag) — used for risk weighting.
- A small set of organization names contain trailing whitespace — handled via `.str.strip()` upstream.
- Claim-line ZIPs occasionally lack the +4 extension — we collapse to 5-digit ZIP for matching.
- Missing state values are imputed only when claims also have a state; otherwise flagged.

## Anonymization Status

- This dataset contains **no protected health information (PHI)**: no patient identifiers, no diagnoses linked to individual patients.
- Provider NPIs are public via the NPPES registry (CMS).
- Organization names and addresses are publicly listed in the NPPES registry.
- **No external API calls were made with raw row data** during model training.

## External Data Sources Used

- **NPPES (NPI registry)** — CMS public bulk file (`npidata_pfile.csv`). Optional — pipeline runs without it.
- No proprietary payer datasets were consulted.
- **No external API calls** were used during training or inference.
