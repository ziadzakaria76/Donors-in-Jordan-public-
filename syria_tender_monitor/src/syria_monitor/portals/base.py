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
    rendered_with_browser: bool = False
    browser_note: Optional[str] = None

    @property
    def status_line(self) -> str:
        if self.skipped_reason:
            return f"{self.label}: skipped -- {self.skipped_reason}"
        if not self.available:
            return f"{self.label}: UNAVAILABLE -- {self.error} ({self.url})"
        suffix = " [rendered in a browser]" if self.rendered_with_browser else ""
        # Counted here rather than left to the spreadsheet: "85 kept of 85" reads
        # as a portal working perfectly, and gives no hint that most of those
        # rows never named this country and were admitted on an inference.
        inferred = sum(1 for t in self.tenders
                       if any(f.startswith("country_inferred:") for f in t.flags))
        if inferred:
            suffix += f" ({inferred} country inferred)"
        return (f"{self.label}: ok -- {len(self.tenders)} kept of "
                f"{self.stats.seen} fetched{suffix}")


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
            # ",.0f" not "g": :g turns 1500000 into "1.5e+06", which is worse
            # than useless in a report a human reads to judge contract size.
            tender.add_flag(f"value_{value.currency}_{value.amount:,.0f}")
        if closing is None:
            tender.add_flag("deadline_not_published")
        # A COUNTRY THE PORTAL INFERRED IS NOT A COUNTRY THE PORTAL PUBLISHED.
        # gate.py reads the country FIELD as authoritative and consults text only
        # when no field exists, so a portal that writes a country in for a row
        # that never named one has manufactured the strongest signal the gate
        # has -- and every later check is bypassed. That can be the right call
        # (see ungm.row_to_record), but it must not be invisible: downstream,
        # country_fields shows the value and nothing shows where it came from.
        if record.get("country_inferred"):
            tender.add_flag(f"country_inferred:{record['country_inferred']}")
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
            return self._annotate(outcome)
        except Exception as exc:                      # never abort the whole run
            outcome.available = False
            outcome.error = f"{type(exc).__name__}: {exc}"
            outcome.diagnosis = "portal module raised -- see traceback in --dry-run -v"
            return self._annotate(outcome)

        for record in records:
            keep, link_type, delivery = self.gate.check(record, outcome.stats)
            if not keep:
                continue
            outcome.tenders.append(self.to_tender(record, link_type, delivery))
        return self._annotate(outcome)

    def _annotate(self, outcome: PortalOutcome) -> PortalOutcome:
        """Carry diagnostics onto every return path, failures included -- a
        portal that could not be read is exactly when the note explaining why
        matters most."""
        outcome.layer = getattr(self, "_winning_layer", None)
        outcome.quality = getattr(self, "_winning_quality", None)
        outcome.rendered_with_browser = getattr(self, "_used_browser", False)
        outcome.browser_note = getattr(self, "_browser_note", None)
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

    # auto: escalate to a browser only when the page is diagnosed as needing one
    # always: render every page   |   never: plain HTTP only
    BROWSER_MODES = ("auto", "always", "never")

    @property
    def browser_mode(self) -> str:
        mode = str(self.cfg.get("browser", "auto")).lower()
        return mode if mode in self.BROWSER_MODES else "auto"

    @staticmethod
    def needs_browser(diagnosis: Optional[str]) -> bool:
        """Only the two diagnoses a browser can actually fix.

        A genuine layout change or a transport error is not helped by rendering
        -- it needs a human to look at the page or fix the URL -- and launching
        Chromium for those wastes time and hides the real cause.
        """
        return bool(diagnosis) and diagnosis.startswith(("js_shell", "bot_wall"))

    def page_result(self, label: str, url: str) -> ExtractionResult:
        """Fetch, extract, and escalate to a rendered browser if that is what
        the page needs. Plain HTTP is always tried first."""
        from .. import browser as browser_mod

        if self.browser_mode == "always":
            html, status = self._render(url, browser_mod)
            if html is not None:
                return self.extract_page(html, url, status)

        html, status = self.fetch_page(label, url)
        result = self.extract_page(html, url, status)
        if result.rows or self.browser_mode == "never":
            return result

        diagnosis = result.diagnosis or diagnose(html, status)
        if not self.needs_browser(diagnosis):
            return result

        rendered, rendered_status = self._render(url, browser_mod)
        if rendered is None:
            return result
        retry = self.extract_page(rendered, url, rendered_status)
        if retry.rows:
            self._used_browser = True
            return retry
        return result

    def _render(self, url: str, browser_mod) -> tuple[Optional[str], int]:
        try:
            html, status = browser_mod.render(
                url,
                timeout_ms=int(self.cfg.get("browser_timeout_ms", 30000)),
                settle_ms=int(self.cfg.get("browser_settle_ms", 1500)),
                wait_for=self.cfg.get("browser_wait_for"),
            )
            return html, status
        except browser_mod.BrowserUnavailable as exc:
            # Never fatal: the portal reports what it could not do and the run
            # continues with the other nine.
            self._browser_note = str(exc)
            return None, 0

    def fetch_tenders(self) -> list[dict]:
        records: list[dict] = []
        for label, url in self.pages():
            result = self.page_result(label, url)
            self._winning_layer = result.layer
            self._winning_quality = result.quality
            if not result.rows:
                note = f" ({self._browser_note})" if getattr(self, "_browser_note", None) else ""
                raise RuntimeError((result.diagnosis or "no rows extracted") + note)
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
