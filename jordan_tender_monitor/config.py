"""
Central configuration for the Jordan Tender Intelligence Monitor.

Every value here was set during the Phase 1 interview. Edit this file to change
behaviour -- no other module hard-codes any of these settings.

Credentials never live here. They are read from .env (see .env.example).
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = BASE_DIR / "tender_monitor.log"
SEEN_DB = DATA_DIR / "seen_tenders.db"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------
# Q1 -- SECTORS
# Empty list == "all sectors", no sector filter is applied.
# If you later want to narrow the pipeline, list sectors here, e.g.
#   TARGET_SECTORS = ["Management Consulting", "Digital Government"]
# --------------------------------------------------------------------------
TARGET_SECTORS: list[str] = []

# Used ONLY to label tenders with a best-guess sector in the report.
# Never used to include or exclude a tender.
SECTOR_LEXICON: dict[str, list[str]] = {
    "Management Consulting": [
        "management consult", "advisory", "organisational", "organizational",
        "restructuring", "business process", "operating model", "pmo",
        "change management", "transformation",
    ],
    "Digital Government": [
        "digital", "e-government", "egovernment", "ict", "information system",
        "software", "erp", "data centre", "data center", "cyber", "automation",
        "gis", "platform", "portal",
    ],
    "Public Financial Management": [
        "public financial management", "pfm", "budget", "treasury", "taxation",
        "tax administration", "revenue", "audit", "internal control",
        "fiscal", "debt management", "accounting",
    ],
    "Governance": [
        "governance", "institutional", "public administration", "civil service",
        "anti-corruption", "rule of law", "justice", "parliament", "policy reform",
        "decentralisation", "decentralization",
    ],
    "Health": [
        "health", "hospital", "medical", "pharmaceutic", "clinic", "nutrition",
        "epidemi", "vaccine",
    ],
    "Education": [
        "education", "school", "curriculum", "teacher", "vocational", "tvet",
        "university", "training centre", "literacy",
    ],
    "Energy & Water": [
        "energy", "electricity", "power", "renewable", "solar", "water",
        "wastewater", "sanitation", "irrigation", "utility", "grid",
    ],
    "Infrastructure": [
        "infrastructure", "road", "transport", "construction", "housing",
        "urban", "municipal", "railway", "airport", "logistics",
    ],
    "Social Protection": [
        "social protection", "social safety", "cash transfer", "livelihood",
        "refugee", "resilience", "gender", "youth employment", "labour market",
        "labor market",
    ],
    "Environment & Climate": [
        "climate", "environment", "green", "circular economy", "biodiversity",
        "emission", "adaptation", "mitigation",
    ],
    "Private Sector Development": [
        "private sector", "sme", "msme", "entrepreneur", "investment promotion",
        "trade", "value chain", "competitiveness", "ppp", "public-private",
    ],
}

# --------------------------------------------------------------------------
# Q2 -- KEYWORDS
# Empty list == no keyword FILTER. Every Jordan tender is kept regardless of
# wording.
#
# Because filtering is off, the 40-point keyword-density component of the score
# would collapse to a constant and ranking would lose its strongest signal.
# RANKING_LEXICON below is therefore used for SCORING ONLY -- it never removes
# a tender, it only pushes consulting-shaped work to the top of the report.
# Populate MATCH_KEYWORDS if you ever want hard filtering back.
# --------------------------------------------------------------------------
MATCH_KEYWORDS: list[str] = []

RANKING_LEXICON: list[str] = [
    "advisory", "advisor", "consult", "consulting", "consultancy", "consultant",
    "technical assistance", "capacity building", "capacity development",
    "institutional strengthening", "institutional reform", "business process",
    "feasibility study", "management consulting", "strategy", "strategic plan",
    "organisational review", "organizational review", "operating model",
    "due diligence", "assessment", "diagnostic", "study", "review", "audit",
    "monitoring and evaluation", "impact evaluation", "training", "roadmap",
    "master plan", "policy", "reform", "restructuring", "transformation",
    "digital transformation", "e-government", "public financial management",
    "project management", "pmo", "programme management", "program management",
    "supervision", "design services", "transaction advisory", "ppp",
    "expression of interest", "request for proposal", "firm", "consulting firm",
    # Arabic equivalents. Without these an Arabic notice would score 0 on the
    # keyword component and always sink to the bottom of the report, which
    # would defeat the "include Arabic and flag it" choice.
    "استشار", "استشارية", "خدمات استشارية", "مستشار", "دراسة جدوى", "دراسة",
    "بناء القدرات", "المساعدة الفنية", "مساعدة فنية", "الدعم الفني",
    "إصلاح مؤسسي", "التطوير المؤسسي", "استراتيجية", "خطة استراتيجية",
    "التحول الرقمي", "الحوكمة", "تدريب", "تقييم", "مراجعة", "إعادة هيكلة",
    "إدارة المشاريع", "مناقصة", "عطاء", "طرح", "دعوة لتقديم", "إبداء الاهتمام",
]

# --------------------------------------------------------------------------
# Q3 -- MINIMUM CONTRACT VALUE
# --------------------------------------------------------------------------
MIN_VALUE_USD: float | None = 100_000.0
# Most donor notices publish no value at notice stage. Dropping them would
# silently remove the majority of the pipeline, so unknown-value tenders are
# kept and scored 8/15 on the value component (per spec).
KEEP_UNKNOWN_VALUE = True

# Static FX rates used to normalise stated values into USD. Approximate --
# they are for filtering/ranking only, never for anything financial.
FX_TO_USD: dict[str, float] = {
    "USD": 1.0, "EUR": 1.09, "GBP": 1.27, "JOD": 1.41, "CHF": 1.13,
    "SAR": 0.27, "AED": 0.27, "JPY": 0.0064, "SEK": 0.095, "NOK": 0.093,
    "DKK": 0.145, "CAD": 0.73, "AUD": 0.66, "XDR": 1.33,
}

# --------------------------------------------------------------------------
# Q4 -- NOTICE TYPES
# Empty list == all types. Portals label notice types inconsistently, so a
# type filter reliably drops real opportunities.
# --------------------------------------------------------------------------
NOTICE_TYPES: list[str] = []

# --------------------------------------------------------------------------
# Q5 -- LOOKBACK WINDOW
# None == no posted-date cutoff; return everything still open.
# Set to 7, 30 or 90 to restrict by posting date.
# --------------------------------------------------------------------------
LOOKBACK_DAYS: int | None = None

# --------------------------------------------------------------------------
# Q6 -- CLOSED TENDERS
# --------------------------------------------------------------------------
EXCLUDE_CLOSED = True
# Notices with no published deadline are kept and flagged rather than dropped.
KEEP_UNKNOWN_DEADLINE = True

# --------------------------------------------------------------------------
# Q7 -- NEW-ONLY MODE
# On: each run reports only tenders never seen before, which keeps the daily
# email to what actually changed instead of resending the whole open list.
#
# The first run after enabling this reports everything, because the database
# starts empty; from the second run onward it reports only new notices. To go
# back to full listings, set this to False, or run `python run.py --reset-db`
# to forget everything already reported and re-send it once.
# --------------------------------------------------------------------------
NEW_ONLY_MODE = True

# --------------------------------------------------------------------------
# Q8 -- LANGUAGE
# "both_flag_arabic" -> include Arabic tenders, keep original text, flag them.
# Alternatives: "english_only", "translate"
# --------------------------------------------------------------------------
LANGUAGE_MODE = "both_flag_arabic"
ARABIC_FLAG_NOTE = "Arabic-language notice - manual review required"

# --------------------------------------------------------------------------
# Q9 -- ELIGIBILITY
# "flag" -> keep national-only tenders, mark them, and deprioritise them.
# Alternatives: "exclude", "include_all"
# --------------------------------------------------------------------------
ELIGIBILITY_MODE = "flag"
NATIONAL_ONLY_PENALTY = 25  # points subtracted from the score
NATIONAL_ONLY_MARKERS = [
    "national firms only", "local firms only", "national consultants only",
    "jordanian firms", "locally registered", "national companies only",
    "restricted to national", "domestic firms only", "national competitive bidding",
    "registered in jordan",
    # Donor-specific nationality restrictions that also exclude international firms.
    # SFD in particular restricts many calls to Saudi firms or Saudi-led JVs.
    "saudi firms", "saudi companies", "joint venture with a saudi",
    "restricted to japanese", "japanese firms only", "japanese nationals",
    "member country firms only",
    # Arabic
    "الشركات المحلية فقط", "الشركات الأردنية", "المؤسسات المحلية فقط",
    "مسجلة في الأردن", "للشركات المحلية", "الشركات السعودية",
]

# --------------------------------------------------------------------------
# Q10 -- PORTALS
# All 13 enabled. Set a value to False to skip that portal entirely.
# --------------------------------------------------------------------------
ENABLED_PORTALS: dict[str, bool] = {
    # REST APIs
    "worldbank": True,
    "ted": True,
    "samgov": True,
    # HTML scrapers
    "ebrd": True,
    "eib": True,
    "ungm": True,
    "giz": True,
    "kfw": True,
    "isdb": True,
    "fcdo": True,
    # Announcement-only (lower reliability)
    "sfd": True,
    "adfd": True,
    "jica": True,
}

# Human-readable portal names, used in the report.
PORTAL_NAMES: dict[str, str] = {
    "worldbank": "World Bank",
    "ted": "EU TED",
    "samgov": "SAM.gov (USAID/US Gov)",
    "ebrd": "EBRD",
    "eib": "EIB",
    "ungm": "UNGM (UN agencies)",
    "giz": "GIZ",
    "kfw": "KfW",
    "isdb": "IsDB",
    "fcdo": "UK FCDO / Find a Tender",
    "sfd": "Saudi Fund for Development",
    "adfd": "Abu Dhabi Fund for Development",
    "jica": "JICA",
}

# --------------------------------------------------------------------------
# Scraping behaviour
# --------------------------------------------------------------------------
MAX_WORKERS = 5              # parallel scrapers
REQUEST_TIMEOUT = 45         # seconds
POLITE_DELAY_SECONDS = 2.0   # minimum gap between requests to the same host
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5         # seconds, exponential
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
COUNTRY_TERMS = [
    "jordan", "jordanian", "hashemite kingdom", "jordanien", "jordanie",
    "الأردن", "الاردن", "الأردنية", "الاردنية", "المملكة الأردنية",
    "amman", "عمان", "aqaba", "irbid", "zarqa",
]

# HTML-scraper hardening
MAX_PAGINATION_PAGES = 5   # follow "next page" at most this many times per source
DETAIL_FETCH_BUDGET = 8    # extra requests per portal to recover missing deadlines
FOLLOW_PAGINATION = True
ENRICH_FROM_DETAIL = True

# Deduplication
DEDUPE_SIMILARITY_THRESHOLD = 85  # rapidfuzz token_sort_ratio

# --------------------------------------------------------------------------
# Scoring weights
#
# Spec baseline: keyword 40 / sector 30 / value 15 / urgency 15.
# Components whose filter is disabled would award every tender the same points,
# so they are dropped and the remaining weights renormalise to 100.
# With "all sectors" selected, the sector component is dropped and the
# effective weights become keyword 57.1 / value 21.4 / urgency 21.4.
# --------------------------------------------------------------------------
SCORE_WEIGHTS: dict[str, float] = {
    "keyword": 40.0,
    "sector": 30.0,
    "value": 15.0,
    "urgency": 15.0,
}

# --------------------------------------------------------------------------
# Q11 -- EMAIL DELIVERY
# "graph"  -> Microsoft Graph API (chosen)
# "smtp"   -> Office 365 SMTP
# "none"   -> save files only
# The dispatcher falls back graph -> smtp -> file-save if credentials are absent.
# --------------------------------------------------------------------------
EMAIL_METHOD = "graph"


def _addresses(name: str) -> list[str]:
    """Comma-separated address list from the environment."""
    return [a.strip() for a in os.getenv(name, "").split(",") if a.strip()]


# Recipients live in .env, not here, so the repository carries no personal
# addresses. Set EMAIL_RECIPIENTS=you@example.com in .env (comma-separate for
# several). With none set, the report is written to output/ and no mail is sent.
EMAIL_RECIPIENTS = _addresses("EMAIL_RECIPIENTS")
EMAIL_CC = _addresses("EMAIL_CC")
# The subject is assembled in reporter.build_subject() so it can reflect the
# run's health, not just the count -- a run where every portal was unreachable
# must not look like a quiet day in the inbox.
EMAIL_SUBJECT_PREFIX = "Jordan Tender Intelligence"

# --------------------------------------------------------------------------
# Q12 -- REPORT FORMAT
# "A" summary table | "B" grouped by sector | "C" full details | "D" exec brief
# --------------------------------------------------------------------------
REPORT_FORMAT = "C"
# Outlook clips messages larger than ~100 KB. Full detail is rendered inline for
# this many tenders (highest scoring first); the rest are listed as a compact
# table with a pointer to the attached workbook. Nothing is ever dropped.
MAX_INLINE_TENDERS = 50
DESCRIPTION_CHAR_LIMIT = 1500  # per tender, in the email body only

# --------------------------------------------------------------------------
# Q13 -- OUTPUT FILES
# --------------------------------------------------------------------------
OUTPUT_FORMATS = ["excel", "json", "csv", "html", "docx"]

# Which of the generated files are attached to the email, in this order.
# The Word document circulates and annotates more easily than the workbook;
# the workbook is better for working the pipeline. Both are attached.
EMAIL_ATTACH_FORMATS = ["docx", "excel"]
EXCEL_ATTACH = True  # kept for backwards compatibility; see EMAIL_ATTACH_FORMATS

# Excel row colours by score band
COLOR_HIGH = "C6EFCE"    # >= 70  light green
COLOR_MEDIUM = "FFEB9C"  # 40-69  yellow
COLOR_LOW = "FFC7CE"     # < 40   light red

# --------------------------------------------------------------------------
# Q14 -- SCHEDULE
# "once" | "daily" | "weekly" | "mon_thu"
# --------------------------------------------------------------------------
SCHEDULE_MODE = "daily"
SCHEDULE_TIME = "07:00"   # local time, 24h
SCHEDULE_WEEKDAY = "monday"  # only used when SCHEDULE_MODE == "weekly"

# --------------------------------------------------------------------------
# Credentials (loaded from .env -- never hard-code them here)
# --------------------------------------------------------------------------
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SAM_API_KEY = os.getenv("SAM_API_KEY", "")


def refresh_credentials() -> None:
    """Re-read credentials from the environment after load_dotenv() has run."""
    global AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, SENDER_EMAIL
    global SMTP_USER, SMTP_PASS, SMTP_HOST, SMTP_PORT, SAM_API_KEY
    global EMAIL_RECIPIENTS, EMAIL_CC
    EMAIL_RECIPIENTS = _addresses("EMAIL_RECIPIENTS")
    EMAIL_CC = _addresses("EMAIL_CC")
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
    AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
    AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
    SAM_API_KEY = os.getenv("SAM_API_KEY", "")
