"""
Offline sample data for --self-test and the test suite.

Deliberately includes the awkward cases: a tender with every optional field
None, an Arabic notice, a national-only restriction, a duplicate across two
portals, a deadline of exactly today, and a value published in a European
format. These are the shapes that break pipelines, so they belong in the
sample rather than a tidy set of well-formed records.
"""

from __future__ import annotations

from datetime import date, timedelta

from .agents.scraper import PortalHealth
from .portals import base


def sample_records(today: date | None = None) -> list[dict]:
    today = today or date.today()

    def d(days: int) -> date:
        return today + timedelta(days=days)

    records = [
        base.build_record(
            portal="worldbank",
            title="Institutional Strengthening of the Ministry of Finance, Jordan",
            url="https://example.org/wb/1",
            posted=d(-10), closing=d(45),
            value_text="USD 1,850,000",
            description="Consulting services to support public financial management "
                        "reform, including budget execution and treasury operations.",
            notice_type="Request for Expression of Interest",
            contact="procurement@example.org",
            reference="WB-JO-2026-114",
        ),
        base.build_record(
            portal="ungm",
            # Same assignment as above, published on a second portal. The
            # deduplicator must collapse these into one.
            title="Institutional Strengthening of the Ministry of Finance (Jordan)",
            url="https://example.org/ungm/1",
            posted=d(-9), closing=d(45),
            value_text=None,
            description="UNDP Jordan: PFM reform advisory.",
            notice_type="Request for Proposal",
            reference="UNGM-2026-441",
        ),
        base.build_record(
            portal="giz",
            title="Beratungsleistungen zur Verwaltungsreform, Jordanien",
            url="https://example.org/giz/2",
            posted=d(-20), closing=d(60),
            # European format: 1.5 million, not 1.5.
            value_text="EUR 1.500.000",
            description="Technische Zusammenarbeit zur Verwaltungsreform in Amman.",
            notice_type="Ausschreibung",
            reference="GIZ-2026-77",
            default_currency="EUR",
        ),
        base.build_record(
            portal="sfd",
            title="خدمات استشارية لتطوير القطاع المالي في الأردن",
            url="https://example.org/sfd/3",
            posted=d(-5), closing=d(30),
            value_text="٧٥٠٠٠٠ دولار",
            description="دراسة جدوى وبناء القدرات لوزارة المالية. الشركات المحلية فقط.",
            notice_type="مناقصة",
            reference="SFD-2026-9",
        ),
        base.build_record(
            portal="ebrd",
            # Deadline exactly today: must be KEPT. An off-by-one here throws
            # away the most urgent tender in the report.
            title="Energy Efficiency Investment Programme Advisory, Amman",
            url="https://example.org/ebrd/4",
            posted=d(-30), closing=today,
            value_text="EUR 900,000",
            description="Advisory services for an energy efficiency facility.",
            notice_type="Expression of Interest",
            reference="EBRD-2026-900",
            default_currency="EUR",
        ),
        base.build_record(
            portal="isdb",
            # Every optional field absent. Nothing downstream may assume a
            # field exists.
            title="Consulting Services for Water Sector Study, Jordan",
            url=None, posted=None, closing=None,
            value_text=None, description=None, notice_type=None,
            contact=None, reference=None,
        ),
        base.build_record(
            portal="fcdo",
            # Already closed: must be dropped.
            title="Trade Facilitation Advisory, Aqaba, Jordan",
            url="https://example.org/fcdo/5",
            posted=d(-90), closing=d(-3),
            value_text="GBP 400,000",
            description="Closed notice, retained in the fixture to prove it is dropped.",
            notice_type="Contract notice",
            reference="FT-2026-5",
            default_currency="GBP",
        ),
        base.build_record(
            portal="worldbank",
            # Published value below the $100k floor: must be dropped.
            title="Small Equipment Supply for Clinics, Jordan",
            url="https://example.org/wb/6",
            posted=d(-4), closing=d(20),
            value_text="USD 40,000",
            description="Supply and delivery of small equipment.",
            notice_type="Request for Quotation",
            reference="WB-JO-2026-200",
        ),
        base.build_record(
            portal="kfw",
            title="Digital Transformation Advisory, Government of Jordan",
            url="https://example.org/gtai/7",
            posted=d(-2), closing=d(75),
            value_text="EUR 2.400.000",
            description="Advisory services for an e-government platform rollout, "
                        "including business process reengineering.",
            notice_type="Tender",
            reference="GTAI-2026-7",
            default_currency="EUR",
        ),
    ]
    return records


def sample_health() -> list[PortalHealth]:
    """A realistic mix: healthy portals, a broken one, an unconfigured one."""
    return [
        PortalHealth("worldbank", "World Bank", 1, "ok", count=2, layer="api"),
        PortalHealth("ted", "EU TED", 1, "ok", count=0, layer="api"),
        PortalHealth(
            "samgov", "SAM.gov (USAID / US Gov)", 1, "unconfigured",
            reason="not configured - no SAM_API_KEY in .env",
            urls=["https://api.sam.gov/prod/opportunities/v2/search"]),
        PortalHealth("fcdo", "UK Find a Tender", 1, "ok", count=1, layer="api"),
        PortalHealth("ungm", "UNGM (UNDP, UNICEF, WFP, UNOPS, UNHCR, UNRWA)", 2,
                     "ok", count=1, layer="embedded-json", quality=0.92),
        PortalHealth(
            "ebrd", "EBRD", 2, "unavailable",
            reason="bot wall (Cloudflare/Incapsula) - needs a different network "
                   "or Playwright",
            urls=["https://www.ebrd.com/home/work-with-us/project-procurement/"
                  "procurement-notices.html"]),
        PortalHealth("eib", "EIB", 2, "ok", count=0, layer="structural", quality=0.71),
        PortalHealth("giz", "GIZ", 2, "ok", count=1, layer="table", quality=0.88),
        PortalHealth("kfw", "KfW (via Germany Trade & Invest)", 2, "ok", count=1,
                     layer="selectors", quality=0.95),
        PortalHealth("isdb", "IsDB", 2, "ok", count=1, layer="structural", quality=0.64),
        PortalHealth("sfd", "Saudi Fund for Development", 3, "ok", count=1,
                     layer="selectors", quality=0.79),
        PortalHealth("adfd", "Abu Dhabi Fund for Development", 3, "ok", count=0,
                     layer="anchor-pattern", quality=0.41),
        PortalHealth("jica", "JICA", 3, "ok", count=0, layer="structural", quality=0.55),
    ]


def all_broken_health() -> list[PortalHealth]:
    """Every portal down -- the case the subject line must not hide."""
    health = sample_health()
    for h in health:
        if h.status == "unconfigured":
            continue
        h.status = "unavailable"
        h.count = 0
        h.reason = "transport error - ConnectionError (the host is blocked)"
    return health
