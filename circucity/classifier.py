"""Classification, scoring and matching engine.

For a given lead the engine:
  1. Detects the Lead Type from the editable persona definitions.
  2. Scores fit across Marketplace / Cira / Gavriel / Partner / Strategic /
     Capital dimensions using knowledge-base signals.
  3. Picks the recommended offer, angle and CTA.
  4. Extracts evidence + personalisation facts.

Lead Type is separate from Offer, per the design.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .knowledge import load

DIMENSIONS = ["marketplace", "cira", "gavriel", "partner", "strategic", "capital"]

DIMENSION_LABELS = {
    "marketplace": "Marketplace",
    "cira": "Cira",
    "gavriel": "Gavriel",
    "partner": "Partner Program",
    "strategic": "Strategic",
    "capital": "Capital",
}

# knowledge section key -> (section, signals key)
PRODUCT_SIGNAL_KEYS = {
    "marketplace": ("marketplace", "signals"),
    "cira": ("cira", "signals"),
    "gavriel": ("gavriel", "signals"),
    "partner": ("partner_program", "signals"),
    "strategic": ("strategic_partnerships", "signals"),
}

# Non-product dimensions score against persona keywords
PERSONA_KEYWORDS = {
    "capital": "CapitalPartner",
}


@dataclass
class Classification:
    lead_class: str
    confidences: dict  # dimension -> fit %
    reason: str
    matched_persona: list[str]
    recommended_offer: str
    recommended_secondary: str
    recommended_angle: str
    recommended_cta: str
    evidence_signals: list[str]
    personalisation_facts: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _count_signals(text: str, signals: list[str]) -> tuple[int, list[str]]:
    norm = _normalise(text)
    found = [s for s in signals if s.lower() in norm]
    return len(found), found


def _score(text: str, signals: list[str]) -> float:
    n, _ = _count_signals(text, signals)
    if not signals:
        return 0.0
    return round(min(100.0, n / len(signals) * 100.0), 1)


def lead_corpus(lead: dict) -> str:
    """Build the searchable corpus for a lead from all its free text."""
    parts = [
        lead.get("contact", ""),
        lead.get("organisation", ""),
        lead.get("role", ""),
        lead.get("industry", ""),
        lead.get("business_model", ""),
        lead.get("evidence", ""),
        lead.get("notes", ""),
        lead.get("website", ""),
        lead.get("country", ""),
    ]
    custom = lead.get("custom") or {}
    for v in custom.values():
        parts.append(str(v))
    return " ".join(p for p in parts if p)


def detect_lead_class(corpus: str, kb: dict) -> tuple[str, float, list[str]]:
    personas = (kb.get("personas") or {}).get("personas") or {}
    norm = _normalise(corpus)
    best, best_score, best_hits = "GrowthPartner", -1.0, []
    for cls, spec in personas.items():
        keywords = list((spec or {}).get("keywords") or [])
        hits = [k for k in keywords if k.lower() in norm]
        score = len(hits) * 10 + sum(len(k) for k in hits) * 0.05
        if score > best_score:
            best, best_score, best_hits = cls, score, hits
    conf = round(min(100.0, best_score / 3.0), 1) if best_score > 0 else 0.0
    return best, conf, best_hits


def _dimension_signals(kb: dict, dim: str) -> list[str]:
    if dim in PRODUCT_SIGNAL_KEYS:
        sec, key = PRODUCT_SIGNAL_KEYS[dim]
        return list((kb.get(sec) or {}).get(key) or [])
    # Capital dimension: score against the CapitalPartner persona keywords
    personas = (kb.get("personas") or {}).get("personas") or {}
    spec = personas.get(PERSONA_KEYWORDS.get(dim, "")) or {}
    return list(spec.get("keywords") or [])


def _recommend(lead_class: str, scores: dict, kb: dict) -> tuple[str, str, str, str]:
    """Pick offer / secondary / angle / CTA from knowledge + fit scores."""
    m, c, g = scores["marketplace"], scores["cira"], scores["gavriel"]
    p = scores["partner"]
    s = scores["strategic"]
    cap = scores["capital"]

    products = {"Marketplace": m, "Cira": c, "Gavriel": g}
    ranked = sorted(products.items(), key=lambda kv: kv[1], reverse=True)

    if lead_class == "Seller":
        best = "Marketplace + Gavriel + Cira" if g >= 50 and c >= 40 else "Marketplace + Gavriel"
        secondary = "Cira subscription" if c >= 50 else ""
        angle = "Sell more pre-loved stock with less listing work"
        cta = (kb.get("marketplace") or {}).get("cta") or "List your store on CircuCity"
    elif lead_class == "GavrielCustomer":
        best = "Gavriel"
        secondary = "CircuCity Marketplace"
        angle = "Automate your unique-item listing workflow"
        cta = (kb.get("gavriel") or {}).get("cta") or "See a Gavriel demo"
    elif lead_class == "CiraCustomer":
        best = "Cira"
        secondary = "Gavriel referral"
        angle = "AI sales and support that never misses a customer"
        cta = (kb.get("cira") or {}).get("cta") or "Book a Cira demo"
    elif lead_class == "GrowthPartner":
        best = "Cira partnership"
        secondary = "Gavriel referrals"
        angle = "Commission on a product your clients already need"
        cta = (kb.get("partner_program") or {}).get("cta") or "Apply to the partner program"
    elif lead_class == "StrategicPartner":
        best = "Strategic partnership"
        secondary = ""
        angle = "Member benefit / merchant introductions / joint circularity programme"
        cta = (kb.get("strategic_partnerships") or {}).get("cta") or "Explore a circular partnership"
    elif lead_class == "CapitalPartner":
        best = "Investment / ecosystem support"
        secondary = ""
        angle = "Impact thesis + structured circular commerce infrastructure"
        cta = "Introductory call for investors"
    else:  # BuyerPartner
        best = "Buyer audience partnership"
        secondary = "Joint campaign"
        angle = "Give your audience a circular shopping alternative"
        cta = "Discuss an audience partnership"

    # When a non-partner lead scores far higher as partner, surface it
    if lead_class in ("Seller", "CiraCustomer", "GavrielCustomer") and p >= 60:
        return "CircuCity Global Sales / Growth Partnership", "Cira partnership", \
            "You already advise buyers of CircuCity products", \
            (kb.get("partner_program") or {}).get("cta") or "Apply to the partner program"

    return best, secondary, angle, cta


def _reason(lead_class: str, scores: dict, best_offer: str, matched: list[str]) -> str:
    top = sorted(
        ((DIMENSION_LABELS[d], v) for d, v in scores.items()),
        key=lambda kv: kv[1], reverse=True,
    )[:2]
    hits = ", ".join(matched[:4]) if matched else "no strong persona signals"
    dims = "; ".join(f"{label} {v}%" for label, v in top)
    return f"Profile matches {lead_class}. {dims}. Signals: {hits}. Best route: {best_offer}."


def _evidence(lead_class: str, kb: dict, corpus: str) -> tuple[list[str], list[str], list[str]]:
    """Return (matched persona keywords, personalisation facts, evidence signals)."""
    persona_hits: list[str] = []
    personas = (kb.get("personas") or {}).get("personas") or {}
    spec = personas.get(lead_class) or {}
    persona_hits = [k for k in (spec.get("keywords") or []) if k.lower() in _normalise(corpus)]

    evidence: list[str] = []
    for dim, (sec, key) in PRODUCT_SIGNAL_KEYS.items():
        signals = (kb.get(sec) or {}).get(key) or []
        n, found = _count_signals(corpus, signals)
        if n:
            evidence.append(f"{DIMENSION_LABELS[dim]}: {', '.join(found[:5])}")

    facts = [
        f"Matched persona keyword(s): {', '.join(persona_hits[:5])}",
        "Lead class: " + lead_class,
    ] + evidence[:4]
    return persona_hits, facts, evidence


def classify(lead: dict) -> Classification | None:
    corpus = lead_corpus(lead)
    if not _normalise(corpus):
        return None

    kb = load()
    lead_class, _conf, persona_hits = detect_lead_class(corpus, kb)

    scores: dict[str, float] = {}
    for dim in DIMENSIONS:
        scores[dim] = _score(corpus, _dimension_signals(kb, dim))

    # Weight persona strength into the lead's best-fit product score
    if lead_class == "Seller":
        scores["marketplace"] = min(100.0, scores["marketplace"] + min(30.0, len(persona_hits) * 15))
        scores["gavriel"] = min(100.0, scores["gavriel"] + min(20.0, len(persona_hits) * 8))
    elif lead_class == "CiraCustomer":
        scores["cira"] = min(100.0, scores["cira"] + min(30.0, len(persona_hits) * 15))
    elif lead_class == "GavrielCustomer":
        scores["gavriel"] = min(100.0, scores["gavriel"] + min(30.0, len(persona_hits) * 15))
    elif lead_class == "GrowthPartner":
        scores["partner"] = min(100.0, scores["partner"] + min(30.0, len(persona_hits) * 15))
    elif lead_class == "StrategicPartner":
        scores["strategic"] = min(100.0, scores["strategic"] + min(30.0, len(persona_hits) * 15))
    elif lead_class == "CapitalPartner":
        scores["capital"] = min(100.0, scores["capital"] + min(30.0, len(persona_hits) * 15))

    scores = {k: round(v, 1) for k, v in scores.items()}

    best_offer, secondary, angle, cta = _recommend(lead_class, scores, kb)
    persona_hits, facts, evidence = _evidence(lead_class, kb, corpus)

    return Classification(
        lead_class=lead_class,
        confidences=scores,
        reason=_reason(lead_class, scores, best_offer, persona_hits),
        matched_persona=persona_hits,
        recommended_offer=best_offer,
        recommended_secondary=secondary,
        recommended_angle=angle,
        recommended_cta=cta,
        evidence_signals=evidence,
        personalisation_facts=facts,
    )
