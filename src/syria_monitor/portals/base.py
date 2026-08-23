"""Portal base classes.

Every portal exposes exactly fetch_tenders() -> list[dict] returning raw
records. Normalisation, the country gate and error handling live here, so:

  * a portal cannot skip the country check by omission -- it never runs it;
  * a failing portal never aborts the run: it is skipped, the reason is
    captured, and it is reported as unavailable with the URL to check by hand;
  * --capture works for every HTML portal, including ones with custom fetch
    logic, because capture() goes through the same fetch_page() the run uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..dates import parse_date
from ..extraction import ExtractionResult, diagnose, extract
from ..fetch import Fetcher, TransportError
from ..gate import GateStats
from ..models import Tender


@dataclass
class PortalOutcome:
    name: str
    label: str
    url: str
    tenders: list[Tender] = field(default_factory=list)
    available: bool = True
    error: Optional[str] = None
    diagnosis: Optional[str] = None
    stats: GateStats = field(default_factory=GateStats)
    layer: Optional[str] = None
    quality: Optional[float] = None
    skipped_reason: Optional[str] = None

    @property
    def status_line(self) -> str:
        if self.skipped_reason:
            return f"{self.label}: skipped -- {self.skipped_reason}"
        if not self.available:
            return f"{self.label}: UNAVAILABLE -- {self.error} ({self.url})"
        return f"{self.label}: ok -- {len(self.tenders)} kept of {self.stats.seen} fetched"


class BasePortal:
    name = "base"
    label = "Base"
    url = ""
    is_html = False
    requires_key: Optional[str] = None      # env var name, when the portal needs one

    def __init__(self, cfg: dict, profile: dict, fetcher: Fetcher, gate):
        self.cfg = cfg or {}
        self.profile = profile
        self.fetcher = fetcher
        self.gate = gate

    # -- subclasses implement this and nothing about country filtering --------
    def fetch_tenders(self) -> list[dict]:
        raise NotImplementedError

    def unavailable_reason(self) -> Optional[str]:
        """Non-fatal reason to skip, e.g. a missing API key."""
        return None

    # -- normalisation --------------------------------------------------------
    def to_tender(self, record: dict, link_type: str, delivery: Optional[str]) -> Tender:
        from ..money import parse_value

        posted = parse_date(record.get("posted_date"))
        closing = parse_date(record.get("closing_date"))
        value = parse_value(record.get("value_text") or record.get("value"), posted, self.profile)

        tender = Tender(
            id=str(record.get("id") or record.get("url") or record.get("title", ""))[:200],
            title=str(record.get("title") or "").strip(),
            portal=self.name,
            url=record.get("url"),
            posted_date=posted,
            closing_date=closing,
            sector=record.get("sector"),
            description=record.get("description"),
            eligibility=record.get("eligibility"),
            contact=record.get("contact"),
            notice_type=record.get("notice_type"),
            language=record.get("language") or _guess_language(record),
            delivery_country=delivery or record.get("delivery_country"),
            syria_link_type=link_type,
            raw_value=value.raw,
            raw_currency=value.currency,
            value_flags=list(value.flags),
            country_fields={k: v for k, v in record.items()
                            if k in self.gate.matcher.field_names() and v not in (None, "")},
        )
        # estimated_value_usd is set only where the currency really is USD.
        # Local-currency amounts are reported as published; see money.py for why
        # SYP is never converted.
        if value.amount is not None and (value.currency or "USD").upper() == "USD":
            tender.estimated_value_usd = value.amount
        if value.amount is not None and (value.currency or "USD").upper() != "USD":
            tender.add_flag(f"value_{value.currency}_{value.amount:g}")
        if closing is None:
            tender.add_flag("deadline_not_published")
        for f in value.flags:
            tender.add_flag(f)
        return tender

    # -- the run --------------------------------------------------------------
    def collect(self) -> PortalOutcome:
        """FINAL. Do not override in a portal module: this is where the shared
        country gate is applied, and overriding it would let a portal skip it."""
        outcome = PortalOutcome(name=self.name, label=self.label, url=self.url)

        reason = self.unavailable_reason()
        if reason:
            outcome.skipped_reason = reason
            return outcome

        try:
            records = self.fetch_tenders()
        except TransportError as exc:
            outcome.available = False
            outcome.error = str(exc)
            outcome.diagnosis = "transport: wrong URL or blocked host"
            return outcome
        except Exception as exc:                      # never abort the whole run
            outcome.available = False
            outcome.error = f"{type(exc).__name__}: {exc}"
            outcome.diagnosis = "portal module raised -- see traceback in --dry-run -v"
            return outcome

        for record in records:
            keep, link_type, delivery = self.gate.check(record, outcome.stats)
            if not keep:
                continue
            outcome.tenders.append(self.to_tender(record, link_type, delivery))
        outcome.layer = getattr(self, "_winning_layer", None)
        outcome.quality = getattr(self, "_winning_quality", None)
        return outcome

    # -- capture --------------------------------------------------------------
    def capture(self) -> list[tuple[str, str, int, Optional[ExtractionResult]]]:
        """Live pages for --capture. REST portals return their raw payload."""
        return []


def _guess_language(record: dict) -> str:
    blob = " ".join(str(record.get(k) or "") for k in ("title", "description"))
    arabic = sum(1 for ch in blob if "؀" <= ch <= "ۿ")
    return "ar" if arabic >= max(3, len(blob) * 0.05) else "en"


class HtmlPortal(BasePortal):
    """HTML portal driven by the extraction cascade.

    Subclasses provide pages() and row_to_record(); anything with custom fetch
    logic overrides fetch_page(), which keeps --capture working for it too.
    """

    is_html = True
    selectors: Optional[dict] = None
    anchor_pattern: Optional[str] = None

    def pages(self) -> list[tuple[str, str]]:
        return [("index", self.url)]

    def fetch_page(self, label: str, url: str) -> tuple[str, int]:
        response = self.fetcher.get(url)
        return response.text, response.status

    def row_to_record(self, row, page_url: str) -> dict:
        record = {
            "id": row.url or row.title,
            "title": row.title,
            "url": row.url or page_url,
            "description": row.text,
            "_safe_text_fields": ["title", "description"],
        }
        record.update({k: v for k, v in row.cells.items() if isinstance(v, (str, int, float))})
        if "deadline" in row.cells:
            record["closing_date"] = row.cells["deadline"]
        if "published" in row.cells:
            record["posted_date"] = row.cells["published"]
        if "value" in row.cells:
            record["value_text"] = row.cells["value"]

        # Rows from the class-independent layers carry their dates in prose
        # rather than in mapped cells. Anchor on a closing label -- never on the
        # first date-shaped text in the row, which is usually the publication
        # date -- and let the countdown guard void a match that sits behind
        # "expires in N days".
        if not record.get("closing_date"):
            from ..dates import find_labelled_date
            deadline = find_labelled_date(row.text)
            if deadline:
                record["closing_date"] = deadline.isoformat()
        if not record.get("value_text"):
            record["value_text"] = row.text
        return record

    def extract_page(self, html: str, url: str, status: int = 200) -> ExtractionResult:
        return extract(html, base_url=url, selectors=self.selectors,
                       anchor_pattern=self.anchor_pattern, status=status)

    def fetch_tenders(self) -> list[dict]:
        records: list[dict] = []
        for label, url in self.pages():
            html, status = self.fetch_page(label, url)
            result = self.extract_page(html, url, status)
            self._winning_layer = result.layer
            self._winning_quality = result.quality
            if not result.rows:
                raise RuntimeError(result.diagnosis or diagnose(html, status))
            for row in result.rows:
                records.append(self.row_to_record(row, url))
        return records

    def capture(self):
        captured = []
        for label, url in self.pages():
            try:
                html, status = self.fetch_page(label, url)
            except TransportError as exc:
                captured.append((label, "", 0, None))
                self._capture_error = str(exc)
                continue
            captured.append((label, html, status, self.extract_page(html, url, status)))
        return captured


class ApiPortal(BasePortal):
    """REST portal. Country filtering still happens in the shared gate: an API's
    own country parameter is a hint, never a guarantee."""

    is_html = False

    def raw_payload(self) -> Any:
        return None

    def capture(self):
        try:
            payload = self.raw_payload()
        except TransportError as exc:
            self._capture_error = str(exc)
            return []
        return [("api", str(payload)[:200000], 200, None)]
