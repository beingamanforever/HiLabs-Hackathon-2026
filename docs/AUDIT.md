# Audit

## Scope

This audit reviews the current implementation of:

- Track 1 analysis pipeline
- Track 2 passive relabeling pipeline
- Track 3 robocall triage pipeline

Reviewed files:

- [src/r3hackathon/data.py](/Users/aman/Desktop/Hackathon/src/r3hackathon/data.py)
- [src/r3hackathon/features.py](/Users/aman/Desktop/Hackathon/src/r3hackathon/features.py)
- [src/r3hackathon/track1.py](/Users/aman/Desktop/Hackathon/src/r3hackathon/track1.py)
- [src/r3hackathon/track2.py](/Users/aman/Desktop/Hackathon/src/r3hackathon/track2.py)
- [src/r3hackathon/track3.py](/Users/aman/Desktop/Hackathon/src/r3hackathon/track3.py)

## What Is Good

- The code is correctly split into data loading, feature engineering, Track 1, and Track 2.
- The claims workbook is processed in streamed read-only mode, which is appropriate for a 399k-row `.xlsx`.
- Track 2 respects the problem statement’s main constraint: the current CV run shows `0` agreement-zone changes.
- The passive rules are now high precision and measurable, rather than broad heuristic flips.
- Track 1 and Track 2 both run end to end and write reproducible artifacts.
- Track 3 now ranks unresolved rows after passive correction and respects the official 450-call / 40%-usable-verdict framing.

## Findings

### 1. State-based flipping is effective but brittle

Severity: Medium

The strongest Track 2 rule, `geo_cluster_low_signal_flip`, depends on high-risk states learned from the current training data: `AL`, `MI`, and `NJ`.

Why this matters:

- It works well on the current dataset.
- It may not transfer cleanly to the hidden validation set.
- The model may be learning dataset-specific operational issues instead of stable provider-data behavior.

Current evidence:

- This rule is the largest positive contributor in the current passive engine.
- It also carries the highest overfitting risk.

Recommendation:

- Replace raw state membership with a more general cluster score using org size, specialty family, score band, evidence pattern, and claims presence.
- Keep state as a weak feature, not a primary flip gate.

### 2. Claims are over-compressed to one provider-level summary

Severity: Medium

`aggregate_claims_for_base()` collapses all claims for an NPI into one modal ZIP/state plus a latest DOS. That is simple and fast, but it loses multi-location behavior.

Why this matters:

- Providers can bill across multiple sites.
- The mode ZIP may hide relocation, split practice, or hospital-system rotation.
- The hackathon prompt explicitly points toward multi-location and temporal effects.

Recommendation:

- Aggregate claims by `(OrigNPI, ZIP, STATE)` and keep top location clusters.
- Add location share, latest DOS per location, and location entropy features.
- Score whether the PF location is the active dominant location, a secondary location, or absent.

### 3. Track 2 currently only flips toward `ACCURATE`

Severity: Low to Medium

This is a deliberate safety choice, but it leaves some real opportunity unused in the `R3=ACCURATE / Call=INACCURATE` bucket.

Why this matters:

- The dataset contains a meaningful stale-org-site failure mode.
- Current logic only flags these rows as `triage_candidate`.
- That is safe, but passive lift remains limited.

Recommendation:

- Keep passive `ACCURATE -> INACCURATE` rules separate and even stricter.
- Require multiple independent contradictions:
  - strong org-site signature
  - no matching claims at PF location
  - active claims at different location cluster
  - maybe recent org/HCO address mismatch

### 4. Feature-table rebuild cost is high

Severity: Low

Track 1 and Track 2 each rebuild the same feature table from scratch, including the claims aggregation pass.

Why this matters:

- Iteration is slow.
- It makes experimentation more expensive during the hackathon.

Recommendation:

- Add a cached feature artifact, for example:
  - `outputs/cache/feature_table.parquet`
  - `outputs/cache/claims_agg.parquet`
- Recompute only when source workbook timestamps change.

### 5. Track 1 taxonomy is useful but still heuristic

Severity: Low

The taxonomy in `assign_taxonomy()` is a practical first cut, but it is a rule stack, not a learned segmentation model.

Why this matters:

- Order effects can change bucket assignment.
- Some rows fit multiple archetypes.
- Presentation-wise this is fine, but analytically it can be improved.

Recommendation:

- Add a secondary “reason flags” layer so a row can carry multiple archetype tags.
- Keep one primary bucket for deck simplicity, but preserve multi-label detail for analysis.

## Metrics Verified

From the current checked-in outputs:

- Track 1:
  - rows: `2493`
  - R3 vs Web QC agreement: `79.86%`
  - R3 vs Call QC agreement: `50.62%`

- Track 2 grouped CV:
  - baseline accuracy: `50.62%`
  - corrected accuracy: `53.07%`
  - net gain: `+2.45%`
  - agreement-zone changes: `0`
  - changed-row precision: `93.85%`

- Track 3 simulation:
  - selected rows: `450`
  - expected usable verdicts: `180`
  - expected accuracy gain from calling: `+5.85%`
  - expected combined accuracy after Track 2 + Track 3: `58.91%`

## How To Make This Pipeline Better

### Priority 1

Harden Track 3:

- add more robust calibration for `p_conclusive_rank`
- test alternative business-gain definitions
- run ablations on the triage score components
Track 3 is now implemented, so the next step is improving its generalization and calibration.

### Priority 2

Upgrade claims from provider-level summary to location-aware history:

- top ZIP clusters per NPI
- recency per ZIP cluster
- dominant ZIP share
- whether PF ZIP is dominant, secondary, or absent
- telehealth-heavy vs site-specific profile

This is likely the highest-value Track 2 improvement.

### Priority 3

Replace the current state heuristic with a learned cluster feature:

- organization cluster
- specialty family
- evidence pattern
- claims presence / absence
- low-score signature

That should reduce holdout fragility.

### Priority 4

Add better negative-evidence modeling:

- not just whether provider/organization pages were found
- but whether the “found different address” evidence is concentrated in org sites, provider sites, or aggregators
- whether contradiction is repeated across multiple domains

This should improve stale-web detection.

### Priority 5

Add cache + experiment harness:

- cached feature table
- threshold sweep notebook/script
- ablation tests by rule and by feature family
- grouped CV by org and by NPI

This will make iteration much faster and help defend the final presentation.

## Recommended Next Build

If continuing from here, I would do:

1. `src/r3hackathon/track3.py`
2. cached claims aggregation
3. location-aware claims clustering
4. threshold sweep / ablation report
5. inference wrapper and Docker API
