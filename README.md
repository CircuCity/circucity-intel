# CircuCity Growth Intelligence System

A local research → classify → score → match → personalise → outreach system for CircuCity. It understands **who** each lead is, **what role** they could play in CircuCity's growth (Seller, Cira Customer, Gavriel Customer, Growth Partner, Strategic Partner, Capital Partner, Buyer Acquisition Partner), **why** they would care, and **what to say** to them.

Built from the product brief: the app's "brain" is a structured, **editable CircuCity Knowledge Base** (company, marketplace, Cira, Gavriel, partner program, strategic partnerships, personas), and every lead is classified and scored against that brain — not against one hardcoded prompt.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Pages

- **Dashboard** — pipeline metrics, status & lead-type breakdown
- **Research & Classify** — paste a LinkedIn bio / About page / company text; the system detects lead type, scores fit across all six dimensions, recommends an offer, angle, CTA and personalisation facts (AI-first when Groq is configured)
- **Find leads** — web search for candidates, fetch their sites, AI-classify and bulk-import as leads
- **Import CSV** — upload leads (template provided, any column subset), edit rows in the grid, optionally AI-classify each one, then import
- **Leads** — view, edit, classify, write and **send** a personalised email, log email history, manage outreach status and next action
- **Add lead** — manual entry
- **Knowledge base** — live-edit the CircuCity brain (JSON, validated). Scoring uses these files, so changing pricing/offers/targets immediately changes recommendations

## Sending email + AI writing

Two optional connections, configured in secrets — never in code:

1. **AI writer (Groq)** — picks the best template strategy from the classification, then writes a genuinely personalised email with the LLM. Falls back to deterministic templates if the key is missing or a call fails.
2. **SMTP** — the "Send email" button delivers the draft via your mail server and logs a copy to the lead's history.

Local secrets file `.streamlit/secrets.toml` (gitignored — copy it from this template):

```toml
[groq]
api_key = "gsk_..."        # https://console.groq.com
model = "llama-3.3-70b-versatile"

[smtp]
host = "smtp.gmail.com"    # your provider (Gmail app password, Mailgun, Brevo, ...)
port = 587
user = "you@example.com"
password = "app-password"
from_addr = "you@example.com"
from_name = "CircuCity"
```

**Streamlit Community Cloud**: add the same keys under the app's Settings → Secrets, with `GROQ_API_KEY` / `GROQ_MODEL` or the `groq.*` / `smtp.*` block. The sidebar shows live connection status for both.

## Architecture

```
app.py                 Streamlit UI (all pages)
circucity/
  knowledge.py         Knowledge loader/saver + section registry
  leads.py             Lead model + JSON persistence (data/leads.json)
  classifier.py        Lead-type detection, six-dimension fit scoring, offer/angle/CTA
  emails.py            Per-lead-class personalised email templates + compose()
  ai_writer.py         Optional Groq LLM writer (works in template mode without it)
  mailer.py            SMTP sending via stdlib smtplib
  config.py            Secrets access + sidebar connection status
knowledge/*.json       Editable CircuCity Knowledge Base + persona definitions
data/leads.json        Persisted leads (created on first save)
.streamlit/secrets.toml  Local API keys / SMTP (gitignored)
```

**Lead Type ≠ Offer.** A growth marketer is a `GrowthPartner` and its offer is `Cira partnership`; a second-hand store is a `Seller` and gets `Marketplace + Gavriel`; a sustainability network is a `StrategicPartner` with no product pitched. The classifier keeps these separate.

## How it decides

For every lead it builds a corpus from contact, role, industry, business model, evidence and notes, then:

1. **Detects lead type** from the editable `personas.json` keywords.
2. **Scores fit** (0–100%) per dimension by counting knowledge-base signals present in the corpus.
3. **Recommends** offer, secondary, angle and CTA from the lead type + scores (also editable in the knowledge JSON).
4. **Extracts evidence** — the exact matched signals, used as personalisation facts in the generated email.

## Extending

- Add a persona or keyword → edit `personas.json` (also via the Knowledge base page).
- Change an offer or CTA → edit the relevant section JSON.
- Leads support **arbitrary custom fields** (`custom` dict) which the classifier also reads.