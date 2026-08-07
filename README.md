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
- **Research & Classify** — paste a LinkedIn bio / About page / company text; the system detects lead type, scores fit across all six dimensions, recommends an offer, angle, CTA and personalisation facts
- **Leads** — view, edit, classify, generate a personalised email, log emails, manage outreach status and next action
- **Add lead** — manual entry
- **Knowledge base** — live-edit the CircuCity brain (JSON, validated). Scoring uses these files, so changing pricing/offers/targets immediately changes recommendations

## Architecture

```
app.py                 Streamlit UI (all pages)
circucity/
  knowledge.py         Knowledge loader/saver + section registry
  leads.py             Lead model + JSON persistence (data/leads.json)
  classifier.py        Lead-type detection, six-dimension fit scoring, offer/angle/CTA
  emails.py            Per-lead-class personalised email templates
knowledge/*.json       Editable CircuCity Knowledge Base + persona definitions
data/leads.json        Persisted leads (created on first save)
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