"""LLM-based classification refinement via Groq.

The keyword engine is fast and free, but real-life research text often
matches no keywords. When a classification comes up weak, we ask the LLM to
decide the lead class and fit scores against the CircuCity knowledge base.
"""

from __future__ import annotations

import json
import re

from .ai_writer import chat_completion
from .knowledge import LEAD_CLASSES, load

DIMENSIONS = ["marketplace", "cira", "gavriel", "partner", "strategic", "capital"]

DESCRIPTIONS = {
    "Seller": "a second-hand / vintage / sustainable resale store or brand",
    "CiraCustomer": "an ecommerce / online brand that could subscribe to Cira",
    "GavrielCustomer": "an inventory-heavy resale business that needs listing automation",
    "GrowthPartner": "a sales/BD/AI/SaaS/ecommerce person who could sell for CircuCity",
    "StrategicPartner": "an organisation in the circular economy / sustainability space",
    "CapitalPartner": "an investor or fund focused on impact / climate",
    "BuyerPartner": "media, creator, community or newsletter that reaches buyers",
}


def _kb_context(kb: dict) -> str:
    company = (kb.get("company") or {}).get("company") or {}
    marketplace = kb.get("marketplace") or {}
    cira = kb.get("cira") or {}
    gavriel = kb.get("gavriel") or {}
    partner = kb.get("partner_program") or {}
    strategic = kb.get("strategic_partnerships") or {}

    lines = [
        f"CIRCUCITY: {company.get('name', 'CircuCity')} - {company.get('mission', '')} "
        f"Targets: {company.get('countries', '')}.",
        f"MARKETPLACE: second-hand/vintage stores and sustainable brands as sellers; "
        f"CTA: {marketplace.get('cta', 'list your store')}.",
        f"CIRA: AI sales + support for Shopify/WooCommerce/ecommerce brands; "
        f"CTA: {cira.get('cta', 'book a demo')}.",
        f"GAVRIEL: AI listing automation for inventory-heavy resellers; "
        f"CTA: {gavriel.get('cta', 'see a demo listing')}.",
        f"PARTNER: commission for B2B/SaaS sales, marketing, BD, ecommerce specialists; "
        f"CTA: {partner.get('cta', 'join the partner program')}.",
        f"STRATEGIC: circular-economy organisations, municipalities, networks - distribution, "
        f"credibility, joint campaigns. CTA: {strategic.get('cta', 'explore a partnership')}.",
        "CAPITAL: impact investors, green-tech funds, grants, ESG programmes.",
    ]
    desc = "; ".join(f"'{k}': {v}" for k, v in DESCRIPTIONS.items())
    return "\n".join(lines) + "\n\nPERSONA TYPES - choose exactly one of: " + desc


def _system_prompt(kb: dict) -> str:
    return (
        "You are CircuCity's lead-intelligence analyst. You classify a prospect "
        "against CircuCity's knowledge base and return ONLY strict JSON (no markdown).\n\n"
        + _kb_context(kb)
    )


USER_TEMPLATE = """PROSPECT:
{corpus}

Decide the single best persona, score fit 0-100 for each of the six dimensions
(marketplace, cira, gavriel, partner, strategic, capital), and give a reason,
recommended offer, secondary offer, angle and a concrete CTA.

Return ONLY JSON:
{{
  "lead_class": "one of {lead_classes}",
  "fits": {{"marketplace": 0-100, "cira": 0-100, "gavriel": 0-100, "partner": 0-100, "strategic": 0-100, "capital": 0-100}},
  "reason": "one clear sentence why",
  "offer": "recommended offer for this lead",
  "secondary": "secondary opportunity or empty string",
  "angle": "the messaging angle",
  "cta": "the call to action",
  "facts": ["2-3 personalisation facts learned from the profile"]
}}
Do not fabricate facts. If the text is clearly not a researched profile (e.g.
'LinkedIn bio', a URL, an empty label), return lead_class 'GrowthPartner', all
fits 0, empty facts, and reason 'insufficient evidence'."""


def _parse(text: str) -> dict | None:
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    try:
        start, end = text.index("{"), text.rindex("}")
        data = json.loads(text[start:end + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    return data


def _validate(data: dict) -> dict | None:
    cls = data.get("lead_class")
    if cls not in LEAD_CLASSES:
        return None
    fits = data.get("fits")
    if not isinstance(fits, dict):
        return None
    fits = {d: max(0, min(100, int(fits.get(d, 0)))) for d in DIMENSIONS}
    data["fits"] = fits
    data["facts"] = list(data.get("facts") or [])[:4]
    return data


def llm_classify(corpus: str, kb: dict, api_key: str, model: str) -> dict | None:
    if not api_key or not corpus.strip():
        return None
    try:
        user = USER_TEMPLATE.replace("{corpus}", corpus[:3000]) \
            .replace("{lead_classes}", ", ".join(LEAD_CLASSES))
        text = chat_completion(api_key, model, _system_prompt(kb), user)
    except Exception:
        return None
    data = _parse(text or "")
    if data is None:
        return None
    return _validate(data)