# Track 1 Summary

## Overview
- Total rows analyzed: 2493
- R3 vs Web QC agreement: 79.86%
- R3 vs Call QC agreement: 50.62%
- Total disagreement rows: 1231
- False inaccurate rows: 465
- False accurate rows: 276

## Primary Taxonomy
- behavioral_health_telehealth_floater: 403 rows, median R3 score 0.00, claims ZIP match rate 11.91%
- false_inaccurate_no_reliable_web_evidence: 384 rows, median R3 score 0.00, claims ZIP match rate 8.07%
- false_accurate_stale_org_site: 198 rows, median R3 score 95.12, claims ZIP match rate 10.10%
- mid_score_ambiguity: 166 rows, median R3 score 42.86, claims ZIP match rate 13.25%
- large_org_multi_location_confusion: 44 rows, median R3 score 64.00, claims ZIP match rate 29.55%

## Highest-Risk States
- AL: 114 rows, disagreement rate 93.86%
- MI: 231 rows, disagreement rate 77.92%
- IN: 15 rows, disagreement rate 73.33%
- NJ: 176 rows, disagreement rate 72.16%
- VA: 13 rows, disagreement rate 61.54%
- CA: 104 rows, disagreement rate 55.77%
- IL: 44 rows, disagreement rate 54.55%
- MD: 15 rows, disagreement rate 53.33%
- MA: 54 rows, disagreement rate 51.85%
- CO: 27 rows, disagreement rate 51.85%

## Highest-Risk Specialties
- SURGERY PHYSICIAN (208600000X): 18 rows, disagreement rate 100.00%
- CLINICAL PSYCHOLOGIST (103TC0700X): 12 rows, disagreement rate 100.00%
- GASTROENTEROLOGY PHYSICIAN (207RG0100X): 12 rows, disagreement rate 100.00%
- CRITICAL CARE MEDICINE (INTERNAL MEDICINE) PHYSICIAN (207RC0200X): 10 rows, disagreement rate 100.00%
- PEDIATRICS PHYSICIAN (208000000X): 45 rows, disagreement rate 97.78%
- OBSTETRICS & GYNECOLOGY PHYSICIAN (207V00000X): 35 rows, disagreement rate 97.14%
- CARDIOVASCULAR DISEASE PHYSICIAN (207RC0000X): 33 rows, disagreement rate 96.97%
- INTERNAL MEDICINE PHYSICIAN (207R00000X): 69 rows, disagreement rate 95.65%
- NEPHROLOGY PHYSICIAN (207RN0300X): 16 rows, disagreement rate 93.75%
- CLINICAL SOCIAL WORKER (1041C0700X): 31 rows, disagreement rate 87.10%

## Notes
- Call QC comments are used here for discovery and taxonomy only.
- This output is deck-ready and should feed Track 2 feature design, not holdout inference.
