"""Reports & Exceptions Export view (UX_FLOWS.md Flow 7).

Allows auditors and managers to generate and download multi-sheet Excel (.xlsx)
audit workpapers with complete run traceability, formula injection neutralization,
and categorized exception sheets.
"""

from __future__ import annotations

import mimetypes

import streamlit as st

from frontend.api_client import ApiClientError, api_client
from frontend.components.auth_guard import get_token, handle_api_call, render_sidebar
from frontend.components.badges import format_datetime
from frontend.constants import COLOR_PRIMARY, COLOR_SURFACE

# Ensure OpenXML spreadsheet MIME type is registered in Python's mimetypes database
# so Streamlit media file storage reliably resolves .xlsx across all operating systems
# (including minimal Linux containers lacking /etc/mime.types).
mimetypes.add_type(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsx",
)


def render_reports_page() -> None:
    """Render the audit exceptions report export workbench."""
    render_sidebar()
    token = get_token()
    if not token:
        st.warning("Please sign in to access reports and export deliverables.")
        return

    st.title("Audit Exceptions Workpaper Reports")
    st.caption("Export standardized multi-sheet Excel (.xlsx) workpapers for audit documentation.")

    # 1. Fetch available uploads
    try:
        uploads_resp = handle_api_call(api_client.list_uploads, token, page=1, page_size=50)
        uploads = uploads_resp.get("items", [])
    except ApiClientError as err:
        st.error(f"Error fetching uploads: {err.message}")
        return

    if not uploads:
        st.info("No transaction uploads found. Please upload a dataset to begin.")
        if st.button("Go to Upload Page", type="primary"):
            st.session_state["nav_destination"] = "Upload"
            st.rerun()
        return

    # Select upload
    col_sel1, col_sel2 = st.columns(2)
    upload_options = {f"{u['id']}: {u['original_filename']}": u["id"] for u in uploads}
    default_upload_idx = 0
    curr_up_id = st.session_state.get("current_upload_id")
    if curr_up_id:
        for idx, up_id in enumerate(upload_options.values()):
            if up_id == curr_up_id:
                default_upload_idx = idx
                break

    with col_sel1:
        selected_up_label = st.selectbox(
            "Select Upload Dataset",
            options=list(upload_options.keys()),
            index=default_upload_idx,
        )
    selected_up_id = upload_options[selected_up_label]
    st.session_state["current_upload_id"] = selected_up_id

    # 2. Fetch runs for selected upload
    try:
        runs = handle_api_call(api_client.list_runs_for_upload, token, upload_id=selected_up_id)
    except ApiClientError as err:
        st.error(f"Error fetching runs: {err.message}")
        return

    completed_runs = [r for r in runs if r.get("status") == "completed"]
    if not completed_runs:
        st.info(
            f"No completed analysis runs found for '{selected_up_label}'. "
            "Please trigger an analysis run from the Upload page first."
        )
        if st.button("Go to Upload Page", type="primary"):
            st.session_state["nav_destination"] = "Upload"
            st.rerun()
        return

    run_options = {
        f"Run #{r['id']} ({format_datetime(r.get('finished_at'))})": r["id"] for r in completed_runs
    }
    default_run_idx = 0
    curr_run_id = st.session_state.get("current_run_id")
    if curr_run_id:
        for idx, r_id in enumerate(run_options.values()):
            if r_id == curr_run_id:
                default_run_idx = idx
                break

    with col_sel2:
        selected_run_label = st.selectbox(
            "Select Analysis Run",
            options=list(run_options.keys()),
            index=default_run_idx,
        )
    selected_run_id = run_options[selected_run_label]
    st.session_state["current_run_id"] = selected_run_id

    # 3. Load run details
    try:
        run_detail = handle_api_call(api_client.get_run, token, run_id=selected_run_id)
    except ApiClientError as err:
        st.error(f"Error fetching run details: {err.message}")
        return

    summary = run_detail.get("summary") or {}
    scoring = summary.get("scoring") or {}
    by_level = scoring.get("by_level") or {}
    high_count = by_level.get("High", by_level.get("high", 0))
    med_count = by_level.get("Medium", by_level.get("medium", 0))
    low_count = by_level.get("Low", by_level.get("low", 0))
    total_flagged = scoring.get("total_flagged", high_count + med_count + low_count)

    is_signed_off = run_detail.get("signed_off_by") is not None
    signed_off_at = format_datetime(run_detail.get("signed_off_at"))

    st.markdown("---")

    # 4. Run Overview Card
    with st.container(border=True):
        st.subheader("📋 Audit Report Package Overview")
        if is_signed_off:
            st.success(
                f"🔒 **Officially Signed Off**: This run was signed off on {signed_off_at}. "
                "The report includes immutable sign-off traceability."
            )
        else:
            st.info(
                "ℹ️ **Preliminary Workpaper**: This run is currently in review and has not yet been "
                "signed off by an audit manager."
            )

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Total Exceptions", f"{total_flagged:,}")
        m_col2.metric("High Risk", f"{high_count:,}")
        m_col3.metric("Medium Risk", f"{med_count:,}")
        m_col4.metric("Low Risk", f"{low_count:,}")

        st.markdown(
            f'<div style="background-color: {COLOR_SURFACE}; padding: 16px; '
            f'border-radius: 8px; margin: 16px 0;">'
            f'<h4 style="color: {COLOR_PRIMARY}; margin-top: 0;">📑 Included Workpaper Sheets</h4>'
            f'<ul style="margin-bottom: 0; line-height: 1.8;">'
            f"<li><b>Summary</b>: Executive scorecard, dataset metadata, and active settings</li>"
            f"<li><b>Flagged Transactions</b>: Full line-item exceptions, risk points, reasons</li>"
            f"<li><b>Rule Counts</b>: Rule-by-rule breakdown (R1 - R6) and category mappings</li>"
            f"<li><b>Benford</b>: Leading-digit distribution and conformity metrics</li>"
            f"<li><b>Review Log</b>: Complete audit disposition history and notes</li>"
            f"</ul>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 5. Report Fetch and Download Button
        with st.spinner("Preparing Excel workpaper report..."):
            try:
                report_bytes = handle_api_call(
                    api_client.get_report, token, run_id=selected_run_id, format="xlsx"
                )
                file_name = f"auditlens_report_run_{selected_run_id}.xlsx"

                d_col1, d_col2 = st.columns([2, 1])
                with d_col1:
                    st.download_button(
                        label="📥 Download Excel Audit Report (.xlsx)",
                        data=report_bytes,
                        file_name=file_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True,
                    )
                with d_col2:
                    st.caption(
                        "🛡️ **Formula Injection Protected**: All exported cells are neutralized "
                        "against spreadsheet execution vulnerabilities."
                    )

            except ApiClientError as err:
                st.error(f"Failed to generate report: {err.message}")
