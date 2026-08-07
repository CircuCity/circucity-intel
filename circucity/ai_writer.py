"""Optional AI email writing via Groq (OpenAI-compatible chat completions).

The structured classification provides the reasoning; the LLM writes the
email. Falls back to templates elsewhere if the key is missing or a call
fails (compose_email in emails.py handles that).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are the outreach writer for CircuCity, a circular-commerce platform: "
    "a marketplace connecting second-hand stores and consumers, plus AI products "
    "Cira (AI sales & support for ecommerce) and Gavriel (AI listing automation), "
    "and a partner program with commissions. Write warm, concrete, concise emails. "
    "No hype, no gimmicks, no 'I hope this finds you well'. One short hook, one "
    "why-it-matters line, the CTA. Treat every person as a human, never pitch a "
    "product that does not match the recommended offer."
)


def _build_user_prompt(lead: dict, classification: dict | None, signer: str) -> str:
    cls = classification or {}
    facts = "\n".join(f"- {f}" for f in (cls.get("personalisation_facts") or []))
    parts = [
        f"CONTACT: {lead.get('contact', '')}",
        f"ORGANISATION: {lead.get('organisation', '')}",
        f"COUNTRY: {lead.get('country', '')}",
        f"ROLE: {lead.get('role', '')}",
        f"INDUSTRY: {lead.get('industry', '')}",
        f"LEAD TYPE: {cls.get('lead_class', '')}",
        f"RECOMMENDED OFFER: {cls.get('recommended_offer', '')}",
        f"RECOMMENDED SECONDARY: {cls.get('recommended_secondary', '')}",
        f"RECOMMENDED ANGLE: {cls.get('recommended_angle', '')}",
        f"RECOMMENDED CTA: {cls.get('recommended_cta', '')}",
        f"PERSONALISATION FACTS:\n{facts}",
    ]
    return "\n".join(parts) + (
        f"\n\nWrite a short outreach email (max 120 words) to this lead for CircuCity."
        f" Sign as '{signer}'.\n"
        "Return ONLY two lines: first the subject, then a blank line, then the body."
    )


def _chat(api_key: str, model: str, user_prompt: str, timeout: int = 60) -> str:
    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GROQ_URL, data=data, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"].strip()


def _parse(text: str) -> tuple[str, str]:
    """Split 'subject: ...  / blank line / body' into (subject, body)."""
    lines = text.splitlines()
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return "", text
    subject = non_empty[0].strip()
    subject = re.sub(r"^\s*(subject:?)\s*", "", subject, flags=re.IGNORECASE).strip()
    idx = next(i for i, ln in enumerate(lines) if ln.strip()) + 1
    body = "\n".join(lines[idx:]).strip()
    return subject, body


def generate_ai_email(lead: dict, classification: dict | None,
                      api_key: str, model: str, signer: str) -> tuple[str, str]:
    """Return (subject, body) or (None, None) on any failure."""
    if not api_key:
        return None, None
    try:
        prompt = _build_user_prompt(lead, classification or {}, signer)
        text = _chat(api_key, model, prompt)
        subject, body = _parse(text)
        return subject, body
    except Exception:
        return None, None