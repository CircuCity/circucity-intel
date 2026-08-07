"""CSV lead import helpers."""

from __future__ import annotations

import io

import pandas as pd

from .classifier import classify
from .leads import add_lead, blank_lead

# Friendly header names -> lead field
COLUMN_MAP = {
    "contact": "contact", "name": "contact", "person": "contact",
    "organisation": "organisation", "org": "organisation", "company": "organisation",
    "country": "country",
    "website": "website", "url": "website", "site": "website",
    "email": "email",
    "role": "role", "job title": "role", "title": "role",
    "industry": "industry", "sector": "industry",
    "business model": "business_model", "business_model": "business_model",
    "evidence": "evidence", "notes": "evidence", "research": "evidence", "bio": "evidence",
    "source": "source",
}

TEMPLATE_COLUMNS = ["contact", "organisation", "country", "website", "email",
                    "role", "industry", "business_model", "evidence", "source"]


def template_csv() -> str:
    df = pd.DataFrame([{
        "contact": "Anna Muller",
        "organisation": "AM Growth",
        "country": "Germany",
        "website": "https://amgrowth.example",
        "email": "anna@amgrowth.example",
        "role": "Growth Consultant",
        "industry": "Ecommerce growth",
        "business_model": "Consultancy for Shopify brands",
        "evidence": "Works with Shopify brands, 8 years ecommerce, posts about CRO.",
        "source": "LinkedIn",
    }])
    return df.to_csv(index=False)


def parse_csv(upload) -> tuple[list[dict], list[str]]:
    """Parse an uploaded CSV into lead dicts. Returns (leads, warnings)."""
    raw = pd.read_csv(io.BytesIO(upload.getvalue()))
    warnings = []

    normalized = raw.copy()
    normalized.columns = [str(c).strip().lower() for c in raw.columns]

    leads = []
    for _, row in normalized.iterrows():
        lead = blank_lead()
        for col in normalized.columns:
            target = COLUMN_MAP.get(col)
            if target and pd.notna(row[col]) and str(row[col]).strip():
                lead[target] = str(row[col]).strip()
        if not any([lead["contact"], lead["organisation"], lead["evidence"]]):
            warnings.append(f"Row skipped (no contact/organisation/evidence): {dict(row)}")
            continue
        leads.append(lead)

    if len(leads) == 0:
        warnings.append("No usable rows found. Expected columns: "
                        + ", ".join(TEMPLATE_COLUMNS))
    return leads, warnings


def rows_to_leads(df: pd.DataFrame) -> list[dict]:
    """Convert an (edited) preview dataframe back to lead dicts."""
    leads = []
    for _, row in df.iterrows():
        lead = blank_lead()
        for col in df.columns:
            target = COLUMN_MAP.get(str(col).strip().lower())
            if target and pd.notna(row[col]) and str(row[col]).strip():
                lead[target] = str(row[col]).strip()
        if any([lead["contact"], lead["organisation"], lead["evidence"]]):
            leads.append(lead)
    return leads


def import_and_classify(leads: list[dict], prefer_ai: bool) -> list[dict]:
    """Classify each lead, save, and return the resulting lead dicts."""
    saved = []
    for lead in leads:
        cls = classify(lead, prefer_ai=prefer_ai)
        if cls:
            lead["lead_class"] = cls.lead_class
        result = add_lead(lead)
        saved.append(result)
    return saved