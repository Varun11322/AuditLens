"""Main Streamlit application entry point for AuditLens."""

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
    login_page = st.Page(render_login_page, title="Login", icon="🔐")
    nav = st.navigation([login_page], position="hidden")
    nav.run()
else:
    upload_page = st.Page(
        render_upload_page,
        title="Upload",
        icon="📤",
        default=True,
    )
    dashboard_page = st.Page(
        render_dashboard_page,
        title="Dashboard",
        icon="📊",
    )
    review_page = st.Page(
        render_review_page,
        title="Review",
        icon="🔍",
    )
    benford_page = st.Page(
        render_benford_page,
        title="Benford",
        icon="📈",
    )
    reports_page = st.Page(
        render_reports_page,
        title="Reports",
        icon="📄",
    )
    evaluation_page = st.Page(
        render_evaluation_page,
        title="Evaluation",
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
