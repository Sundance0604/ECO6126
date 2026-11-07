from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from zoneinfo import ZoneInfo

from .market import ROOT


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def source_hashes():
    names = ["natural_consumption_HCtrading.py", "Research_Proposal_ZH.pdf"]
    names += [p.name for p in sorted(ROOT.glob("*.jpg"))]
    names += [p.relative_to(ROOT).as_posix() for folder in ("src", "scripts", "analysis", "tests")
              for p in sorted((ROOT / folder).glob("*.py"))]
    return {name: digest(ROOT / name) for name in names}


def model_version():
    files = ["natural_consumption_HCtrading.py", "src/market.py", "src/metrics.py"]
    return "v1.5-A-raw-" + canonical_hash({p: digest(ROOT / p) for p in files})[:12]


def environment():
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas")}}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
