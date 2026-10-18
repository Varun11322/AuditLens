"""Model & Rule Evaluation workbench (PRD Feature 8, AUDIT_RULES.md Section 9).

Allows auditors to upload ground_truth.csv, compute strict & audit-adjusted precision,
recall, per-anomaly-type breakdown, and view plain-English explanations of supporting signals.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.api_client import ApiClientError, api_client
from frontend.components.auth_guard import get_token, handle_api_call, render_sidebar
from frontend.components.badges import format_datetime
from frontend.constants import COLOR_PRIMARY, COLOR_SURFACE

ANOMALY_TYPE_LABELS = {
    "duplicate": ("Duplicate Payment (R2)", "Cash Disbursement", "Strong Rule (40 pts)"),
    "self_approval": ("Self-Approval (R1)", "Segregation of Duties", "Strong Rule (40 pts)"),
    "missing_approver": ("Missing Approver (R3)", "Authorization Control", "Strong Rule (30 pts)"),
    "just_below_limit": (
        "Just Below Approval Limit (R4)",
        "Policy Evasion",
        "Strong Rule (40 pts)",
    ),
    "round": ("Round Amount (R5)", "Supporting Indicator", "Supporting Signal (10 pts)"),
    "weekend_afterhours": (
        "Weekend / After-Hours (R6)",
        "Supporting Indicator",
        "Supporting Signal (10 pts)",
    ),
    "random_outlier": (
        "Statistical Outlier",
        "Machine Learning",
        "Isolation Forest (0-40 pts)",
    ),
}


def render_evaluation_page() -> None:
    """Render the ground-truth benchmark and model evaluation workbench."""
    render_sidebar()
    token = get_token()
    if not token:
        st.warning("Please sign in to access model and rule evaluation.")
        return

    st.title("Model & Rule Evaluation")
    st.caption(
        "Benchmark detection performance against synthetic ground truth labels "
        "(PRD Feature 8 & AUDIT_RULES.md Section 9)."
    )

    # 1. Fetch uploads
    try:
        uploads_resp = handle_api_call(api_client.list_uploads, token, page=1, page_size=50)
        uploads = uploads_resp.get("items", [])
    except ApiClientError as err:
        st.error(f"Error fetching uploads: {err.message}")
        return

    if not uploads:
        st.info("No transaction uploads found. Please upload a dataset on the Upload page first.")
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
        st.info(f"No completed analysis runs found for '{selected_up_label}'.")
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

    st.markdown("---")

    # 3. Ground Truth File Uploader
    st.subheader("Upload Ground Truth Labels")
    st.markdown(
        "Upload the `ground_truth.csv` file generated alongside the synthetic ledger. "
        "The CSV must contain `transaction_id` and `anomaly_types` columns."
    )

    uploaded_gt = st.file_uploader(
        "Choose ground_truth.csv",
        type=["csv"],
        key=f"gt_uploader_{selected_run_id}",
    )

    eval_storage_key = f"eval_metrics_run_{selected_run_id}"

    if uploaded_gt is not None:
        if st.button("Evaluate Detection Performance", type="primary"):
            with st.spinner("Evaluating detections against ground truth..."):
                try:
                    file_bytes = uploaded_gt.getvalue()
                    metrics = handle_api_call(
                        api_client.evaluate_run,
                        token,
                        run_id=selected_run_id,
                        file_content=file_bytes,
                        filename=uploaded_gt.name,
                    )
                    st.session_state[eval_storage_key] = metrics
                    st.success("Evaluation completed successfully!")
                except ApiClientError as err:
                    st.error(f"Evaluation failed: {err.message}")
                    return

    metrics = st.session_state.get(eval_storage_key)
    if not metrics:
        st.info(
            "Upload a `ground_truth.csv` file above and click 'Evaluate Detection Performance'."
        )
        return

    # 4. Scorecard Metrics
    st.markdown("---")
    st.subheader("Benchmark Scorecard")

    strict_p = metrics.get("strict_precision", 0.0) * 100.0
    audit_p = metrics.get("audit_adjusted_precision", 0.0) * 100.0
    rec = metrics.get("overall_recall", 0.0) * 100.0
    tp_strict = metrics.get("strict_true_positives", 0)
    total_anom = metrics.get("total_anomalies", 0)
    total_flagged = metrics.get("total_flagged", 0)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            "Strict Precision",
            f"{strict_p:.1f}%",
            help="Injected anomaly clones only count as true positives.",
        )
        st.caption(f"{tp_strict:,} TP / {total_flagged:,} Flagged")
    with m2:
        st.metric(
            "Audit-Adjusted Precision",
            f"{audit_p:.1f}%",
            help="Recognizes both original donor and duplicate copy as valid detections per R2.",
        )
        st.caption(f"{metrics.get('audit_adjusted_true_positives', 0):,} Valid / {total_flagged:,}")
    with m3:
        st.metric(
            "Overall Recall",
            f"{rec:.1f}%",
            help="Proportion of all injected anomalies successfully detected.",
        )
        st.caption(f"{tp_strict:,} of {total_anom:,} detected")
    with m4:
        st.metric(
            "Total Injected Anomalies",
            f"{total_anom:,}",
        )
        st.caption(f"{total_flagged:,} flagged exceptions")

    # 5. Recall Breakdown by Anomaly Type Table
    st.markdown("---")
    st.subheader("Recall Breakdown by Anomaly Type")
    st.caption(
        "Evaluates detection recall across strong audit rules (R1-R4), "
        "supporting indicators (R5-R6), and ML isolation forest outliers."
    )

    by_type = metrics.get("recall_by_type", {})
    table_rows = []
    for atype, meta in ANOMALY_TYPE_LABELS.items():
        type_stats = by_type.get(atype, {})
        injected = type_stats.get("total_injected", 0)
        detected = type_stats.get("detected", 0)
        recall_pct = type_stats.get("recall", 0.0) * 100.0

        if injected == 0:
            status_str = "Not Injected"
        elif recall_pct >= 99.0:
            status_str = "100% Target Met"
        elif recall_pct >= 50.0:
            status_str = "Selective Signal"
        else:
            status_str = "Supporting Only"

        table_rows.append(
            {
                "Anomaly Type": meta[0],
                "Audit Category": meta[1],
                "Signal Type": meta[2],
                "Injected Count": f"{injected:,}",
                "Detected Count": f"{detected:,}",
                "Recall Rate": f"{recall_pct:.1f}%",
                "Status": status_str,
            }
        )

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    # 6. Plain-English Explanations
    st.markdown("---")
    st.subheader("Audit Context & Interpretations")

    with st.container(border=True):
        st.markdown(
            f'<div style="background-color: {COLOR_SURFACE}; padding: 16px; border-radius: 8px;">'
            f'<h4 style="color: {COLOR_PRIMARY}; margin-top: 0;">'
            f"💡 Why Audit-Adjusted Precision Differs from Strict Precision</h4>"
            f'<p style="color: #1B2A33; line-height: 1.6; margin-bottom: 0;">'
            f"{metrics.get('explanation')}"
            f"</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown(
            f'<div style="background-color: {COLOR_SURFACE}; padding: 16px; border-radius: 8px;">'
            f'<h4 style="color: {COLOR_PRIMARY}; margin-top: 0;">'
            f"🔍 Why Round Amounts (R5) and Weekend Postings (R6) are Supporting Signals</h4>"
            f'<p style="color: #1B2A33; line-height: 1.6;">'
            f"Under <b>AUDIT_RULES.md Section 3</b>, Round amounts (R5) and Weekend/After-Hours "
            f"postings (R6) are assigned <b>10 risk points each</b>. In genuine accounting "
            f"ledgers, many legitimate transactions are naturally rounded (such as recurring "
            f"retainers, stipends, or milestones) or entered outside business hours. "
            f"Flagging every single round or off-hour transaction would overwhelm audit teams "
            f"with false positives."
            f"</p>"
            f'<p style="color: #1B2A33; line-height: 1.6; margin-bottom: 0;">'
            f"Because AuditLens requires a minimum combined score of <b>30 points</b> to flag, "
            f"R5 and R6 only trigger an exception when combined with another triggered rule or "
            f"an elevated ML anomaly score. While rule-firing recall is 100%, flag recall is "
            f"intentionally selective to prioritize auditor attention on high-risk combinations."
            f"</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.caption(
        "ℹ️ **Note on Synthetic vs. Real Data**: Synthetic datasets possess known ground truth. "
        "In live enterprise audits, ground truth does not exist, and flagged exceptions represent "
        "potential risks requiring auditor inquiry rather than confirmed fraud."
    )
