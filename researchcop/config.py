"""Configuration: defaults, optional config.toml, command-line overrides."""
from __future__ import annotations

import copy
import tomllib
from pathlib import Path

DEFAULTS = {
    "paths": {"input": "input", "output": "output"},
    "models": {
        "review": "claude-opus-5-5",
        "verify": "claude-opus-5-5",
        "references": "claude-sonnet-5-5",
        "effort": "high",
    },
    "review": {
        "language": "de",
        "second_review": False,
        "verify_min_severity": 2,
        "code_execution": True,
        "web_search": False,
        "max_pdf_pages": 100,
    },
    "sources": {"check_dois": True, "crossref_search": True, "contact_email": ""},
    "run": {"workers": 4},
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config(dict):
    @property
    def root(self) -> Path:
        return Path(self["_root"])

    def path(self, key: str) -> Path:
        p = Path(self["paths"][key])
        return p if p.is_absolute() else self.root / p

    @property
    def out(self) -> Path:
        return self.path("output")

    def dir(self, name: str) -> Path:
        d = self.out / name
        d.mkdir(parents=True, exist_ok=True)
        return d


def load(config_file: str | None = None, root: str | None = None, overrides: dict | None = None) -> Config:
    root_path = Path(root or ".").resolve()
    data = DEFAULTS
    cfg_path = Path(config_file) if config_file else root_path / "config.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            data = _merge(data, tomllib.load(f))
    data = _merge(data, overrides or {})
    cfg = Config(data)
    cfg["_root"] = str(root_path)
    return cfg
