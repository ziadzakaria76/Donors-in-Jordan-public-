"""
Central configuration for the Jordan Tender Intelligence Monitor.

Every value here was set during the Phase 1 interview; the Q-numbers below map
to the interview questions. Edit this file to change behaviour -- no other
module hard-codes any of these settings.

Credentials and recipient addresses never live here. They are read from .env,
which is gitignored, because this repository is public.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
#
# The environment overrides exist so the test suite and --self-test can point
# state at a temp directory. Without them a diagnostic run would write fixture
# IDs into the real seen-tenders database, and the next live run would report
# nothing and look broken.
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("JTM_DATA_DIR") or BASE_DIR / "data")
OUTPUT_DIR = Path(os.getenv("JTM_OUTPUT_DIR") or BASE_DIR / "output")
LOG_FILE = Path(os.getenv("JTM_LOG_FILE") or BASE_DIR / "tender_monitor.log")
SEEN_DB = Path(os.getenv("JTM_SEEN_DB") or DATA_DIR / "seen_tenders.db")
FIXTURE_DIR = BASE_DIR / "tests" / "fixtures"
LIVE_FIXTURE_DIR = FIXTURE_DIR / "live"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Q1 -- SECTORS: "all sectors, label but never filter".
#
# An empty TARGET_SECTORS means no sector filter is applied. SECTOR_LEXICON is
# used only to attach a best-guess label for grouping and reading; it can never
# remove a tender. Donor portals describe the same institutional-reform job as
# "Governance", "Public Administration" or an untagged "Technical Assistance",
# so a sector filter drops real work on wording alone.
# --------------------------------------------------------------------------
TARGET_SECTORS: list[str] = []

SECTOR_LEXICON: dict[str, list[str]] = {
    "Management Consulting": [
        "management consult", "advisory services", "organisational review",
        "organizational review", "restructuring", "business process",
        "operating model", "pmo", "change management", "transformation",
        "corporate strategy",
    ],
    "Digital Government": [
        "digital", "e-government", "egovernment", "ict", "information system",
        "software", "erp", "data centre", "data center", "cyber", "automation",
        "gis", "digital platform", "portal development", "interoperability",
    ],
    "Public Financial Management": [
        "public financial management", "pfm", "budget", "treasury", "taxation",
        "tax administration", "revenue", "internal control", "fiscal",
        "debt management", "accounting", "public expenditure",
    ],
    "Governance": [
        "governance", "institutional", "public administration", "civil service",
        "anti-corruption", "rule of law", "justice", "parliament",
        "policy reform", "decentralisation", "decentralization",
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
        "energy", "electricity", "power plant", "renewable", "solar", "water",
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
        "climate", "environment", "green transition", "circular economy",
        "biodiversity", "emission", "adaptation", "mitigation",
    ],
    "Private Sector Development": [
        "private sector", "sme", "msme", "entrepreneur", "investment promotion",
        "trade facilitation", "value chain", "competitiveness", "ppp",
        "public-private",
    ],
}

# --------------------------------------------------------------------------
# Q2 -- KEYWORDS: "no filter; lexicon ranks only".
#
# MATCH_KEYWORDS empty == no keyword filter. Every Jordan tender is kept
# regardless of wording, because donor titles are frequently unmatchable
# ("Consulting Services -- P178432").
#
# With filtering off, the keyword score component would award every tender the
# same points and carry no information. RANKING_LEXICON therefore drives
# SCORING ONLY: it never removes a tender, it only lifts consulting-shaped work
# to the top. Arabic terms are included because otherwise every Arabic notice
# would score zero here and permanently sink -- which would defeat Q8.
# --------------------------------------------------------------------------
MATCH_KEYWORDS: list[str] = []

RANKING_LEXICON: list[str] = [
    "advisory", "adviser", "advisor", "consult", "consulting", "consultancy",
    "consultant", "technical assistance", "capacity building",
    "capacity development", "institutional strengthening", "institutional reform",
    "business process", "feasibility study", "management consulting",
    "strategy", "strategic plan", "organisational review", "organizational review",
    "operating model", "due diligence", "assessment", "diagnostic", "study",
    "review", "audit", "monitoring and evaluation", "impact evaluation",
    "training", "roadmap", "master plan", "policy", "reform", "restructuring",
    "transformation", "digital transformation", "e-government",
    "public financial management", "project management", "pmo",
    "programme management", "program management", "supervision",
    "design services", "transaction advisory", "ppp", "expression of interest",
    "request for proposal", "terms of reference", "consulting firm",
    # Arabic equivalents -- see the note above.
    "استشار", "استشارية", "خدمات استشارية", "مستشار", "دراسة جدوى", "دراسة",
    "بناء القدرات", "المساعدة الفنية", "مساعدة فنية", "الدعم الفني",
    "إصلاح مؤسسي", "التطوير المؤسسي", "استراتيجية", "خطة استراتيجية",
    "التحول الرقمي", "الحوكمة", "تدريب", "تقييم", "مراجعة", "إعادة هيكلة",
    "إدارة المشاريع", "مناقصة", "عطاء", "دعوة لتقديم", "إبداء الاهتمام",
]

# Terms that mark a notice as goods/works rather than consulting. Used only to
# push such notices DOWN the ranking -- never to exclude them (Q2).
DEPRIORITISE_LEXICON: list[str] = [
    "supply and delivery", "supply of", "procurement of vehicles",
    "medical equipment", "civil works", "construction of", "rehabilitation of",
    "spare parts", "furniture", "stationery", "fuel supply", "catering",
]

# --------------------------------------------------------------------------
# Q3 -- MINIMUM CONTRACT VALUE: "$100k floor, keep unknowns".
#
# The floor applies ONLY to tenders whose value was actually published. Most
# donor notices omit value at notice stage (UNGM, GIZ and EBRD almost always
# do), so dropping unknown-value tenders would silently remove the majority of
# the pipeline. An unpublished value means unknown, not small.
# --------------------------------------------------------------------------
MIN_VALUE_USD: float | None = 100_000.0
KEEP_UNKNOWN_VALUE = True

# Static FX rates used to normalise stated values into USD, for filtering and
# ranking only. Never used for anything financial.
FX_TO_USD: dict[str, float] = {
    "USD": 1.0, "EUR": 1.09, "GBP": 1.27, "JOD": 1.41, "CHF": 1.13,
    "SAR": 0.27, "AED": 0.27, "JPY": 0.0064, "SEK": 0.095, "NOK": 0.093,
    "DKK": 0.145, "CAD": 0.73, "AUD": 0.66, "XDR": 1.33, "KWD": 3.26,
}

# --------------------------------------------------------------------------
# Q4 -- NOTICE TYPES: "all types, type shown as a label".
#
# Empty == all types. Portals label inconsistently and often not at all, so a
# type filter drops tenders on a technicality. EOIs and GPNs are also the
# earliest signal available -- filtering to RFP-only optimises for tenders you
# are already too late to shape.
# --------------------------------------------------------------------------
NOTICE_TYPES: list[str] = []

# --------------------------------------------------------------------------
# Q5 -- LOOKBACK WINDOW: "all currently open, no date cutoff".
# None == no posted-date cutoff. New-only mode (Q7) already bounds volume;
# a lookback window on top would permanently hide a tender you had never seen.
# --------------------------------------------------------------------------
LOOKBACK_DAYS: int | None = None

# --------------------------------------------------------------------------
# Q6 -- DEADLINES: "exclude closed; keep and flag undated".
# A tender closing TODAY counts as open -- an off-by-one here discards the most
# urgent tenders in the report.
# --------------------------------------------------------------------------
EXCLUDE_CLOSED = True
KEEP_UNKNOWN_DEADLINE = True
UNKNOWN_DEADLINE_NOTE = "Deadline not published - verify on portal"

# --------------------------------------------------------------------------
# Q7 -- NEW-ONLY MODE: on, SQLite-backed.
# The first run reports everything because the database starts empty; that is
# expected, not a bug. `run.py --reset-db` forgets everything and re-sends once.
# --------------------------------------------------------------------------
NEW_ONLY_MODE = True

# --------------------------------------------------------------------------
# Q8 -- LANGUAGE: include Arabic, keep original text, flag it.
# Alternatives kept for reference: "english_only".
# --------------------------------------------------------------------------
LANGUAGE_MODE = "include_flag_arabic"
ARABIC_FLAG_NOTE = "Arabic-language notice - manual review required"

# --------------------------------------------------------------------------
# Q9 -- ELIGIBILITY: flag and deprioritise, never exclude.
# Eligibility language usually lives in the tender documents rather than the
# listing page, so excluding on it means acting on evidence you cannot see.
# "National firms only" also often still permits an international firm in JV
# with a local partner, which is a real and winnable route.
# --------------------------------------------------------------------------
ELIGIBILITY_MODE = "flag"
NATIONAL_ONLY_PENALTY = 25
NATIONAL_ONLY_NOTE = "National/local firms only - JV with a local partner may be required"
NATIONAL_ONLY_MARKERS = [
    "national firms only", "local firms only", "national consultants only",
    "jordanian firms only", "locally registered", "national companies only",
    "restricted to national", "domestic firms only",
    "national competitive bidding", "registered in jordan",
    "must be registered in jordan", "local firms are eligible",
    # Donor-specific nationality restrictions that also exclude an
    # international firm bidding on its own.
    "saudi firms", "saudi companies", "joint venture with a saudi",
    "restricted to japanese", "japanese firms only", "japanese nationals",
    "member country firms only", "member countries only",
    # Arabic
    "الشركات المحلية فقط", "الشركات الأردنية", "المؤسسات المحلية فقط",
    "مسجلة في الأردن", "للشركات المحلية", "الشركات السعودية",
]

# --------------------------------------------------------------------------
# Q10 -- PORTALS: all 13 enabled, tiered by reliability.
# A quiet portal costs one request per run; a disabled portal yields nothing
# permanently. Set a value to False to skip that portal entirely.
# --------------------------------------------------------------------------
ENABLED_PORTALS: dict[str, bool] = {
    # Tier 1 -- REST APIs, most reliable
    "worldbank": True,
    "ted": True,
    "samgov": True,
    "fcdo": True,
    # Tier 2 -- HTML scraping, high yield
    "ungm": True,
    "ebrd": True,
    "eib": True,
    "giz": True,
    "kfw": True,
    "isdb": True,
    # Tier 3 -- announcement-only, low yield
    "sfd": True,
    "adfd": True,
    "jica": True,
}

PORTAL_NAMES: dict[str, str] = {
    "worldbank": "World Bank",
    "ted": "EU TED",
    "samgov": "SAM.gov (USAID / US Gov)",
    "fcdo": "UK Find a Tender",
    "ungm": "UNGM (UNDP, UNICEF, WFP, UNOPS, UNHCR, UNRWA)",
    "ebrd": "EBRD",
    "eib": "EIB",
    "giz": "GIZ",
    "kfw": "KfW (via Germany Trade & Invest)",
    "isdb": "IsDB",
    "sfd": "Saudi Fund for Development",
    "adfd": "Abu Dhabi Fund for Development",
    "jica": "JICA",
}

# Reliability tier, shown in the report so a quiet Tier 3 portal is not
# mistaken for a broken one.
PORTAL_TIERS: dict[str, int] = {
    "worldbank": 1, "ted": 1, "samgov": 1, "fcdo": 1,
    "ungm": 2, "ebrd": 2, "eib": 2, "giz": 2, "kfw": 2, "isdb": 2,
    "sfd": 3, "adfd": 3, "jica": 3,
}
TIER_LABELS = {1: "API", 2: "HTML", 3: "announcements only"}

# --------------------------------------------------------------------------
# Scraping behaviour
# --------------------------------------------------------------------------
MAX_WORKERS = 5
REQUEST_TIMEOUT = 45
POLITE_DELAY_SECONDS = 2.0   # minimum gap between requests to the SAME host
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

MAX_PAGINATION_PAGES = 5
DETAIL_FETCH_BUDGET = 8
FOLLOW_PAGINATION = True
ENRICH_FROM_DETAIL = True

DEDUPE_SIMILARITY_THRESHOLD = 85   # rapidfuzz token_sort_ratio

# --------------------------------------------------------------------------
# Scoring weights.
#
# Baseline: keyword 40 / sector 30 / value 15 / urgency 15.
#
# A component whose filter is disabled awards every tender the same points and
# therefore carries no information. Such components are DROPPED and the rest
# renormalised to 100 (see agents/filter.py). With "all sectors" selected the
# sector component is dropped, giving keyword 57.1 / value 21.4 / urgency 21.4.
# --------------------------------------------------------------------------
SCORE_WEIGHTS: dict[str, float] = {
    "keyword": 40.0,
    "sector": 30.0,
    "value": 15.0,
    "urgency": 15.0,
}
UNKNOWN_VALUE_SCORE_FRACTION = 0.55   # unknown value scores mid-band, not zero

# --------------------------------------------------------------------------
# Q11 -- EMAIL DELIVERY: Graph -> SMTP -> disk.
#
# SECURITY: if Mail.Send is granted as an Azure APPLICATION permission it is
# TENANT-WIDE -- the app can send as any mailbox in the organisation. Scope it
# to one mailbox with an ApplicationAccessPolicy. See the README.
# --------------------------------------------------------------------------
EMAIL_METHOD = "graph"
EMAIL_FALLBACK_CHAIN = ["graph", "smtp", "file"]


def _addresses(name: str) -> list[str]:
    """Comma-separated address list from the environment."""
    return [a.strip() for a in os.getenv(name, "").split(",") if a.strip()]


# Recipients live in .env because this repository is public. Committing them
# would publish colleagues' work addresses permanently -- git history keeps
# them even after deletion. With none set, files are written and no mail sent.
EMAIL_RECIPIENTS = _addresses("EMAIL_RECIPIENTS")
EMAIL_CC = _addresses("EMAIL_CC")
EMAIL_SUBJECT_PREFIX = "Jordan Tenders"

# --------------------------------------------------------------------------
# Q12 -- REPORT FORMAT: full detail, top 50 inline, overflow tabled.
# Outlook clips messages over roughly 100 KB and hides the tail without saying
# so. Beyond MAX_INLINE_TENDERS, tenders MOVE to a compact table -- they are
# never dropped.
# --------------------------------------------------------------------------
REPORT_FORMAT = "full_detail"
MAX_INLINE_TENDERS = 50
DESCRIPTION_CHAR_LIMIT = 1500

# --------------------------------------------------------------------------
# Q13 -- OUTPUT FILES: all five; Word and Excel attached.
# --------------------------------------------------------------------------
OUTPUT_FORMATS = ["docx", "excel", "json", "csv", "html"]
EMAIL_ATTACH_FORMATS = ["docx", "excel"]

# Excel score-band fills. openpyxl requires BARE hex -- "#C6EFCE" raises.
COLOR_HIGH = "C6EFCE"     # >= 70  green
COLOR_MEDIUM = "FFEB9C"   # 40-69  amber
COLOR_LOW = "FFC7CE"      # < 40   red
COLOR_HEADER = "1F4E79"

# --------------------------------------------------------------------------
# Q14 -- SCHEDULE: weekdays 07:00, pinned to Asia/Amman.
#
# Jordan is UTC+3 year-round (DST abolished in 2022). 07:00 on a UTC host would
# fire at 10:00 in Amman, so the timezone is pinned explicitly rather than
# trusting the host clock. Equivalent cron: 0 4 * * 1-5  (04:00 UTC).
# --------------------------------------------------------------------------
SCHEDULE_MODE = "weekdays"
SCHEDULE_TIME = "07:00"
SCHEDULE_TIMEZONE = "Asia/Amman"
SCHEDULE_CRON_UTC = "0 4 * * 1-5"

# --------------------------------------------------------------------------
# Q15 -- FAILURE ALERTING: portal health in the subject, diagnosed table in the
# body. A subject reading "0 opportunities" whether every portal failed or
# every portal worked lets a dead monitor go unnoticed for weeks.
# --------------------------------------------------------------------------
HEALTH_IN_SUBJECT = True
ACTION_NEEDED_PREFIX = "ACTION NEEDED"

# --------------------------------------------------------------------------
# Country matching.
#
# Latin terms are matched on WORD BOUNDARIES: plain substring matching puts
# Jordanstown (Northern Ireland) and Ammanford (Wales) in the report, which is
# a live risk on UK Find a Tender because it scans the whole UK corpus.
# Arabic terms stay substring-based because Arabic is agglutinative --
# الأردنية legitimately contains الأردن.
# --------------------------------------------------------------------------
COUNTRY_TERMS_LATIN = [
    "jordan", "jordanian", "hashemite kingdom", "jordanien", "jordanie",
    "amman", "aqaba", "irbid", "zarqa", "mafraq", "karak", "madaba", "salt",
]
COUNTRY_TERMS_ARABIC = [
    "الأردن", "الاردن", "الأردنية", "الاردنية", "المملكة الأردنية",
    "عمان", "العقبة", "إربد", "الزرقاء", "المفرق",
]
# A .jo domain is positive evidence of Jordan even with no country word.
COUNTRY_TLD = ".jo"

# --------------------------------------------------------------------------
# Credentials -- read from .env, never hard-coded, never logged.
# --------------------------------------------------------------------------
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SAM_API_KEY = os.getenv("SAM_API_KEY", "")


def refresh_credentials() -> None:
    """Re-read credentials and recipients after load_dotenv() has run."""
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
