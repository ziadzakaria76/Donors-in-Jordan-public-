"""Configuration and profile loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config.yml"
PROFILE_DIR = ROOT / "profiles"


class Config:
    def __init__(self, data: dict, profile: dict):
        self.data = data
        self.profile = profile

    # --- plumbing -----------------------------------------------------------
    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @staticmethod
    def env_list(name: str) -> list[str]:
        return [v.strip() for v in (os.environ.get(name) or "").split(",") if v.strip()]

    # --- frequently used ----------------------------------------------------
    @property
    def output_dir(self) -> Path:
        return Path(os.environ.get("MONITOR_OUTPUT_DIR") or self.get("output.dir", "output"))

    @property
    def db_path(self) -> Path:
        return Path(os.environ.get("MONITOR_DB_PATH") or self.get("state.db_path", "seen_tenders.db"))

    @property
    def enabled_portals(self) -> list[str]:
        portals = self.get("portals", {}) or {}
        return [name for name, cfg in portals.items() if (cfg or {}).get("enabled", True)]

    def portal_cfg(self, name: str) -> dict:
        return (self.get("portals", {}) or {}).get(name) or {}

    @property
    def included_link_types(self) -> list[str]:
        return list(self.get("scope.include_link_types", ["inside_syria"]))


def load_profile(key: str = "syria", directory: Optional[Path] = None) -> dict:
    path = (directory or PROFILE_DIR) / f"{key}.yml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config(path: Optional[Path] = None) -> Config:
    cfg_path = Path(path or os.environ.get("MONITOR_CONFIG") or DEFAULT_CONFIG)
    with open(cfg_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    profile = load_profile(data.get("profile", "syria"))
    return Config(data, profile)
