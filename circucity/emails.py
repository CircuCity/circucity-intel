"""Personalised outreach email generation.

Templates are keyed by lead class and filled with the classification's
recommended offer / angle / CTA plus personalisation facts from research.
"""

from __future__ import annotations

import re

from .knowledge import load

TEMPLATES = {
    "Seller": {
        "subject": "Your {org} on CircuCity Marketplace",
        "body": """Hi {first},

I came across {org} while researching circular retail in {country} — the way you curate {fact_short} stands out.

CircuCity connects second-hand and vintage stores with buyers across Europe, and helps you list faster with AI. Pre-loved stock stops being a time sink and becomes your best channel.

{angle}

Would you be open to a 15-minute chat about listing {org} and what AI-assisted listings would look like for your inventory?

{cta} — reply and I'll send the details.

Best,
{signer}""",
    },
    "CiraCustomer": {
        "subject": "Never miss another customer on {org}",
        "body": """Hi {first},

{org} clearly invests in the customer experience online. Most stores lose revenue every day to slow support and abandoned carts.

Cira is an AI agent that sells, supports and recovers carts for Shopify/WooCommerce stores — trained on your products, live 24/7.

{angle}

Worth a 15-minute demo? {cta}.

Best,
{signer}""",
    },
    "GavrielCustomer": {
        "subject": "Automating {org}'s listing backlog",
        "body": """Hi {first},

{org} handles a lot of unique inventory — exactly the kind of work that eats hours.

Gavriel turns a photo into a complete, publishable listing in seconds, so your team stops writing product descriptions by hand.

{angle}

Happy to show a real demo listing generated from one of your items. {cta}.

Best,
{signer}""",
    },
    "GrowthPartner": {
        "subject": "A partner offer for {first}",
        "body": """Hi {first},

You work with {industry_focus} — the exact audience CircuCity's products serve.

We're building the partner network for Cira (AI sales & support for ecommerce) and Gavriel (AI listing automation) across Europe, with a commission on every acquisition you bring in.

{angle}

15-minute partnership conversation this week? {cta}.

Best,
{signer}""",
    },
    "StrategicPartner": {
        "subject": "Circular commerce infrastructure — a fit for {org}?",
        "body": """Hi {first},

CircuCity is building the structured circular-economy infrastructure: a marketplace connecting second-hand stores and consumers, with CO₂ impact tracking and EcoTokens rewards.

{org}'s work around {fact_short} aligns directly with what we're building, and there are several ways to collaborate — member benefits, merchant introductions, joint circularity programmes or research.

{angle}

Could we explore what a partnership would look like? {cta}.

Best,
{signer}""",
    },
    "CapitalPartner": {
        "subject": "CircuCity — structured circular commerce, {country} and beyond",
        "body": """Hi {first},

CircuCity operates as circular-commerce infrastructure: a marketplace for second-hand stores and consumers, monetised through fees and AI SaaS (Cira, Gavriel), with measurable CO₂ impact.

{org} focuses on {fact_short} — we're raising to expand across {country} and Europe and would value a conversation.

{angle}

Open to an introductory call? {cta}.

Best,
{signer}""",
    },
    "BuyerPartner": {
        "subject": "Circular shopping for {audience}",
        "body": """Hi {first},

Your {audience} care about shopping differently — but second-hand still often means scattered marketplaces and uncertain sellers.

CircuCity is a structured circular marketplace: verified vintage and second-hand stores, CO₂ saved on every purchase, EcoTokens rewards, even swapping.

{angle}

Would a partnership be interesting — joint campaign, featured collection or a rewards tie-in? {cta}.

Best,
{signer}""",
    },
}


def _first_name(contact: str) -> str:
    return (contact.strip().split()[0] if contact.strip() else "there")


def _fact_short(lead: dict, classification: dict) -> str:
    """Pick the strongest one-line fact about the lead for personalisation."""
    if lead.get("industry"):
        return lead["industry"]
    if lead.get("business_model"):
        return lead["business_model"]
    if classification and classification.get("evidence_signals"):
        ev = classification["evidence_signals"][0]
        return ev.split(":", 1)[-1].strip()
    if lead.get("organisation"):
        return lead["organisation"]
    return "your work"


def _fill(template: str, lead: dict, classification: dict | None, signer: str) -> str:
    angle = (classification or {}).get("recommended_angle") or ""
    cta = (classification or {}).get("recommended_cta") or "Let's talk"
    focus = lead.get("industry") or lead.get("business_model") or "ecommerce"
    audience = lead.get("industry") or "your audience"

    values = {
        "first": _first_name(lead.get("contact", "")),
        "org": lead.get("organisation") or "your store",
        "country": lead.get("country") or "Europe",
        "fact_short": _fact_short(lead, classification),
        "industry_focus": focus,
        "audience": audience,
        "angle": angle,
        "cta": cta,
        "signer": signer,
    }
    out = template
    for key, val in values.items():
        out = out.replace("{" + key + "}", val)
    # Remove any placeholders that did not resolve
    out = re.sub(r"\{[a-z_]+\}", "", out)
    return out


def generate_email(lead: dict, classification: dict | None, signer: str = "The CircuCity team") -> tuple[str, str]:
    """Return (subject, body). Falls back to the most fitting template."""
    cls = classification.get("lead_class") if classification else ""
    template = TEMPLATES.get(cls)
    if not template:
        cls = "GrowthPartner"
        template = TEMPLATES[cls]
    subject = _fill(template["subject"], lead, classification, signer)
    body = _fill(template["body"], lead, classification, signer)
    return subject, body


def subject_line(lead: dict, classification: dict | None, signer: str = "The CircuCity team") -> str:
    subject, _ = generate_email(lead, classification, signer)
    return subject
