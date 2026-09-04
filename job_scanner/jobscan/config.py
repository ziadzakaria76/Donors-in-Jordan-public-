"""Configuration loading, and the lock that keeps the profile block frozen.

The profile block is frozen by rule, and a rule nothing checks is a rule that
decays. `profile_fingerprint()` hashes the canonical form of the block and
qa_check compares it against .profile.lock; editing any value -- including
max_age_days, the one most likely to be "just widened a bit" when a run comes
back thin -- turns the battery red.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = PROJECT_ROOT / "sources.yaml"
PROFILE_LOCK = PROJECT_ROOT / ".profile.lock"

# The scanner is polite by contract, not by configuration. A source file
# asking for a shorter gap is refused rather than quietly honoured.
MIN_DELAY_SECONDS = 1.5


class ConfigError(Exception):
    pass


def profile_fingerprint(profile: dict[str, Any]) -> str:
    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Config:
    def __init__(self, raw: dict[str, Any], path: Path):
        self.path = path
        self.profile: dict[str, Any] = raw.get("profile") or {}
        self.sources: list[dict[str, Any]] = raw.get("sources") or []
        self._validate()

    def _validate(self) -> None:
        if not self.profile:
            raise ConfigError(f"{self.path}: no profile block")
        for required in ("target", "max_age_days", "specialty", "shortlist_min_score"):
            if required not in self.profile:
                raise ConfigError(f"{self.path}: profile is missing '{required}'")
        if not isinstance(self.profile["max_age_days"], int) or self.profile["max_age_days"] <= 0:
            raise ConfigError(f"{self.path}: max_age_days must be a positive integer")

        seen: set[str] = set()
        for source in self.sources:
            key = source.get("key")
            if not key:
                raise ConfigError(f"{self.path}: a source has no key")
            if key in seen:
                raise ConfigError(f"{self.path}: duplicate source key {key!r}")
            seen.add(key)
            verified = source.get("verified", "unconfirmed")
            if verified not in (True, "url-confirmed", "unconfirmed"):
                raise ConfigError(
                    f"{self.path}: source {key!r} has verified={verified!r}; allowed "
                    "values are true, 'url-confirmed', 'unconfirmed'"
                )
            # An enabled source must at minimum have had its URL confirmed.
            if source.get("enabled") and verified == "unconfirmed":
                raise ConfigError(
                    f"{self.path}: source {key!r} is enabled but nothing about it "
                    "has been confirmed"
                )

    @property
    def max_age_days(self) -> int:
        return int(self.profile["max_age_days"])

    @property
    def shortlist_min_score(self) -> int:
        return int(self.profile["shortlist_min_score"])

    def fingerprint(self) -> str:
        return profile_fingerprint(self.profile)

    def select(self, only: list[str] | None) -> list[dict[str, Any]]:
        """Sources to attempt this run.

        `--only` names sources explicitly and overrides the enabled flag, so a
        disabled source can be probed without first being enabled -- which is
        the order the discovery work actually happens in. It does not override
        permanently_disabled.
        """
        if only:
            wanted = [k.strip() for k in only if k.strip()]
            known = {s["key"] for s in self.sources}
            unknown = [k for k in wanted if k not in known]
            if unknown:
                raise ConfigError(f"unknown source key(s): {', '.join(unknown)}")
            return [s for s in self.sources if s["key"] in wanted]
        return [s for s in self.sources if s.get("enabled")]


def load(path: str | Path | None = None) -> Config:
    resolved = Path(path) if path else DEFAULT_SOURCES
    if not resolved.exists():
        raise ConfigError(f"no such config file: {resolved}")
    with resolved.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ConfigError(f"{resolved}: expected a mapping at the top level")
    return Config(raw, resolved)
