"""Sidebar deployment + config helper page slice used by app.py.
"""
from __future__ import annotations

import os

import streamlit as st


def get_secret(key: str, default=None):
    """Read a secret from env vars first (local/headless), then st.secrets."""
    value = os.environ.get(key)
    if value is not None:
        return value
    try:
        data = st.secrets
    except Exception:
        return default
    for part in key.split("."):
        try:
            if isinstance(data, dict) or hasattr(data, "get"):
                data = data.get(part)
            else:
                data = getattr(data, part, default)
        except Exception:
            return default
        if data is None:
            return default
    return data


def groq_config() -> dict:
    api_key = get_secret("GROQ_API_KEY") or get_secret("groq.api_key")
    model = get_secret("GROQ_MODEL") or get_secret("groq.model") or "llama-3.3-70b-versatile"
    return {"api_key": api_key, "model": model}


def smtp_config() -> dict:
    def s(k):
        return get_secret(f"smtp.{k}")

    return {
        "host": s("host"),
        "port": int(s("port") or 587),
        "user": s("user"),
        "password": s("password"),
        "from_addr": s("from_addr"),
        "from_name": s("from_name") or "CircuCity",
    }


def config_status() -> dict:
    g = groq_config()
    smtp = smtp_config()
    return {
        "groq_ready": bool(g["api_key"]),
        "groq_model": g["model"],
        "smtp_ready": bool(smtp["host"] and smtp["user"] and smtp["password"] and smtp["from_addr"]),
        "smtp_host": smtp["host"],
        "smtp_from": smtp["from_addr"],
    }


def render_config_sidebar() -> None:
    status = config_status()
    st.sidebar.subheader("Connections")
    if status["groq_ready"]:
        st.sidebar.success(f"Groq AI - {status['groq_model']}")
    else:
        st.sidebar.warning("Groq AI: add GROQ_API_KEY to secrets")
    if status["smtp_ready"]:
        st.sidebar.success(f"SMTP - {status['smtp_host']}")
    else:
        st.sidebar.warning("SMTP: host/user/password/from_addr required")