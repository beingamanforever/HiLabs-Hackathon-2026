import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    """Return a path from the environment when set, otherwise *default*."""
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


PROJECT_ROOT = _env_path("PROJECT_ROOT", Path(__file__).resolve().parents[2])
BASE_DATA_FILE = _env_path("BASE_DATA_FILE", PROJECT_ROOT / "Base data_hackathon.xlsx")
CLAIMS_DATA_FILE = _env_path("CLAIMS_DATA_FILE", PROJECT_ROOT / "Claims data_Hackathon.xlsx")
NPPES_DATA_FILE = _env_path("NPPES_DATA_FILE", PROJECT_ROOT / "data" / "npidata_pfile.csv")
CACHE_DIR = _env_path("CACHE_DIR", PROJECT_ROOT / "outputs" / "cache")

CONCLUSIVE_LABELS = {"ACCURATE", "INACCURATE"}
TELEHEALTH_POS_CODES = {"2", "02", "10"}
LOW_SCORE_BANDS = {"<=0", "0-25"}
MID_SCORE_BANDS = {"25-50", "50-75"}
HIGH_SCORE_BANDS = {"75-100"}

URL_EVIDENCE_COLUMNS = [
    "Address_ProviderView_not_found_in_websites_URLS_Orgwebsite",
    "Address_ProviderView_not_found_in_websites_URLS_Providerwebsite",
    "Address_ProviderView_not_found_in_websites_URLS_Aggregator",
    "Address_ProviderView_found_in_websites_URLS_Orgwebsite",
    "Address_ProviderView_found_in_websites_URLS_Providerwebsite",
    "Address_ProviderView_found_in_websites_URLS_Aggregator",
    "Address_OrgView_not_found_in_websites_URLS_Orgwebsite",
    "Address_OrgView_not_found_in_websites_URLS_Providerwebsite",
    "Address_OrgView_not_found_in_websites_URLS_Aggregator",
    "Address_OrgView_found_in_websites_URLS_Orgwebsite",
    "Address_OrgView_found_in_websites_URLS_Providerwebsite",
    "Address_OrgView_found_in_websites_URLS_Aggregator",
]

COMMENT_PATTERNS = {
    "operator_confirmed_accurate": r"ADDRESS IS ACCURATE|WORKS AT THE PF LOCATION|PRACTICES AT THE PF LOCATION",
    "left_org": r"LEFT ORG|LEFT THE PRACTICE|NO LONGER PRACTIC|NO LONGER WORK",
    "new_address": r"NEW ADDRESS|MOVED|RELOCAT",
    "telehealth": r"TELEHEALTH|VIRTUAL",
    "wrong_org_phone": r"PF NO\. IS LINKED TO THE ORG|PHONE NUMBER IS LINKED TO THE ORGANIZATION",
    "operator_or_frontdesk": r"OPERATOR|FRONT DESK|RECEPTION|S/W",
}

BEHAVIORAL_HEALTH_KEYWORDS = (
    "BEHAVIORAL",
    "COUNSELOR",
    "THERAPIST",
    "PSYCHIAT",
    "PSYCHOLOG",
    "SOCIAL WORK",
    "MENTAL HEALTH",
)

# ── Staleness decay ────────────────────────────────────────────────────────────
# Exponential decay half-life for address staleness score.
# 210 days ≈ 7 months; a provider silent at PF ZIP for 14 months → staleness ≈ 0.87
STALENESS_HALF_LIFE_DAYS: int = 210

# ── Conformal calibration ─────────────────────────────────────────────────────
# Marginal coverage target for conformal flip guard and triage selection.
CONFORMAL_ALPHA: float = 0.05   # 95% coverage guarantee

# ── Source credibility tier patterns ──────────────────────────────────────────
# Tier 1: government registries, hospital / health-system owned sites — highest trust
TIER1_PATTERNS: tuple[str, ...] = (
    ".gov",
    "cms.gov",
    "nppes",
    "npi.",
    "state.",
    "hospital",
    "medical-center",
    "medicalcenter",
    "health-system",
    "healthsystem",
    "medicare",
    "medicaid",
    "hhs.",
    "ahrq.",
    "jointcommission",
)

# Tier 3: lead-gen / consumer aggregators — lowest trust (treated as weak signal)
TIER3_PATTERNS: tuple[str, ...] = (
    "healthgrades",
    "vitals.com",
    "zocdoc",
    "webmd",
    "wellness",
    "usnews",
    "ratemds",
    "yelp",
    "yellowpages",
    "doximity",
    "castleconnolly",
    "sharecare",
    "betterdoctor",
)

# ── LightGBM ranker config ────────────────────────────────────────────────────
LGB_NDCG_EVAL_AT: list[int] = [50, 100, 450]
LGB_N_ESTIMATORS: int = 200
LGB_EARLY_STOPPING: int = 20
LGB_LEARNING_RATE: float = 0.05
LGB_NUM_LEAVES: int = 31
LGB_MIN_CHILD_SAMPLES: int = 5  # guard against small-group overfitting

# ── NPPES columns of interest ─────────────────────────────────────────────────
NPPES_COLUMN_MAP: dict[str, str] = {
    "NPI": "NPI",
    "Provider First Line Business Practice Location Address": "nppes_address",
    "Provider Business Practice Location Address Postal Code": "nppes_zip_raw",
    "Provider Business Practice Location Address State Name": "nppes_state",
    "NPI Deactivation Date": "nppes_deactivation_date",
}
