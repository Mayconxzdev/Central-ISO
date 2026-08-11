from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "target", "node_modules"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".xlsx", ".db", ".sqlite", ".lock"}

PATTERNS = {
    "private IPv4": re.compile(r"(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"),
    "removed corporate/third-party marker": re.compile(
        r"\b(?:" + "|".join(["Ves" + "per", "Vent " + "Rio", "Petro" + "bras", "Petro" + "net", "MEL" + "FEX", "MACCO" + "MEVAP", "PROTECTION " + "EX"]) + r")\b",
        re.I,
    ),
    "OpenAI-like secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub PAT-like secret": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}

findings: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in IGNORE_DIRS for part in path.parts) or path.suffix.lower() in BINARY_SUFFIXES:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{path.relative_to(ROOT)}:{line}: {label}: {match.group(0)}")

if findings:
    print("Public-safety scan failed:")
    print("\n".join(findings))
    raise SystemExit(1)
print("Public-safety scan passed.")
