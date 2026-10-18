"""Main Streamlit application entry point for AuditLens."""

import sys
from pathlib import Path

# Ensure project root is on sys.path when invoked via `streamlit run frontend/app.py`
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

import streamlit as st

from frontend.pages.benford import render_benford_page
from frontend.pages.dashboard import render_dashboard_page
from frontend.pages.evaluation import render_evaluation_page
from frontend.pages.login import render_login_page
from frontend.pages.reports import render_reports_page
from frontend.pages.review import render_review_page
from frontend.pages.upload import render_upload_page

st.set_page_config(
    page_title="AuditLens",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

token = st.session_state.get("token")

if not token:
    login_page = st.Page(render_login_page, title="Login", url_path="login", icon="🔐")
    nav = st.navigation([login_page], position="hidden")
    nav.run()
else:
    upload_page = st.Page(
        render_upload_page,
        title="Upload",
        url_path="upload",
        icon="📤",
        default=True,
    )
    dashboard_page = st.Page(
        render_dashboard_page,
        title="Dashboard",
        url_path="dashboard",
        icon="📊",
    )
    review_page = st.Page(
        render_review_page,
        title="Review",
        url_path="review",
        icon="🔍",
    )
    benford_page = st.Page(
        render_benford_page,
        title="Benford",
        url_path="benford",
        icon="📈",
    )
    reports_page = st.Page(
        render_reports_page,
        title="Reports",
        url_path="reports",
        icon="📄",
    )
    evaluation_page = st.Page(
        render_evaluation_page,
        title="Evaluation",
        url_path="evaluation",
        icon="🎯",
    )

    page_map = {
        "Upload": upload_page,
        "Dashboard": dashboard_page,
        "Review": review_page,
        "Benford": benford_page,
        "Reports": reports_page,
        "Evaluation": evaluation_page,
    }

    nav = st.navigation(list(page_map.values()))

    # Check for programmatic navigation request (e.g. from Dashboard or Upload buttons)
    dest = st.session_state.pop("nav_destination", None)
    if dest in page_map:
        st.switch_page(page_map[dest])
    else:
        nav.run()
