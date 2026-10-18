"""Overview Dashboard view (UX_FLOWS.md Flow 4)."""

import streamlit as st

from frontend.api_client import ApiClientError, api_client
from frontend.components.auth_guard import get_token, handle_api_call, render_sidebar
from frontend.components.badges import format_currency
from frontend.components.charts import (
    create_risk_distribution_chart,
    create_rule_counts_chart,
    create_timeline_chart,
    create_top_vendors_chart,
)


def render_dashboard_page() -> None:
    """Render the audit metrics dashboard with Plotly charts and summary statistics."""
    render_sidebar()
    token = get_token()
    if not token:
        st.warning("Please sign in to access the dashboard.")
        return

    st.title("Audit Exceptions Dashboard")
    st.caption("Visual risk distribution, triggered rules, and anomalous patterns for ledger runs.")

    # 1. Fetch available uploads
    try:
        uploads_resp = handle_api_call(api_client.list_uploads, token, page=1, page_size=50)
        uploads = uploads_resp.get("items", [])
    except ApiClientError as err:
        st.error(f"Error fetching uploads: {err.message}")
        return

    if not uploads:
        st.info("No uploads found. Please upload a transaction ledger to begin.")
        if st.button("Go to Upload Page", type="primary"):
            st.session_state["nav_destination"] = "Upload"
            st.rerun()
        return

    # Select upload
    upload_options = {f"{u['id']}: {u['original_filename']}": u["id"] for u in uploads}
    default_upload_idx = 0
    curr_up_id = st.session_state.get("current_upload_id")
    if curr_up_id:
        for idx, up_id in enumerate(upload_options.values()):
            if up_id == curr_up_id:
                default_upload_idx = idx
                break

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
            f"No completed analysis runs for '{selected_up_label}'. "
            "Run an analysis from the Upload page."
        )
        if st.button("Go to Upload Page", type="primary"):
            st.session_state["nav_destination"] = "Upload"
            st.rerun()
        return

    # Select run
    run_options = {
        f"Run #{r['id']} ({r.get('finished_at', '')[:19].replace('T', ' ')})": r["id"]
        for r in completed_runs
    }
    default_run_idx = 0
    curr_run_id = st.session_state.get("current_run_id")
    if curr_run_id:
        for idx, r_id in enumerate(run_options.values()):
            if r_id == curr_run_id:
                default_run_idx = idx
                break

    selected_run_label = st.selectbox(
        "Select Analysis Run",
        options=list(run_options.keys()),
        index=default_run_idx,
    )
    selected_run_id = run_options[selected_run_label]
    st.session_state["current_run_id"] = selected_run_id

    # 3. Load run detail and flagged items
    with st.spinner("Loading run dashboard..."):
        try:
            run_detail = handle_api_call(api_client.get_run, token, run_id=selected_run_id)
            flagged_resp = handle_api_call(
                api_client.list_flagged,
                token,
                run_id=selected_run_id,
                page=1,
                page_size=200,
            )
            benford_resp = handle_api_call(api_client.get_benford, token, run_id=selected_run_id)
        except ApiClientError as err:
            st.error(f"Error loading dashboard data: {err.message}")
            return

    summary = run_detail.get("summary", {})
    scoring = summary.get("scoring", {})
    rules_sum = summary.get("rules", {})
    val_sum = summary.get("validation", {})

    total_txns = val_sum.get("accepted_rows", 0)
    total_flagged = flagged_resp.get("total", scoring.get("total_flagged", 0))

    by_level = scoring.get("by_level", {})
    high_count = by_level.get("High", by_level.get("high", 0))
    med_count = by_level.get("Medium", by_level.get("medium", 0))
    low_count = by_level.get("Low", by_level.get("low", 0))

    # Calculate total flagged amount from flagged sample or compute
    flagged_items = flagged_resp.get("items", [])
    total_flagged_amount = sum(float(item.get("amount", 0.0)) for item in flagged_items)
    if total_flagged > len(flagged_items) and len(flagged_items) > 0:
        # Scale estimate if sample is partial
        avg_flagged = total_flagged_amount / len(flagged_items)
        total_flagged_amount = avg_flagged * total_flagged

    pct_flagged = (total_flagged / total_txns * 100) if total_txns > 0 else 0.0

    st.markdown("---")

    # 4. Metrics Row
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Transactions", f"{total_txns:,}")
    m2.metric(
        "Flagged Exceptions",
        f"{total_flagged:,}",
        delta=f"{pct_flagged:.1f}% of total",
        delta_color="inverse",
    )
    m3.metric("High Risk", f"{high_count:,}")
    m4.metric("Medium Risk", f"{med_count:,}")
    m5.metric("Total Flagged Amount", format_currency(total_flagged_amount))

    # 5. Benford Summary Card
    with st.container(border=True):
        b_col1, b_col2 = st.columns([3, 1])
        with b_col1:
            st.markdown("##### Benford's Law First-Digit Conformity")
            if benford_resp.get("available"):
                conf_label = benford_resp.get("conformity_label", "Evaluated")
                mad_val = benford_resp.get("mad", 0.0)
                st.markdown(
                    f"**Overall Dataset Status:** "
                    f"<span style='font-size: 1.1rem; font-weight: 600;'>{conf_label}</span> "
                    f"(Mean Absolute Deviation: `{mad_val:.4f}`)",
                    unsafe_allow_html=True,
                )
                non_conf_v = benford_resp.get("non_conformant_vendors", [])
                if non_conf_v:
                    st.warning(
                        f"⚠️ {len(non_conf_v)} vendor(s) exhibited first-digit non-conformity."
                    )
            else:
                reason = benford_resp.get("reason", "Insufficient data")
                st.info(f"Benford analysis unavailable: {reason}.")
            st.caption(
                "ℹ️ Non-conformity is a statistical signal for investigation, not proof of fraud."
            )
        with b_col2:
            st.write("")
            if st.button("📊 View Benford Analysis", use_container_width=True):
                st.session_state["nav_destination"] = "Benford"
                st.rerun()

    # 6. Charts Grid
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        risk_fig = create_risk_distribution_chart(
            {"high": high_count, "medium": med_count, "low": low_count}
        )
        st.plotly_chart(risk_fig, use_container_width=True)

    with c_col2:
        rule_counts = rules_sum.get("counts_per_rule", {})
        rule_fig = create_rule_counts_chart(rule_counts)
        st.plotly_chart(rule_fig, use_container_width=True)

    # Secondary Charts
    c_col3, c_col4 = st.columns(2)
    with c_col3:
        # Timeline data aggregation from flagged items
        timeline_dict: dict[str, int] = {}
        for item in flagged_items:
            date_str = str(item.get("posting_date", ""))[:10]
            if date_str:
                timeline_dict[date_str] = timeline_dict.get(date_str, 0) + 1
        timeline_records = [{"date": d, "count": c} for d, c in sorted(timeline_dict.items())]
        time_fig = create_timeline_chart(timeline_records)
        st.plotly_chart(time_fig, use_container_width=True)

    with c_col4:
        # Top vendors by flagged amount
        vendor_dict: dict[str, float] = {}
        for item in flagged_items:
            v_id = item.get("vendor_id", "Unknown")
            amt = float(item.get("amount", 0.0))
            vendor_dict[v_id] = vendor_dict.get(v_id, 0.0) + amt
        sorted_vendors = [
            {"vendor_id": v, "amount": a}
            for v, a in sorted(vendor_dict.items(), key=lambda x: x[1], reverse=True)
        ]
        vendor_fig = create_top_vendors_chart(sorted_vendors)
        st.plotly_chart(vendor_fig, use_container_width=True)

    st.markdown("---")

    # 7. Navigation to Review
    r_col1, r_col2 = st.columns([3, 1])
    with r_col1:
        st.write("Ready to investigate flagged items and record audit dispositions?")
    with r_col2:
        if st.button("🔍 Review Flagged Transactions", type="primary", use_container_width=True):
            st.session_state["nav_destination"] = "Review"
            st.rerun()
