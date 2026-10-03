"""Per-source run records, and the note() channel.

Everything a run observes has to arrive somewhere a human will actually look.
stderr is not that place: the weekly run is unattended, and a message printed
there is gone by the time anyone opens the spreadsheet. So non-fatal
observations go through note(), which attaches them to the source's run record
and therefore into the Run status sheet next to the numbers they explain.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Literal

Status = Literal["ok", "empty", "error", "skipped", "blocked"]


@dataclass
class RunRecord:
    source_key: str
    name: str = ""
    platform: str = ""
    status: Status = "skipped"
    fetched: int = 0          # postings the source returned
    kept: int = 0             # survivors of dedupe, age and exclusion filters
    error: str = ""
    notes: list[str] = field(default_factory=list)
    endpoint: str = ""
    verified: object = "unconfirmed"
    duration_ms: int = 0

    def note(self, message: str) -> None:
        text = " ".join(str(message).split())
        if text and text not in self.notes:
            self.notes.append(text)

    def as_row(self) -> dict[str, object]:
        return {
            "source": self.source_key,
            "name": self.name,
            "platform": self.platform,
            "status": self.status,
            "fetched": self.fetched,
            "kept": self.kept,
            "verified": "true" if self.verified is True else str(self.verified),
            "endpoint": self.endpoint,
            "error": self.error,
            "notes": " | ".join(self.notes),
            "ms": self.duration_ms,
        }


class RunLog:
    """Collects the records for one scan."""

    def __init__(self) -> None:
        self.started_at = _dt.datetime.now(_dt.timezone.utc)
        self._records: dict[str, RunRecord] = {}

    def record(self, source_key: str, **kwargs: object) -> RunRecord:
        rec = self._records.get(source_key)
        if rec is None:
            rec = RunRecord(source_key=source_key)
            self._records[source_key] = rec
        for key, value in kwargs.items():
            setattr(rec, key, value)
        return rec

    def note(self, source_key: str, message: str) -> None:
        """Attach a non-fatal observation to a source's run record.

        Creates the record if the source has not been reached yet, so an
        observation made before or instead of a fetch is never lost.
        """
        self._records.setdefault(source_key, RunRecord(source_key=source_key)).note(message)

    def get(self, source_key: str) -> RunRecord:
        return self._records.setdefault(source_key, RunRecord(source_key=source_key))

    @property
    def records(self) -> list[RunRecord]:
        return sorted(self._records.values(), key=lambda r: r.source_key)

    def totals(self) -> dict[str, int]:
        """Counts over real sources only.

        Run-level messages are recorded against a "__run__" pseudo-source so
        they reach the sheet, but counting it as an employer makes the report
        claim more sources than sources.yaml contains.
        """
        real = [r for r in self._records.values() if not r.source_key.startswith("__")]
        by_status = lambda status: sum(1 for r in real if r.status == status)  # noqa: E731
        return {
            "sources": len(real),
            "ok": by_status("ok"),
            "empty": by_status("empty"),
            "error": by_status("error"),
            "blocked": by_status("blocked"),
            "skipped": by_status("skipped"),
            "attempted": by_status("ok") + by_status("empty") + by_status("error") + by_status("blocked"),
            "fetched": sum(r.fetched for r in real),
            "kept": sum(r.kept for r in real),
        }
