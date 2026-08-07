"""Lead model + JSON persistence.

Every lead carries the fields from the spec plus arbitrary custom fields.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .knowledge import DATA_DIR

DATA_FILE = DATA_DIR / "leads.json"

OUTREACH_STATUSES = [
    "New",
    "Researching",
    "Classified",
    "Contacted",
    "Replied",
    "Meeting",
    "Converted",
    "Dead",
]

BASE_FIELDS = [
    "id", "contact", "organisation", "country", "website", "email", "role",
    "industry", "business_model", "lead_class", "source", "evidence",
    "notes", "created_at", "outreach_status", "next_action", "next_action_date",
    "email_history", "custom",
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def blank_lead() -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "contact": "",
        "organisation": "",
        "country": "",
        "website": "",
        "email": "",
        "role": "",
        "industry": "",
        "business_model": "",
        "lead_class": "",
        "source": "Manual",
        "evidence": "",
        "notes": "",
        "created_at": _now(),
        "outreach_status": "New",
        "next_action": "",
        "next_action_date": "",
        "email_history": [],
        "custom": {},
    }


def load_leads() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [ensure_fields(l) for l in raw]


def ensure_fields(lead: dict) -> dict:
    blank = blank_lead()
    merged = deepcopy(blank)
    for k, v in lead.items():
        merged[k] = v
    return merged


def save_leads(leads: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_lead(lead: dict) -> dict:
    leads = load_leads()
    leads.append(ensure_fields(lead))
    save_leads(leads)
    return lead


def update_lead(lead_id: str, changes: dict) -> dict | None:
    leads = load_leads()
    for i, lead in enumerate(leads):
        if lead["id"] == lead_id:
            merged = ensure_fields(lead)
            for k, v in changes.items():
                merged[k] = v
            leads[i] = merged
            save_leads(leads)
            return merged
    return None


def delete_lead(lead_id: str) -> bool:
    leads = load_leads()
    remaining = [l for l in leads if l["id"] != lead_id]
    if len(remaining) == len(leads):
        return False
    save_leads(remaining)
    return True


def get_lead(lead_id: str) -> dict | None:
    for lead in load_leads():
        if lead["id"] == lead_id:
            return lead
    return None


def add_email(lead_id: str, subject: str, body: str, direction: str = "out") -> dict | None:
    lead = get_lead(lead_id)
    if not lead:
        return None
    history = list(lead.get("email_history") or [])
    history.append({
        "direction": direction,
        "subject": subject,
        "body": body,
        "at": _now(),
    })
    return update_lead(lead_id, {"email_history": history})
