"""Loading the candidate profile.

The YAML file is the seed; once the app has run, the database copy is
authoritative so Settings can edit weights without a deploy. This module owns
the loading and the validation, and refuses a profile that would silently
misbehave — a typo in a weight should fail loudly at boot, not quietly change
what Fadi sees in the morning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[2] / "profiles" / "default_profile.yaml"
)


class ProfileError(ValueError):
    """The profile is malformed in a way that would corrupt scoring."""


def load_profile(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else DEFAULT_PROFILE_PATH
    if not path.exists():
        raise ProfileError(f"Profile not found at {path}")
    with path.open(encoding="utf-8") as handle:
        profile = yaml.safe_load(handle)
    if not isinstance(profile, dict):
        raise ProfileError(f"Profile at {path} did not parse to a mapping")
    validate_profile(profile)
    return profile


def validate_profile(profile: dict[str, Any]) -> None:
    """Fail loudly on the mistakes that would otherwise be invisible."""
    if not profile.get("signals"):
        raise ProfileError("Profile defines no signals — every job would score 0")

    seen: set[str] = set()
    for rule in profile["signals"] + list(profile.get("exclusions") or []):
        rule_id = rule.get("id")
        if not rule_id:
            raise ProfileError(f"Rule without an id: {rule!r}")
        if rule_id in seen:
            raise ProfileError(f"Duplicate rule id {rule_id!r}")
        seen.add(rule_id)
        if not (rule.get("keywords") or rule.get("keywords_ar")):
            raise ProfileError(f"Rule {rule_id!r} has no keywords and can never fire")

    for rule in profile["signals"]:
        weight = rule.get("weight")
        if not isinstance(weight, int) or weight == 0:
            raise ProfileError(
                f"Signal {rule['id']!r} needs a non-zero integer weight, got {weight!r}"
            )

    thresholds = profile.get("thresholds", {})
    if thresholds.get("moderate", 0) >= thresholds.get("strong", 100):
        raise ProfileError("thresholds.moderate must be below thresholds.strong")
