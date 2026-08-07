"""Web lead discovery: DuckDuckGo search + page fetch + text extraction.

Best-effort helpers; failures are surfaced to the UI instead of crashing.
"""

from __future__ import annotations

import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _ddgs():
    try:
        from ddgs import DDGS
        return DDGS()
    except ImportError:
        from duckduckgo_search import DDGS
        return DDGS()


def search_web(query: str, max_results: int = 10) -> list[dict]:
    """Return [{title, url, snippet}] from DuckDuckGo (best effort)."""
    try:
        results = _ddgs().text(query, max_results=max_results)
    except Exception as exc:
        return [{"title": f"Search failed: {exc}", "url": "", "snippet": ""}]
    out = []
    for r in results or []:
        out.append({
            "title": str(r.get("title", "")),
            "url": str(r.get("href", "") or r.get("url", "")),
            "snippet": str(r.get("body", "") or r.get("snippet", "")),
        })
    return out


def fetch_text(url: str, max_chars: int = 3500, timeout: int = 12) -> str:
    """Fetch a page and reduce it to rough readable text (best effort)."""
    if not url:
        return ""
    try:
        resp = requests.get(url, headers={"User-Agent": UA},
                            timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception:
        return ""

    html = resp.text
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer",
                         "nav", "form", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)

    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]