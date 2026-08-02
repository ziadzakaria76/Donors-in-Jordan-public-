"""
Built-in sample tenders for `python run.py --self-test`.

These exist so the filter, scorer, deduplicator, report builder and file writers
can be exercised end-to-end without touching the network -- useful on a machine
behind a restrictive egress policy, and as a regression check after editing the
scoring rules.

The set deliberately includes one of each edge case: an expired tender, a
below-threshold tender, an Arabic notice, a national-only notice, an
undated notice, and the same tender published on two portals.
"""

from __future__ import annotations

from datetime import date, timedelta

_today = date.today()


def _in(days: int) -> str:
    return (_today + timedelta(days=days)).isoformat()


def _ago(days: int) -> str:
    return (_today - timedelta(days=days)).isoformat()


SAMPLE_TENDERS: list[dict] = [
    {
        "id": "worldbank:FIXTURE-001",
        "title": "Consulting Services for Public Financial Management Reform "
                 "and Budget Execution Modernisation",
        "portal": "World Bank", "portal_key": "worldbank",
        "url": "https://projects.worldbank.org/en/projects-operations/procurement-detail/FIXTURE-001",
        "posted_date": _ago(6), "closing_date": _in(9),
        "estimated_value_usd": 2_400_000.0,
        "sector": "Public Financial Management",
        "description": "The Ministry of Finance seeks a consulting firm to provide "
                       "technical assistance for public financial management reform, "
                       "covering budget execution, treasury single account rollout, "
                       "institutional reform and capacity building.",
        "eligibility": "Open to international consulting firms.",
        "contact": "procurement@mof.gov.jo", "notice_type": "Request for Proposals (RFP)",
        "language": "en",
    },
    {
        # Same assignment, published on a second portal -> should be merged
        "id": "ungm:FIXTURE-001-DUP",
        "title": "Consulting Services for Public Financial Management Reform and "
                 "Budget Execution Modernization",
        "portal": "UNGM (UN agencies)", "portal_key": "ungm",
        "url": "https://www.ungm.org/Public/Notice/999001",
        "posted_date": _ago(5), "closing_date": _in(9),
        "estimated_value_usd": None, "sector": "Public Financial Management",
        "description": "UNDP Jordan seeks a firm for PFM reform technical assistance.",
        "eligibility": None, "contact": "UNDP", "notice_type": "Request for Proposals (RFP)",
        "language": "en",
    },
    {
        "id": "ted:FIXTURE-002",
        "title": "Technical Assistance for Digital Government Transformation "
                 "and e-Services Architecture, Jordan",
        "portal": "EU TED", "portal_key": "ted",
        "url": "https://ted.europa.eu/en/notice/-/detail/FIXTURE-002",
        "posted_date": _ago(18), "closing_date": _in(26),
        "estimated_value_usd": 1_150_000.0, "sector": "Digital Government",
        "description": "Advisory services covering digital transformation strategy, "
                       "e-government service design, enterprise architecture and "
                       "institutional capacity building for the Ministry of Digital Economy.",
        "eligibility": "Open to firms established in the EU and partner countries.",
        "contact": "EU Delegation to Jordan", "notice_type": "Contract notice - services",
        "language": "en",
    },
    {
        "id": "fcdo:FIXTURE-003",
        "title": "Monitoring, Evaluation and Learning Partner - Jordan Governance Programme",
        "portal": "UK FCDO / Find a Tender", "portal_key": "fcdo",
        "url": "https://www.find-tender.service.gov.uk/Notice/FIXTURE-003",
        "posted_date": _ago(40), "closing_date": _in(48),
        "estimated_value_usd": 3_800_000.0, "sector": "Governance",
        "description": "FCDO seeks a supplier to deliver monitoring and evaluation, "
                       "impact evaluation and learning services across its Jordan "
                       "governance and institutional reform portfolio.",
        "eligibility": None, "contact": "FCDO Commercial", "notice_type": "Services",
        "language": "en",
    },
    {
        # National-only -> flagged and penalised
        "id": "worldbank:FIXTURE-004",
        "title": "Supply and Installation of Laboratory Equipment, Ministry of Health",
        "portal": "World Bank", "portal_key": "worldbank",
        "url": "https://projects.worldbank.org/en/projects-operations/procurement-detail/FIXTURE-004",
        "posted_date": _ago(11), "closing_date": _in(21),
        "estimated_value_usd": 640_000.0, "sector": "Health",
        "description": "National Competitive Bidding. Participation is restricted to "
                       "national firms only, registered in Jordan.",
        "eligibility": "National firms only", "contact": "MoH Procurement Unit",
        "notice_type": "Invitation for Bids (IFB)", "language": "en",
    },
    {
        # Arabic notice -> included and flagged
        "id": "sfd:FIXTURE-005",
        "title": "إعلان طرح استشارات لمشروع تطوير قطاع المياه في الأردن",
        "portal": "Saudi Fund for Development", "portal_key": "sfd",
        "url": "https://www.sfd.gov.sa/ar/tenders/fixture-005",
        "posted_date": _ago(3), "closing_date": _in(33),
        "estimated_value_usd": 900_000.0, "sector": "Energy & Water",
        "description": "الصندوق السعودي للتنمية يعلن عن طرح خدمات استشارية لمشروع "
                       "تطوير قطاع المياه في المملكة الأردنية الهاشمية.",
        "eligibility": None, "contact": None, "notice_type": "SFD announcement",
        "language": "ar",
    },
    {
        # Expired -> filtered out
        "id": "ebrd:FIXTURE-006",
        "title": "Feasibility Study for Amman Urban Transport Corridor",
        "portal": "EBRD", "portal_key": "ebrd",
        "url": "https://www.ebrd.com/work-with-us/procurement/fixture-006",
        "posted_date": _ago(120), "closing_date": _ago(20),
        "estimated_value_usd": 480_000.0, "sector": "Infrastructure",
        "description": "Feasibility study and transaction advisory for a bus rapid "
                       "transit corridor.",
        "eligibility": None, "contact": None, "notice_type": "EBRD procurement notice",
        "language": "en",
    },
    {
        # Below the USD 100k threshold -> filtered out
        "id": "giz:FIXTURE-007",
        "title": "Short-term Trainer for Workshop Facilitation, GIZ Jordan",
        "portal": "GIZ", "portal_key": "giz",
        "url": "https://www.giz.de/en/mediacenter/fixture-007.html",
        "posted_date": _ago(2), "closing_date": _in(12),
        "estimated_value_usd": 35_000.0, "sector": "Education",
        "description": "Facilitation of a two-day workshop.",
        "eligibility": None, "contact": None, "notice_type": "GIZ tender", "language": "en",
    },
    {
        # No deadline published -> kept and flagged
        "id": "isdb:FIXTURE-008",
        "title": "General Procurement Notice - Jordan Renewable Energy and "
                 "Water Efficiency Programme",
        "portal": "IsDB", "portal_key": "isdb",
        "url": "https://www.isdb.org/procurement/fixture-008",
        "posted_date": _ago(9), "closing_date": None,
        "estimated_value_usd": None, "sector": "Energy & Water",
        "description": "General Procurement Notice announcing forthcoming consulting "
                       "and works packages under an IsDB-financed programme.",
        "eligibility": None, "contact": "IsDB Procurement", "notice_type": "General Procurement Notice",
        "language": "en",
    },
    {
        "id": "ungm:FIXTURE-009",
        "title": "Institutional Capacity Assessment and Organisational Review, UNICEF Jordan",
        "portal": "UNGM (UN agencies)", "portal_key": "ungm",
        "url": "https://www.ungm.org/Public/Notice/999009",
        "posted_date": _ago(1), "closing_date": _in(6),
        "estimated_value_usd": None, "sector": "Social Protection",
        "description": "UNICEF Jordan requires a consulting firm to conduct an "
                       "institutional capacity assessment and organisational review "
                       "of a national social protection agency, including business "
                       "process mapping and a reform roadmap.",
        "eligibility": None, "contact": "UNICEF Jordan", "notice_type": "Request for Proposals (RFP)",
        "language": "en",
    },
]
