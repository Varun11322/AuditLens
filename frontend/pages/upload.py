"""Upload Transactions & Run Analysis view (UX_FLOWS.md Flows 2, 3, 8)."""

import time
from typing import Any

import streamlit as st

from frontend.api_client import ApiClientError, api_client
from frontend.components.auth_guard import get_token, handle_api_call, render_sidebar
from frontend.components.badges import format_datetime
from frontend.constants import DEFAULT_SETTINGS


def render_upload_page() -> None:
    """Render the file upload, run configuration, and upload management page."""
    render_sidebar()
    token = get_token()
    if not token:
        st.warning("Please sign in to access this page.")
        return

    st.title("Transaction Ledger Upload")
    st.caption("Upload financial transaction journals in CSV or Excel (.xlsx) format.")

    # Top action: CSV Template download
    col_t1, col_t2 = st.columns([3, 1])
    with col_t2:
        try:
            template_bytes = handle_api_call(api_client.get_template_csv, token)
            st.download_button(
                label="📄 Download CSV Template",
                data=template_bytes,
                file_name="transaction_template.csv",
                mime="text/csv",
                use_container_width=True,
            )
        except Exception:
            pass

    # Upload Section
    with st.container(border=True):
        st.subheader("Upload New Ledger")
        uploaded_file = st.file_uploader(
            "Select transaction journal file (.csv or .xlsx)",
            type=["csv", "xlsx"],
            help="Files up to 25 MB are accepted. Must contain canonical columns.",
        )

        upload_btn = st.button("Upload & Validate", type="primary", disabled=uploaded_file is None)
        if upload_btn and uploaded_file is not None:
            with st.spinner("Validating file..."):
                file_bytes = uploaded_file.getvalue()
                try:
                    res = handle_api_call(
                        api_client.upload_file,
                        token,
                        file_bytes=file_bytes,
                        filename=uploaded_file.name,
                    )
                    st.session_state["latest_upload"] = res
                    st.session_state["current_upload_id"] = res["id"]
                    st.success(f"File '{uploaded_file.name}' successfully validated and stored!")
                except ApiClientError as err:
                    st.error(f"Upload failed: {err.message}")

    # Active/Latest Upload Details & Analysis Launcher
    latest_upload = st.session_state.get("latest_upload")
    if latest_upload:
        _render_upload_summary_and_run_launcher(token, latest_upload)

    st.markdown("---")
    _render_previous_uploads_table(token)


def _render_upload_summary_and_run_launcher(token: str, upload: dict[str, Any]) -> None:
    """Render validation metrics and the run analysis trigger with threshold controls."""
    with st.container(border=True):
        st.subheader(f"Ledger Validation Summary: {upload.get('original_filename')}")

        total = upload.get("row_count_total", 0)
        accepted = upload.get("row_count_accepted", 0)
        rejected = upload.get("row_count_rejected", 0)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Rows", f"{total:,}")
        c2.metric("Accepted Rows", f"{accepted:,}")
        c3.metric("Rejected Rows", f"{rejected:,}")

        val_summary = upload.get("validation_summary", {})
        rejection_reasons = val_summary.get("rejection_reasons", {})
        if rejection_reasons:
            with st.expander("Rejection Details", expanded=True):
                for reason, count in rejection_reasons.items():
                    st.write(f"- **{reason}**: {count} row(s)")

        skipped_rules = val_summary.get("skipped_rules", [])
        if skipped_rules:
            missing_cols = ", ".join(val_summary.get("missing_optional_columns", []))
            skipped_str = ", ".join(skipped_rules)
            st.warning(
                f"Optional columns missing: {missing_cols}. "
                f"The following rules will be skipped: {skipped_str}."
            )

        # Advanced Settings & Run Trigger
        st.markdown("#### Analysis Configuration")
        with st.expander("Advanced settings (thresholds & parameters)", expanded=False):
            st.caption("Defaults are pre-configured according to AUDIT_RULES.md.")
            col_s1, col_s2 = st.columns(2)

            with col_s1:
                approval_limit = st.number_input(
                    "Approval Limit (₹)",
                    min_value=1.0,
                    value=float(DEFAULT_SETTINGS["approval_limit"]),
                    step=10000.0,
                    help="Approval ceiling used for R4 (just below) and R3 (missing approver)",
                )
                just_below_band = st.number_input(
                    "Just Below Limit Band (0.0 - 1.0)",
                    min_value=0.5,
                    max_value=0.99,
                    value=float(DEFAULT_SETTINGS["just_below_band"]),
                    step=0.01,
                    help="Band start ratio (e.g. 0.90 flags 90% to 100% of approval limit)",
                )
                duplicate_window_days = st.number_input(
                    "Duplicate Window (Days)",
                    min_value=0,
                    max_value=90,
                    value=int(DEFAULT_SETTINGS["duplicate_window_days"]),
                    step=1,
                    help="Max days between identical vendor & amount transactions to flag R2",
                )
                round_multiple = st.number_input(
                    "Round Multiple (₹)",
                    min_value=10.0,
                    value=float(DEFAULT_SETTINGS["round_multiple"]),
                    step=100.0,
                    help="R5 round multiple flag condition",
                )
                round_min_amount = st.number_input(
                    "Round Minimum Amount (₹)",
                    min_value=0.0,
                    value=float(DEFAULT_SETTINGS["round_min_amount"]),
                    step=1000.0,
                    help="Minimum amount for R5 to apply",
                )
                missing_approver_min_amount = st.number_input(
                    "Missing Approver Min Amount (₹)",
                    min_value=0.0,
                    value=float(DEFAULT_SETTINGS["missing_approver_min_amount"]),
                    step=1000.0,
                    help="Minimum amount for R3 to apply",
                )

            with col_s2:
                business_hours_start = st.number_input(
                    "Business Hours Start (24h)",
                    min_value=0,
                    max_value=23,
                    value=int(DEFAULT_SETTINGS["business_hours_start"]),
                    step=1,
                )
                business_hours_end = st.number_input(
                    "Business Hours End (24h)",
                    min_value=0,
                    max_value=24,
                    value=int(DEFAULT_SETTINGS["business_hours_end"]),
                    step=1,
                )
                ml_contamination = st.number_input(
                    "ML Contamination Rate",
                    min_value=0.001,
                    max_value=0.5,
                    value=float(DEFAULT_SETTINGS["ml_contamination"]),
                    step=0.005,
                    format="%.3f",
                    help="Expected proportion of anomalies in Isolation Forest",
                )
                ml_min_rows = st.number_input(
                    "ML Minimum Rows",
                    min_value=5,
                    value=int(DEFAULT_SETTINGS["ml_min_rows"]),
                    step=10,
                )
                flag_threshold = st.number_input(
                    "Flag Threshold Score (0 - 100)",
                    min_value=0,
                    max_value=100,
                    value=int(DEFAULT_SETTINGS["flag_threshold"]),
                    step=5,
                    help="Combined risk score threshold to trigger an exception flag",
                )
                random_seed = st.number_input(
                    "Random Seed",
                    value=int(DEFAULT_SETTINGS["random_seed"]),
                    step=1,
                )

        settings_payload = {
            "approval_limit": float(approval_limit),
            "just_below_band": float(just_below_band),
            "duplicate_window_days": int(duplicate_window_days),
            "round_multiple": float(round_multiple),
            "round_min_amount": float(round_min_amount),
            "business_hours_start": int(business_hours_start),
            "business_hours_end": int(business_hours_end),
            "missing_approver_min_amount": float(missing_approver_min_amount),
            "ml_contamination": float(ml_contamination),
            "ml_min_rows": int(ml_min_rows),
            "flag_threshold": int(flag_threshold),
            "random_seed": int(random_seed),
        }

        run_id = st.session_state.get(f"active_run_{upload['id']}")
        run_in_progress = st.session_state.get("run_in_progress", False)

        run_click = st.button(
            "🚀 Run Audit Analysis",
            type="primary",
            disabled=run_in_progress or accepted == 0,
            key=f"run_btn_{upload['id']}",
        )

        if run_click:
            st.session_state["run_in_progress"] = True
            try:
                run_res = handle_api_call(
                    api_client.start_analysis,
                    token,
                    upload_id=upload["id"],
                    settings=settings_payload,
                )
                run_id = run_res["run_id"]
                st.session_state[f"active_run_{upload['id']}"] = run_id
                st.session_state["current_run_id"] = run_id
            except ApiClientError as err:
                st.session_state["run_in_progress"] = False
                st.error(f"Failed to start analysis: {err.message}")

        # Polling progress
        if st.session_state.get("run_in_progress") and run_id:
            status_container = st.empty()
            with status_container.container():
                st.info("Analysis running... executing audit rules and ML model...")
                progress_bar = st.progress(0.2)

            # Poll run status
            max_attempts = 60
            for attempt in range(max_attempts):
                time.sleep(2.0)
                try:
                    run_info = handle_api_call(api_client.get_run, token, run_id=run_id)
                    run_status = run_info.get("status")

                    if run_status == "completed":
                        st.session_state["run_in_progress"] = False
                        st.session_state["current_run_id"] = run_id
                        status_container.empty()
                        st.success(f"Analysis completed successfully! (Run #{run_id})")

                        summary = run_info.get("summary", {})
                        flagged_count = summary.get("flagged_transactions_count", 0)
                        runtime = summary.get("runtime_seconds", 0.0)
                        st.write(f"**{flagged_count:,}** flagged items detected in {runtime:.2f}s.")

                        warnings = summary.get("warnings", [])
                        for w in warnings:
                            st.warning(f"⚠️ {w}")

                        st.button(
                            "View Dashboard",
                            type="primary",
                            on_click=_set_page,
                            args=("Dashboard",),
                        )
                        break

                    if run_status == "failed":
                        st.session_state["run_in_progress"] = False
                        status_container.empty()
                        err_msg = run_info.get("error_message", "Unknown error")
                        st.error(f"Analysis failed: {err_msg}")
                        st.button("Retry Analysis", on_click=_reset_run_state, args=(upload["id"],))
                        break

                    # Still pending/running
                    progress_pct = min(0.9, 0.2 + (attempt * 0.03))
                    progress_bar.progress(progress_pct)

                except ApiClientError as err:
                    st.session_state["run_in_progress"] = False
                    status_container.empty()
                    st.error(f"Error polling run status: {err.message}")
                    break


def _render_previous_uploads_table(token: str) -> None:
    """Render list of previously uploaded datasets with cascade delete action (Flow 8)."""
    st.subheader("Previous Uploads")
    try:
        data = handle_api_call(api_client.list_uploads, token, page=1, page_size=20)
        items = data.get("items", [])
    except ApiClientError as err:
        st.error(f"Unable to load uploads: {err.message}")
        return

    if not items:
        st.info("No uploads yet. Upload a transaction file to begin.")
        return

    for item in items:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.markdown(f"**{item.get('original_filename')}** (ID: {item.get('id')})")
                st.caption(f"Uploaded: {format_datetime(item.get('created_at'))}")
            with col2:
                accepted = item.get("row_count_accepted", 0)
                total = item.get("row_count_total", 0)
                st.write(f"Accepted: **{accepted:,}** / {total:,}")
            with col3:
                if st.button("Select Upload", key=f"sel_up_{item['id']}"):
                    st.session_state["latest_upload"] = item
                    st.session_state["current_upload_id"] = item["id"]
                    st.rerun()
            with col4:
                # Delete with confirmation dialog
                with st.popover("🗑️ Delete", use_container_width=True):
                    st.warning(
                        "All related runs, flagged items, and reviews will be permanently deleted."
                    )
                    if st.button("Confirm Delete", type="primary", key=f"conf_del_{item['id']}"):
                        try:
                            handle_api_call(api_client.delete_upload, token, upload_id=item["id"])
                            st.success("Upload deleted.")
                            if st.session_state.get("current_upload_id") == item["id"]:
                                st.session_state.pop("latest_upload", None)
                                st.session_state.pop("current_upload_id", None)
                            st.rerun()
                        except ApiClientError as err:
                            st.error(f"Delete failed: {err.message}")


def _set_page(page_name: str) -> None:
    """Set destination navigation page."""
    st.session_state["nav_destination"] = page_name


def _reset_run_state(upload_id: int) -> None:
    """Reset run progress tracking state for retry."""
    st.session_state.pop(f"active_run_{upload_id}", None)
    st.session_state["run_in_progress"] = False
