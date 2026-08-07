"""CircuCity Knowledge Layer.

Loads and persists the CircuCity knowledge base from the knowledge/ directory.
Every section is plain JSON, editable from the UI or directly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
DATA_DIR = BASE_DIR / "data"

# Ordered knowledge sections used by the classifier and the UI.
SECTIONS = [
    ("company", "company.json"),
    ("marketplace", "marketplace.json"),
    ("cira", "cira.json"),
    ("gavriel", "gavriel.json"),
    ("partner_program", "partner_program.json"),
    ("strategic_partnerships", "strategic_partnerships.json"),
    ("personas", "personas.json"),
]

SECTION_FILES = dict(SECTIONS)

# Lead classes recognised by the system (Lead Type, distinct from Offer).
LEAD_CLASSES = [
    "Seller",
    "CiraCustomer",
    "GavrielCustomer",
    "GrowthPartner",
    "StrategicPartner",
    "CapitalPartner",
    "BuyerPartner",
]

# Fix important export used elsewhere
SECTION_NAMES = [key for key, _ in SECTIONS]


def _read(key: str) -> dict:
    path = KNOWLEDGE_DIR / SECTION_FILES[key]
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load() -> dict:
    """Load the current knowledge base."""
    return {key: _read(key) for key, _ in SECTIONS}


def save_section(key: str, data: dict) -> None:
    """Persist an edited knowledge section."""
    path = KNOWLEDGE_DIR / SECTION_FILES[key]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def section_names() -> list[str]:
    return [key for key, _ in SECTIONS]


def tokenise(text: str) -> list[str]:
    """Lowercase-normalised token list (keeps useful characters)."""
    return re.sub(r"[^a-z0-9+#\.-]+", " ", text.lower()).split()


def flatten_text(data: dict) -> str:
    """Flatten a knowledge section into a searchable lowercase blob."""
    parts = []
    for v in data.values():
        if isinstance(v, list):
            parts.append(" ".join(str(x) for x in v))
        elif isinstance(v, dict):
            parts.append(flatten_text(v))
        else:
            parts.append(str(v))
    return " ".join(parts).lower()


def flatten_leaves(data: dict, prefix: str = "") -> dict:
    """Flatten nested data to leaf lists for file editing listings."""
    out = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_leaves(v, key))
        elif isinstance(v, list):
            out[key] = v
        else:
            out[key] = v
    return out