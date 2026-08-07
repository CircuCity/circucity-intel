"""Default entry point for Streamlit Community Cloud.

Streamlit automatically detects streamlit_app.py / app.py on deploy.
Ensure the cloud Main file setting points here (or app.py).
"""

from __future__ import annotations

from app import main

main()