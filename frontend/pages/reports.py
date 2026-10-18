"""Reports & Exceptions Export placeholder view (UX_FLOWS.md Flow 7)."""

import streamlit as st

from frontend.components.auth_guard import render_sidebar
from frontend.constants import COLOR_PRIMARY


def render_reports_page() -> None:
    """Render placeholder for Phase 6 Excel report export feature."""
    render_sidebar()
    st.title("Audit Exceptions Workpaper Reports")
    st.caption("Generate and download multi-sheet Excel (.xlsx) audit workpapers.")

    with st.container(border=True):
        st.markdown(
            f'<div style="padding: 24px 12px;">'
            f'<h3 style="color: {COLOR_PRIMARY};">⏳ Report Generation Coming Soon</h3>'
            f'<p style="color: #5F6C74; font-size: 1rem; line-height: 1.6;">'
            f"Comprehensive Excel (.xlsx) report export is scheduled for <b>Phase 6</b>.<br>"
            f"Generated workpapers will include structured sheets for:"
            f"</p>"
            f'<ul style="color: #1B2A33; line-height: 1.8;">'
            f"<li><b>Summary</b>: Executive audit scorecard, risk counts, and run parameters</li>"
            f"<li><b>Flagged Transactions</b>: Complete list of exceptions with "
            f"scores and plain-English reasons</li>"
            f"<li><b>Rule Counts</b>: Breakdown across rules (R1 to R6)</li>"
            f"<li><b>Benford's Law</b>: Observed vs. expected digit frequencies</li>"
            f"<li><b>Review Log</b>: Signed-off audit review history and notes</li>"
            f"</ul>"
            f"</div>",
            unsafe_allow_html=True,
        )
