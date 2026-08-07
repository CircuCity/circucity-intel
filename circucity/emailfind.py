"""Email discovery & verification for lead outreach.

Finds real business emails on a company's own site, or generates
role-mailbox candidates (info@, hello@, ...) and validates them:

    found_website  -> email extracted from the lead's own page
    smtp_ok        -> domain has MX and the mailbox accepted RCPT TO
    mx_ok          -> domain has MX (can receive mail), SMTP probe
                      inconclusive (e.g. port 25 egress blocked)
    rejected       -> MX exists but mailbox rejected RCPT TO
    unverified     -> syntax only
    none           -> nothing usable found

Best effort only; every check degrades gracefully.
"""

from __future__ import annotations

import re
import smtplib
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,24}\b")

BLOCKED_LOCALS = {"example", "yourname", "your.name", "email", "name", "user",
                  "someone", "test", "webmaster", "admin.login", "root"}
FREEMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                    "aol.com", "icloud.com", "proton.me", "protonmail.com",
                    "live.com", "msn.com", "mail.com", "gmx.com"}
ROLE_LOCALS = ["info", "hello", "contact", "sales", "support", "office"]


def valid_syntax(email: str) -> bool:
    return isinstance(email, str) and bool(EMAIL_RE.fullmatch(email.strip()))


def domain_of(email: str) -> str:
    return (email.rsplit("@", 1)[-1]).lower() if valid_syntax(email) else ""


def domain_from_url(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def freemail(email: str) -> bool:
    return domain_of(email) in FREEMAIL_DOMAINS


def extract_emails(text: str, max_hits: int = 6) -> list[str]:
    """Syntactically valid emails appearing in page text (best effort)."""
    if not text:
        return []
    found, seen = [], set()
    for raw in EMAIL_RE.findall(text):
        email = raw.strip(" .,;:()<>\"'")
        if not valid_syntax(email):
            continue
        local = email.split("@", 1)[0].lower()
        if local in BLOCKED_LOCALS or len(local) < 2:
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(email)
        if len(found) >= max_hits:
            break
    return found


def generate_candidates(domain: str) -> list[str]:
    """Role mailboxes for businesses that hide their email address."""
    domain = (domain or "").strip().lower().removeprefix("www.")
    if not valid_syntax("x@" + domain):
        return []
    return [f"{local}@{domain}" for local in ROLE_LOCALS]


def mx_host(domain: str) -> str | None:
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.timeout = 4
        resolver.lifetime = 6
        records = resolver.resolve(domain, "MX", raise_on_no_answer=False)
        if not records:
            return None
        exchange = sorted(records, key=lambda r: r.preference)[0].exchange
        return str(exchange).rstrip(".")
    except Exception:
        return None


def probe_rcpt(email: str, timeout: int = 8) -> str | None:
    """RCPT TO check against the mailbox's MX server.

    Returns "ok" (250/251), "rejected" (5xx), "grey" (4xx) or None when the
    probe cannot complete (no MX, port 25 blocked, server down).
    """
    mx = mx_host(domain_of(email))
    if not mx:
        return None
    try:
        smtp = smtplib.SMTP(mx, 25, timeout=timeout)
        ehlo = False
        try:
            code, _ = smtp.ehlo()
            if code == 250:
                ehlo = True
        except Exception:
            pass
        if not ehlo:
            try:
                smtp.helo()
            except Exception:
                smtp.close()
                return None
        try:
            smtp.mail("check@circucity.com")
            code_rcpt, _ = smtp.rcpt(email)
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
            smtplib.SMTPHeloError, OSError, TimeoutError):
        return None
    except Exception:
        return None
    str_code = str(code_rcpt)
    if str_code.startswith("5"):
        return "rejected"
    if str_code.startswith("4"):
        return "grey"
    if str_code.startswith("2"):
        return "ok"
    return None


def assess(direct_emails: list[str], domain: str, probe: bool = True) -> dict:
    """Pick the best candidate and grade it.

    Emails found on the site itself win immediately (no SMTP probing);
    role-mailbox candidates are probed only when nothing was found, with a
    small cap so the network cost stays low.
    """
    result = {"email": "", "candidates": [], "status": "none"}

    direct = [e for e in (direct_emails or []) if valid_syntax(e)]
    direct = [e for e in direct if e.split("@", 1)[0].lower() not in BLOCKED_LOCALS]
    candidates = [e for e in generate_candidates(domain) if e not in direct]
    all_emails = direct + candidates
    seen, unique = set(), []
    for email in all_emails:
        key = email.lower()
        if key not in seen:
            seen.add(key)
            unique.append(email)
    result["candidates"] = unique
    if not unique:
        return result

    if direct:
        best_direct = max(direct,
                          key=lambda e: (3 if freemail(e) else 5, len(e)))
        result["email"] = best_direct
        result["status"] = "found_website"
        return result

    best, best_dlv = "", 0
    probed = 0
    for email in candidates:
        if not mx_host(domain_of(email)):
            continue
        dlv = 2
        if probe and probed < 4:
            outcome = probe_rcpt(email)
            probed += 1
            if outcome == "ok":
                dlv = 3
            elif outcome == "rejected":
                dlv = 1
        if dlv > best_dlv:
            best, best_dlv = email, dlv
    if not best:
        best = candidates[0]

    result["email"] = best
    if best_dlv == 3:
        result["status"] = "smtp_ok"
    elif best_dlv == 2:
        result["status"] = "mx_ok"
    elif best_dlv == 1:
        result["status"] = "rejected"
    else:
        result["status"] = "unverified"
    return result


def discover(text: str, url: str, probe_smtp: bool = True) -> dict:
    """One-call entry: extract from page text, fall back to candidates."""
    domain = domain_from_url(url)
    return assess(extract_emails(text), domain, probe=probe_smtp)