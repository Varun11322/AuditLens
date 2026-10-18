"""Benford's Law Analysis view (AUDIT_RULES.md Section 4 & UX_FLOWS.md)."""

import pandas as pd
import streamlit as st

from frontend.api_client import ApiClientError, api_client
from frontend.components.auth_guard import get_token, handle_api_call, render_sidebar
from frontend.components.badges import format_datetime
from frontend.components.charts import create_benford_chart
from frontend.constants import COLOR_PRIMARY, COLOR_RISK_HIGH, COLOR_SUCCESS, COLOR_WARNING


def render_benford_page() -> None:
    """Render the Benford's Law digit distribution analysis and vendor-level compliance view."""
    render_sidebar()
    token = get_token()
    if not token:
        st.warning("Please sign in to access Benford analysis.")
        return

    st.title("Benford's Law Analysis")
    st.caption(
        "First-digit frequency analysis to detect non-natural digit distributions "
        "and potential manipulation."
    )

    # 1. Fetch uploads and completed runs
    try:
        uploads_resp = handle_api_call(api_client.list_uploads, token, page=1, page_size=50)
        uploads = uploads_resp.get("items", [])
    except ApiClientError as err:
        st.error(f"Error fetching uploads: {err.message}")
        return

    if not uploads:
        st.info("No uploads found. Please upload a transaction ledger first.")
        return

    upload_options = {f"{u['id']}: {u['original_filename']}": u["id"] for u in uploads}
    curr_up_id = st.session_state.get("current_upload_id")
    def_up_idx = 0
    if curr_up_id:
        for idx, up_id in enumerate(upload_options.values()):
            if up_id == curr_up_id:
                def_up_idx = idx
                break

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        sel_up_label = st.selectbox(
            "Select Upload", options=list(upload_options.keys()), index=def_up_idx
        )
    selected_up_id = upload_options[sel_up_label]
    st.session_state["current_upload_id"] = selected_up_id

    # Runs for upload
    try:
        runs = handle_api_call(api_client.list_runs_for_upload, token, upload_id=selected_up_id)
    except ApiClientError as err:
        st.error(f"Error fetching runs: {err.message}")
        return

    completed_runs = [r for r in runs if r.get("status") == "completed"]
    if not completed_runs:
        st.info(f"No completed analysis runs for '{sel_up_label}'.")
        return

    run_options = {
        f"Run #{r['id']} ({format_datetime(r.get('finished_at'))})": r["id"] for r in completed_runs
    }
    curr_run_id = st.session_state.get("current_run_id")
    def_run_idx = 0
    if curr_run_id:
        for idx, r_id in enumerate(run_options.values()):
            if r_id == curr_run_id:
                def_run_idx = idx
                break

    with col_u2:
        sel_run_label = st.selectbox(
            "Select Run", options=list(run_options.keys()), index=def_run_idx
        )
    selected_run_id = run_options[sel_run_label]
    st.session_state["current_run_id"] = selected_run_id

    # 2. Fetch Benford results
    with st.spinner("Calculating Benford first-digit metrics..."):
        try:
            benford = handle_api_call(api_client.get_benford, token, run_id=selected_run_id)
        except ApiClientError as err:
            st.error(f"Failed to fetch Benford results: {err.message}")
            return

    if not benford.get("available"):
        reason = benford.get("reason", "insufficient data")
        st.info(
            f"Benford's Law analysis is unavailable for this run ({reason}). "
            "Requires at least 1,000 transactions."
        )
        return

    # 3. Overall Metrics Row
    conf_label = benford.get("conformity_label", "Evaluated")
    mad = benford.get("mad", 0.0)
    chi_sq = benford.get("chi_square", 0.0)
    p_val = benford.get("p_value", 0.0)
    sample_size = benford.get("sample_size", 0)

    # Color code conformity badge
    if "close" in conf_label.lower():
        conf_color = COLOR_SUCCESS
    elif "acceptable" in conf_label.lower():
        conf_color = COLOR_PRIMARY
    elif "marginal" in conf_label.lower():
        conf_color = COLOR_WARNING
    else:
        conf_color = COLOR_RISK_HIGH

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"**Nigrini Conformity:**<br>"
            f"<span style='color: {conf_color}; font-size: 1.3rem; font-weight: 700;'>"
            f"{conf_label}</span>",
            unsafe_allow_html=True,
        )
    m2.metric("Mean Absolute Deviation (MAD)", f"{mad:.4f}")
    p_compact = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    with m3:
        st.metric("Chi-Square", f"{chi_sq:.2f}", help=f"Chi-square p-value: {p_compact}")
        st.caption(p_compact)
    m4.metric("Sample Size", f"{sample_size:,}")

    st.caption(
        "ℹ️ **Audit Context**: Non-conformity is a signal for investigation, "
        "not proof of fraud or irregular activity."
    )

    # 4. Chart: Observed vs Expected Distribution
    st.markdown("---")
    st.subheader("First-Digit Observed vs. Expected Distribution")

    # Map keys to int if needed
    obs_freq = {
        int(k): float(v)
        for k, v in benford.get("observed_frequencies", benford.get("observed", {})).items()
    }
    exp_freq = {
        int(k): float(v)
        for k, v in benford.get("expected_frequencies", benford.get("expected", {})).items()
    }

    chart = create_benford_chart(obs_freq, exp_freq)
    st.plotly_chart(chart, use_container_width=True)

    # 5. Vendor-Level Benford Analysis
    st.markdown("---")
    st.subheader("Vendor-Level First-Digit Conformity")
    st.caption("Evaluated on vendors with at least 300 transactions per AUDIT_RULES.md section 4.")

    per_vendor = benford.get("per_vendor", [])
    non_conf = benford.get("non_conformant_vendors", [])

    if non_conf:
        st.warning(
            f"⚠️ **{len(non_conf)} vendor(s) flagged with Non-conformity** "
            f"(MAD > 0.015) — worth a closer look: {', '.join(non_conf)}"
        )

    if per_vendor:
        vendor_rows = []
        for v in per_vendor:
            vendor_rows.append(
                {
                    "Vendor ID": v.get("vendor_id"),
                    "Transaction Count": f"{v.get('transaction_count', 0):,}",
                    "MAD": f"{v.get('mad', 0.0):.4f}",
                    "Conformity": v.get("conformity_label", ""),
                    "Flagged": "⚠️ Non-conformity" if v.get("vendor_id") in non_conf else "Normal",
                }
            )

        st.dataframe(pd.DataFrame(vendor_rows), use_container_width=True, hide_index=True)
    else:
        st.info(
            "No individual vendors had at least 300 transactions to qualify "
            "for separate Benford analysis."
        )
