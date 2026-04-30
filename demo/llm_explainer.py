"""Tiny LLM-powered triage explainer using OpenRouter + DeepSeek V3.1.

Cost is ~$0.0001 per call (negligible). Cached so repeated explanations
don't re-spend.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests

# ── Config ─────────────────────────────────────────────────────────────────────
DEFAULT_KEY = (
    "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"
)
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", DEFAULT_KEY)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Cheap, capable open model — ~$0.27/M prompt, ~$1.10/M completion (V3.1)
PRIMARY_MODEL  = "deepseek/deepseek-chat-v3.1"
FALLBACK_MODEL = "deepseek/deepseek-chat"

# ── Prompts ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a healthcare data analyst at HiLabs explaining why a provider directory record needs active phone-call verification (a robocall).

CONTEXT (assume the reader already knows this):
- Provider directories list physicians and where they practice. They go stale fast.
- R3 is an automated address-accuracy scoring system that classifies each row as ACCURATE / INACCURATE / INCONCLUSIVE.
- Calling QC is the human ground truth from a survey team that phones the provider.
- R3 vs Calling QC agreement is only ~50% — that gap is what we're closing.
- "PF" = the address printed on the plan-file (the directory).
- The system has 3 layers: Track 1 (discovery), Track 2 (passive flips), Track 3 (active robocalls).
- This is a Track 3 triage row — we're choosing whom to call within a hard 450-call budget.

INPUT FIELDS (provided in user message):
- Provider org name and state
- p_r3_wrong: model's probability that R3's label is wrong (0–1)
- p_conclusive_rank: probability a robocall returns a useful verdict (0–1)
- business_gain: relative business value weight
- triage_reason_codes: pipe-delimited signals — examples and meanings:
   • pf_absent_from_claims  → no recent claim activity at the listed address
   • pf_minority_in_claims  → listed address is a minority of provider's claim ZIPs
   • mid_score_band         → R3 score is in the ambiguous 40–65 range
   • org_provider_gap       → provider's billing pattern diverges from org cluster
   • telehealth             → high telehealth activity; physical address unreliable
   • behavioral_health      → behavioral-health risk segment
   • stale_org_signature    → org website looks stale relative to claims
   • provider_page_signal   → provider-page web evidence contradicts plan-file
   • claims_state_match     → claims state matches plan-file state

OUTPUT REQUIREMENTS:
1. Output exactly TWO short lines, no headers, no bullet points.
2. Line 1 starts with "Call because:" and names the 1–2 strongest signals in plain English (max 25 words). Reference the provider by name only if it adds clarity.
3. Line 2 starts with "Expected outcome:" and states what the call will likely confirm or fix in concrete terms (max 20 words).
4. Use specific numbers ONLY when they materially help the reader (e.g. "95% confidence" if pwrong > 0.9). Otherwise omit them.
5. Be confident but conservative. No marketing language. No emojis. No exclamation marks.
"""


def build_user_prompt(row: dict[str, Any]) -> str:
    return (
        f"Provider: {row.get('org', 'unknown')} ({row.get('state', '??')})\n"
        f"P(R3 wrong) = {row.get('pwrong', 0):.0%}\n"
        f"P(useful call) = {row.get('pconc', 0):.0%}\n"
        f"Business gain = {row.get('bgain', 0):.2f}\n"
        f"Address staleness = {row.get('stale', 0):.2f}\n"
        f"Triage reason codes: {row.get('codes', '(none)')}"
    )


# ── API call ───────────────────────────────────────────────────────────────────

def _call_openrouter(model: str, system: str, user: str,
                     timeout: int = 12, max_tokens: int = 90) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hilabs.com",
        "X-Title": "R3 Hackathon Triage Demo",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    r = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


def explain_row(row: dict[str, Any]) -> tuple[str, str | None]:
    """Generate a 2-line explanation. Returns (text, error_or_None)."""
    user = build_user_prompt(row)
    try:
        text = _call_openrouter(PRIMARY_MODEL, SYSTEM_PROMPT, user)
        return text, None
    except Exception as exc_primary:
        try:
            text = _call_openrouter(FALLBACK_MODEL, SYSTEM_PROMPT, user)
            return text, f"primary {PRIMARY_MODEL} failed; used fallback"
        except Exception as exc_fb:
            return "", f"both models failed: {exc_primary}; {exc_fb}"


def fallback_local(row: dict[str, Any], reason_map: dict[str, str]) -> str:
    """Offline fallback when API is unavailable — uses the reason_map dict."""
    codes = [c.strip() for c in str(row.get("codes", "")).split("|") if c.strip()][:2]
    if not codes:
        return "Call because: this row is in the conformal-uncertain pool with high triage score."
    parts = [reason_map.get(c, c.replace("_", " ")) for c in codes]
    pwrong = row.get("pwrong", 0)
    pconc  = row.get("pconc", 0)
    return (
        f"Call because: {' and '.join(parts)}.\n"
        f"Expected outcome: ~{pwrong:.0%} chance R3 is wrong; ~{pconc:.0%} chance the call gives a useful verdict."
    )
