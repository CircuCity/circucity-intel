"""CircuCity Growth Intelligence System - Streamlit UI.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from circucity.ai_writer import explain_fit
from circucity.classifier import DIMENSION_LABELS, classify
from circucity.config import groq_config, render_config_sidebar, smtp_config
from circucity.emailfind import discover
from circucity.emails import compose_email
from circucity.importer import import_and_classify, parse_csv, rows_to_leads, template_csv
from circucity.knowledge import load, save_section, section_names
from circucity.leads import (
    OUTREACH_STATUSES,
    add_email,
    add_lead,
    blank_lead,
    delete_lead,
    get_lead,
    load_leads,
    update_lead,
)
from circucity.mailer import send_email
from circucity.webfind import fetch_text, search_web

st.set_page_config(page_title="CircuCity Growth Intel", page_icon="recycle", layout="wide")

DIMENSION_ORDER = ["marketplace", "cira", "gavriel", "partner", "strategic", "capital"]


def render_scorebars(scores: dict) -> None:
    cols = st.columns(len(DIMENSION_ORDER))
    for col, dim in zip(cols, DIMENSION_ORDER):
        with col:
            st.metric(DIMENSION_LABELS[dim], f"{scores.get(dim, 0):.0f}%")
            st.progress(min(1.0, scores.get(dim, 0) / 100.0))


def page_dashboard() -> None:
    st.title("CircuCity Growth Intelligence System")
    leads = load_leads()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total leads", len(leads))
    c2.metric("Contacted", sum(1 for l in leads if l["outreach_status"] == "Contacted"))
    c3.metric("Replied", sum(1 for l in leads if l["outreach_status"] in ("Replied", "Meeting")))
    c4.metric("Converted", sum(1 for l in leads if l["outreach_status"] == "Converted"))

    if not leads:
        st.info("No leads yet. Add some from the 'Add lead' page, or use 'Research & Classify'.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        df = pd.DataFrame([
            {"Lead": l["contact"] or l["organisation"] or "(unnamed)",
             "Type": l["lead_class"] or "-", "Country": l["country"],
             "Status": l["outreach_status"], "Source": l["source"]}
            for l in leads
        ])
        st.subheader("Pipeline")
        st.dataframe(df, width="stretch", hide_index=True)
    with col2:
        st.subheader("By status")
        status_df = pd.DataFrame(
            [{"status": s, "n": sum(1 for l in leads if l["outreach_status"] == s)}
             for s in OUTREACH_STATUSES]
        )
        st.bar_chart(status_df, x="status", y="n", color="#10b981")

        st.subheader("By lead type")
        type_s: dict[str, int] = {}
        for l in leads:
            t = l.get("lead_class") or "Unknown"
            type_s[t] = type_s.get(t, 0) + 1
        st.bar_chart(pd.DataFrame({"t": list(type_s.keys()), "n": list(type_s.values())}),
                     x="t", y="n", color="#8b5cf6")


def page_add() -> None:
    st.header("Add a lead")
    with st.form("add_lead"):
        c1, c2 = st.columns(2)
        contact = c1.text_input("Contact")
        organisation = c2.text_input("Organisation")
        c3, c4 = st.columns(2)
        country = c3.text_input("Country")
        website = c4.text_input("Website")
        c5, c6 = st.columns(2)
        email = c5.text_input("Email")
        role = c6.text_input("Role")
        c7, c8 = st.columns(2)
        industry = c7.text_input("Industry")
        business_model = c8.text_input("Business model")
        source = st.selectbox("Source", ["LinkedIn", "Web search", "Referral", "Event", "Manual"])
        evidence = st.text_area("Evidence / research notes", height=160,
                                help="Paste website copy, LinkedIn bio or your research. The classifier reads this.")
        submitted = st.form_submit_button("Create lead")
        if submitted:
            lead = blank_lead()
            lead.update({
                "contact": contact, "organisation": organisation, "country": country,
                "website": website, "email": email, "role": role, "industry": industry,
                "business_model": business_model, "source": source, "evidence": evidence,
            })
            add_lead(lead)
            st.success(f"Lead created ({lead['id']}). Classify it from the Leads page.")
            st.rerun()


def page_research() -> None:
    st.header("Research a person or company")
    st.caption("Paste anything: LinkedIn bio, website About page, company description. The system classifies it against the full CircuCity knowledge base.")
    text = st.text_area("Source text", height=180)
    if st.button("Classify with AI" if groq_config()["api_key"] else "Classify", type="primary"):
        probe = blank_lead()
        probe["evidence"] = text
        cls = classify(probe, prefer_ai=bool(groq_config()["api_key"]))
        if cls:
            st.subheader("Result")
            if cls.weak:
                st.warning(
                    f"Only {cls.signal_count} signal(s) found - this looks like label text or an empty field, "
                    "not a researched profile. Classification will be unreliable. "
                    "Paste more context (role, industry, what they sell, who they help)."
                )
            st.markdown(f"**Lead type: {cls.lead_class}**  - recommended offer: *{cls.recommended_offer}*")
            render_scorebars(cls.confidences)
            st.markdown(f"**Angle:** {cls.recommended_angle}")
            st.markdown(f"**CTA:** {cls.recommended_cta}")
            st.markdown(f"**Why:** {cls.reason}")
            with st.expander("Personalisation facts & evidence"):
                for f in cls.personalisation_facts:
                    st.write("-", f)
                for e in cls.evidence_signals:
                    st.write("--", e)
            with st.form("research_save"):
                st.write("Turn this into a lead:")
                c1, c2 = st.columns(2)
                contact = c1.text_input("Contact")
                organisation = c2.text_input("Organisation")
                country = st.text_input("Country")
                if st.form_submit_button("Save as lead"):
                    lead = blank_lead()
                    lead.update({"contact": contact, "organisation": organisation,
                                 "country": country, "source": "Research",
                                 "evidence": text, "lead_class": cls.lead_class})
                    add_lead(lead)
                    st.success("Saved.")
                    st.rerun()


def page_leads() -> None:
    st.header("Leads")
    leads = load_leads()
    if not leads:
        st.info("No leads yet.")
        return

    opts = {f"{l['contact'] or l['organisation'] or l['id']}  ({l['lead_class'] or 'unclassified'})": l["id"]
            for l in leads}
    label = st.selectbox("Select lead", list(opts.keys()))
    lead_id = opts[label]
    lead = get_lead(lead_id)

    if st.button("Delete lead"):
        delete_lead(lead_id)
        st.rerun()

    cls = None
    if lead["evidence"] or lead["notes"] or lead.get("industry"):
        cls = classify(lead)

    gcfg = groq_config()

    st.subheader(f"{lead['contact'] or 'Unnamed'} - {lead['organisation'] or ''}")

    c1, c2 = st.columns(2)
    with c1:
        idx = OUTREACH_STATUSES.index(lead["outreach_status"]) if lead["outreach_status"] in OUTREACH_STATUSES else 0
        status = st.selectbox("Outreach status", OUTREACH_STATUSES, index=idx)
        if status != lead["outreach_status"]:
            lead = update_lead(lead["id"], {"outreach_status": status})
    with c2:
        nxt = st.text_input("Next action", lead["next_action"])
        if nxt != lead["next_action"]:
            lead = update_lead(lead["id"], {"next_action": nxt})

    if cls:
        if cls.weak:
            st.warning("Weak evidence: no CircuCity signals matched. Add role/industry/what-they-sell text for a reliable classification.")
        st.markdown(f"**Recommended offer:** {cls.recommended_offer}  -  **CTA:** {cls.recommended_cta}")
        render_scorebars(cls.confidences)
        st.markdown(f"**Angle:** {cls.recommended_angle}")
        st.markdown(f"**Why:** {cls.reason}")
        fit_key = f"fit_{lead['id']}"
        st.markdown("**How CircuCity fits**")
        need_col, fit_col = st.columns([1, 4])
        with need_col:
            if st.button("Explain fit with AI", key=f"fit_btn_{lead['id']}"):
                with st.spinner(f"Analyzing with {gcfg.get('model', '')} ..."):
                    st.session_state[fit_key] = explain_fit(lead, cls, gcfg.get("api_key", ""), gcfg.get("model", ""))
        with fit_col:
            stored_fit = st.session_state.get(fit_key)
            if stored_fit:
                st.markdown(stored_fit)
            else:
                st.caption("AI writes how CircuCity's marketplace, Cira and Gavriel fit this exact business - grounded in the evidence below.")
        with st.expander("Evidence behind the fit"):
            for f in cls.personalisation_facts:
                st.write("-", f)
            for e in cls.evidence_signals:
                st.write("--", e)
    else:
        st.info("Add role/industry/evidence text below, save, and classification will run.")

    st.subheader("Email")
    email_status = lead.get("custom", {}).get("email_status")
    if email_status:
        st.caption(f"Email: {email_status}"
                   + (" - verified on the lead's own site" if email_status == "found_website"
                      else " - mailbox accepted RCPT" if email_status == "smtp_ok"
                      else " - domain has MX" if email_status == "mx_ok"
                      else " - best guess, not verified" if email_status == "unverified"
                      else ""))
    if lead.get("website") and st.button("Find / re-scan email", key=f"rescan_{lead['id']}"):
        with st.spinner("Scanning the site and its contact pages ..."):
            try:
                text = fetch_text(lead["website"])
            except Exception:
                text = ""
            found_info = discover(text, lead["website"], probe_smtp=False)
        if found_info.get("email"):
            update_lead(lead["id"], {
                "email": found_info["email"],
                "custom": {
                    **lead.get("custom", {}),
                    "email_candidates": found_info.get("candidates", []),
                    "email_status": found_info["status"],
                },
            })
            st.success(f"Email updated to {found_info['email']} ({found_info['status']}).")
            st.rerun()
        else:
            st.warning("No email found on the site or its contact pages - consider a role mailbox or the site's contact form.")
    c_mode, c_signer = st.columns([1, 3])
    with c_mode:
        mode = st.radio("Writer", ["Template", "AI (Groq)"], horizontal=True, key="writer_mode")
    with c_signer:
        signer = st.text_input("Signer name", "The CircuCity team", key="signer_name")

    draft_key = f"draft_{lead['id']}"

    use_ai = mode == "AI (Groq)"
    if use_ai:
        if not gcfg["api_key"]:
            st.warning("No Groq API key in secrets (groq.api_key) - using the template writer.")
            use_ai = False
        elif st.button("Compose with AI", type="primary", key="ai_compose"):
            with st.spinner(f"Writing with {gcfg['model']} ..."):
                subject, body, method = compose_email(lead, cls, signer, use_ai=True, ai_kwargs=gcfg)
            if method == "ai":
                st.session_state[draft_key] = {"subject": subject, "body": body}
                st.success("Draft composed with AI - edit before sending.")
            else:
                st.warning("AI call failed - showing the template draft instead.")

    if draft_key in st.session_state:
        subject = st.session_state[draft_key]["subject"]
        body = st.session_state[draft_key]["body"]
    else:
        subject, body, _ = compose_email(lead, cls, signer, use_ai=False)

    subject = st.text_input("Subject", subject, key=f"subj_{lead['id']}")
    body_box = st.text_area("Email body", body, height=260, key=f"body_{lead['id']}")

    if lead["email"] and lead.get("custom", {}).get("email_status") in ("unverified", "rejected", "none"):
        st.warning("This address is a role-mailbox guess or was rejected - it may bounce. Send anyway, or run 'Find / re-scan email' first.")
    col_a, col_b, col_c = st.columns([1, 1, 3])
    with col_a:
        if st.button("Log email", key=f"log_{lead['id']}"):
            add_email(lead["id"], subject, body_box, "out")
            st.success("Logged to history.")
            st.rerun()
    with col_b:
        if st.button("Send email", type="primary", key=f"send_{lead['id']}"):
            smtp = smtp_config()
            ok, msg = send_email(smtp, lead["email"], subject, body_box)
            if ok:
                add_email(lead["id"], subject, body_box, "out")
                st.success(f"Sent to {lead['email']}.")
                st.rerun()
            else:
                st.error(msg)
    with col_c:
        st.caption("Log saves to history. Send delivers via SMTP and logs the sent copy.")

    st.subheader("Email history")
    for em in reversed(lead.get("email_history") or []):
        with st.expander(f"{em['direction'].upper()} - {em['subject']} ({em['at']})"):
            st.write(em["body"])

    st.subheader("Edit lead")
    show_edit_form(lead)


def show_edit_form(lead: dict) -> None:
    with st.form(f"edit_{lead['id']}"):
        c1, c2 = st.columns(2)
        contact = c1.text_input("Contact", lead["contact"])
        organisation = c2.text_input("Organisation", lead["organisation"])
        c3, c4 = st.columns(2)
        country = c3.text_input("Country", lead["country"])
        website = c4.text_input("Website", lead["website"])
        c5, c6 = st.columns(2)
        email = c5.text_input("Email", lead["email"])
        role = c6.text_input("Role", lead["role"])
        c7, c8 = st.columns(2)
        industry = c7.text_input("Industry", lead["industry"])
        business_model = c8.text_input("Business model", lead["business_model"])
        c9, c10 = st.columns(2)
        source = c9.text_input("Source", lead["source"])
        lead_class = c10.text_input("Lead type (auto-detected)", lead["lead_class"])
        evidence = st.text_area("Evidence / research notes", lead["evidence"], height=140)
        notes = st.text_area("Internal notes", lead["notes"], height=80)
        if st.form_submit_button("Save"):
            update_lead(lead["id"], {
                "contact": contact, "organisation": organisation, "country": country,
                "website": website, "email": email, "role": role, "industry": industry,
                "business_model": business_model, "source": source,
                "lead_class": lead_class, "evidence": evidence, "notes": notes,
            })
            st.rerun()


def page_knowledge() -> None:
    st.header("CircuCity Knowledge Base")
    st.caption("The brain of the system. Edit any section - pricing, offers, targets - and scoring updates immediately. JSON, validated on save.")
    section = st.selectbox("Section", section_names())
    kb = load()
    data = kb.get(section, {})
    text = st.text_area("Section content (JSON)",
                        value=json.dumps(data, ensure_ascii=False, indent=2),
                        height=520, key=f"kb_{section}")
    if st.button("Save section", type="primary"):
        try:
            parsed = json.loads(text)
        except ValueError as e:
            st.error(f"Invalid JSON: {e}")
        else:
            save_section(section, parsed)
            st.success("Saved.")
            st.rerun()
    st.download_button(
        "Download knowledge as JSON",
        json.dumps(data, ensure_ascii=False, indent=2),
        file_name=f"circucity_{section}.json",
    )


def page_find() -> None:
    st.header("Find leads on the web")
    st.caption("Search for candidates, fetch their sites, classify with the AI and import as leads.")
    c1, c2 = st.columns([3, 1])
    query = c1.text_input("Search query",
                          placeholder='e.g. "second-hand clothing store Berlin"')
    n_results = c2.slider("Results", 5, 25, 10)
    if st.button("Search the web", type="primary"):
        with st.spinner("Searching..."):
            st.session_state["find_results"] = search_web(query, n_results)
        st.rerun()

    results = st.session_state.get("find_results")
    if results:
        if len(results) == 1 and not results[0]["url"]:
            st.warning(results[0]["snippet"] or "Search returned nothing.")
            return
        df = pd.DataFrame(results).assign(add=False)
        email_info = st.session_state.get("find_emails", {})
        df["email"] = [email_info.get(r["url"], (None, ""))[0] or "" for r in results]
        df["email_state"] = [email_info.get(r["url"], (None, ""))[1] or "" for r in results]
        edited = st.data_editor(
            df,
            column_config={
                "add": st.column_config.CheckboxColumn("Import"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "url": st.column_config.TextColumn("URL"),
                "email": st.column_config.TextColumn("Email found"),
                "email_state": st.column_config.TextColumn("Verified"),
                "snippet": st.column_config.TextColumn("Snippet", width="large"),
            },
            hide_index=True, width="stretch", key="find_editor",
            disabled=["title", "url", "snippet", "email", "email_state"],
        )
        selected = edited[edited["add"]]
        if len(selected):
            st.markdown(f"**{len(selected)} selected**")
            ai_on = bool(groq_config()["api_key"])
            c_find, c_probe, c_scan, c_go = st.columns([1, 2, 2, 3])
            find_email = c_find.checkbox("Find business email", value=True)
            probe_smtp = c_probe.checkbox("Verify deliverability (SMTP)", value=False)
            remaining = [r for r in results
                         if r["url"] not in email_info and r["url"] in set(selected["url"])]
            if c_scan.button(f"Scan {len(remaining)} for emails", disabled=not remaining):
                info = st.session_state.setdefault("find_emails", {})
                prog = st.progress(0.0)
                for i, row in enumerate(remaining):
                    try:
                        text = fetch_text(row["url"])
                    except Exception:
                        text = ""
                    found_info = discover(text, row["url"], probe_smtp=probe_smtp)
                    info[row["url"]] = (found_info.get("email", ""), found_info.get("status", ""))
                    prog.progress((i + 1) / max(len(remaining), 1))
                st.rerun()
            if c_go.button(
                    f"Fetch, classify & import {len(selected)} (+AI analysis)" if ai_on
                    else f"Fetch, classify & import {len(selected)}", type="primary"):
                imported, failed, with_email = 0, [], 0
                for _, row in selected.iterrows():
                    try:
                        text = fetch_text(row["url"])
                    except Exception:
                        text = ""
                    lead = blank_lead()
                    lead.update({
                        "organisation": _domain(row["url"]),
                        "website": row["url"],
                        "source": "Web search",
                        "evidence": text or str(row["snippet"]),
                        "notes": str(row["title"])[:200],
                    })
                    if find_email:
                        cached = email_info.get(row["url"])
                        if cached and cached[0]:
                            found_info = {"email": cached[0], "status": cached[1],
                                          "candidates": []}
                        else:
                            found_info = discover(text, row["url"], probe_smtp=probe_smtp)
                        if found_info.get("email"):
                            lead["email"] = found_info["email"]
                            lead["custom"]["email_candidates"] = found_info.get("candidates", [])
                            lead["custom"]["email_status"] = found_info["status"]
                            with_email += 1
                    cls = classify(lead, prefer_ai=ai_on)
                    if cls:
                        lead["lead_class"] = cls.lead_class
                    add_lead(lead)
                    imported += 1
                st.success(
                    f"Imported {imported} lead(s) - {with_email} with a business email. "
                    "Open the Leads page.")
                st.rerun()


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    net = urlparse(url if "://" in url else "https://" + url).netloc
    return net.removeprefix("www.") or url


def page_import() -> None:
    st.header("Import leads from CSV")
    st.caption("Upload a CSV with contact, organisation, country, website, email, role, "
               "industry, business_model, evidence, source. Any subset works - edit rows "
               "before importing, and optionally AI-classify each one.")
    st.download_button("Download CSV template", template_csv(),
                       file_name="circucity_leads_template.csv", mime="text/csv")

    up = st.file_uploader("CSV file", type=["csv"])
    if up:
        try:
            leads, warnings = parse_csv(up)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            return
        for w in warnings:
            st.warning(w)
        if leads:
            preview = pd.DataFrame([
                {k: lead[k] for k in ("contact", "organisation", "country", "website",
                                      "email", "role", "industry", "evidence", "source")
                 if lead[k]}
                for lead in leads
            ])
            edited = st.data_editor(preview, num_rows="dynamic", width="stretch",
                                    key="csv_editor")
            ai_on = st.checkbox("AI-classify each row (one Groq call per lead)")
            if st.button(f"Import {len(edited)} leads", type="primary"):
                final = rows_to_leads(edited)
                saved = import_and_classify(final, ai_on and bool(groq_config()["api_key"]))
                st.success(f"Imported and saved {len(saved)} lead(s).")
                st.rerun()


PAGES = {
    "Dashboard": page_dashboard,
    "Research & Classify": page_research,
    "Find leads": page_find,
    "Import CSV": page_import,
    "Leads": page_leads,
    "Add lead": page_add,
    "Knowledge base": page_knowledge,
}


def main() -> None:
    st.sidebar.title("CircuCity Intel")
    st.sidebar.caption("Growth Intelligence System")
    render_config_sidebar()
    page_name = st.sidebar.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    PAGES[page_name]()


if __name__ == "__main__":
    main()
