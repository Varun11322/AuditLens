"""Model & Rule Evaluation placeholder view."""

import streamlit as st

from frontend.components.auth_guard import render_sidebar
from frontend.constants import COLOR_PRIMARY


def render_evaluation_page() -> None:
    """Render placeholder for Phase 7 ground-truth evaluation feature."""
    render_sidebar()
    st.title("Model & Rule Evaluation")
    st.caption("Benchmark anomaly detection performance against synthetic ground truth.")

    with st.container(border=True):
        st.markdown(
            f'<div style="padding: 24px 12px;">'
            f'<h3 style="color: {COLOR_PRIMARY};">⏳ Evaluation Suite Coming Soon</h3>'
            f'<p style="color: #5F6C74; font-size: 1rem; line-height: 1.6;">'
            f"Ground-truth evaluation and benchmark scoring is scheduled for <b>Phase 7</b>.<br>"
            f"Key evaluation capabilities will include:"
            f"</p>"
            f'<ul style="color: #1B2A33; line-height: 1.8;">'
            f"<li>Uploading <code>ground_truth.csv</code> to benchmark run accuracy</li>"
            f"<li>Computing audit-adjusted and strict Precision, Recall, and F1 metrics</li>"
            f"<li>Per-anomaly-type recall breakdown (R1-R6 and ML random outliers)</li>"
            f"<li>False positive rate analysis across threshold sensitivity settings</li>"
            f"</ul>"
            f"</div>",
            unsafe_allow_html=True,
        )
