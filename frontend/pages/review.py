"""Flagged Transactions Review and Manager Sign-Off view (UX_FLOWS.md Flows 5 & 6)."""

import math
from typing import Any

import pandas as pd
import streamlit as st

from frontend.api_client import ApiClientError, ConflictError, ValidationError, api_client
from frontend.components.auth_guard import (
    get_current_user,
    get_token,
    handle_api_call,
    is_manager,
    render_sidebar,
)
from frontend.components.badges import (
    format_currency,
    format_datetime,
    get_risk_badge_html,
    get_status_badge_html,
)
from frontend.constants import STATUS_LABELS


def render_review_page() -> None:
    """Render the exception investigation workbench and manager sign-off workflow."""
    render_sidebar()
    token = get_token()
    if not token:
        st.warning("Please sign in to access the review workbench.")
        return

    st.title("Audit Exceptions Review")
    st.caption(
        "Inspect flagged items, review audit evidence, record dispositions, "
        "and sign off completed workpapers."
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

    # 2. Fetch run details
    try:
        run_detail = handle_api_call(api_client.get_run, token, run_id=selected_run_id)
    except ApiClientError as err:
        st.error(f"Error fetching run details: {err.message}")
        return

    is_signed_off = run_detail.get("signed_off_by") is not None
    signed_off_at = format_datetime(run_detail.get("signed_off_at"))

    # Signed-off Banner or Status Header
    if is_signed_off:
        st.success(
            f"🔒 **Signed Off**: This run was officially signed off on {signed_off_at}. "
            "All review decisions are locked and archived."
        )

    # 3. Filter Controls
    with st.expander("Filter & Search Exceptions", expanded=True):
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)

        with f_col1:
            sel_risk_levels = st.multiselect(
                "Risk Level",
                options=["high", "medium", "low"],
                format_func=lambda x: x.upper(),
                default=[],
            )
            sel_status = st.selectbox(
                "Review Status",
                options=["all", "open", "reviewed", "false_positive", "needs_follow_up"],
                format_func=lambda x: "All" if x == "all" else STATUS_LABELS.get(x, x),
            )

        with f_col2:
            sel_rules = st.multiselect(
                "Triggered Rule",
                options=["R1", "R2", "R3", "R4", "R5", "R6"],
                default=[],
            )
            vendor_search = st.text_input("Vendor ID", placeholder="e.g. VEND-1042")

        with f_col3:
            dept_search = st.text_input("Department", placeholder="e.g. Finance")
            sort_by = st.selectbox(
                "Sort By",
                options=["risk_score", "amount", "posting_date"],
                format_func=lambda x: {
                    "risk_score": "Risk Score",
                    "amount": "Transaction Amount",
                    "posting_date": "Posting Date",
                }.get(x, x),
            )

        with f_col4:
            sort_dir = st.selectbox(
                "Sort Order",
                options=["desc", "asc"],
                format_func=lambda x: "Descending" if x == "desc" else "Ascending",
            )
            amt_min = st.number_input("Min Amount (₹)", min_value=0.0, value=0.0, step=5000.0)

    # 4. Server-Side Pagination
    page_size = 50
    curr_page = st.session_state.get(f"review_page_{selected_run_id}", 1)

    with st.spinner("Fetching flagged transactions..."):
        try:
            flagged_res = handle_api_call(
                api_client.list_flagged,
                token,
                run_id=selected_run_id,
                page=curr_page,
                page_size=page_size,
                risk_level=sel_risk_levels or None,
                rule=sel_rules or None,
                vendor_id=vendor_search.strip() or None,
                department=dept_search.strip() or None,
                review_status=sel_status if sel_status != "all" else None,
                amount_min=amt_min if amt_min > 0 else None,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
        except ApiClientError as err:
            st.error(f"Error fetching flagged transactions: {err.message}")
            return

    total_items = flagged_res.get("total", 0)
    items = flagged_res.get("items", [])
    total_pages = max(1, math.ceil(total_items / page_size))

    # Review Progress Indicator
    # Compute review status counts across the run if available
    try:
        open_items_check = handle_api_call(
            api_client.list_flagged,
            token,
            run_id=selected_run_id,
            page=1,
            page_size=1,
            review_status="open",
        )
        open_count = open_items_check.get("total", 0)
    except Exception:
        open_count = 0

    reviewed_count = max(0, total_items - open_count)
    progress_ratio = (reviewed_count / total_items) if total_items > 0 else 1.0

    p_col1, p_col2 = st.columns([3, 1])
    with p_col1:
        st.write(
            f"**Review Progress:** {reviewed_count:,} of {total_items:,} items dispositioned "
            f"({progress_ratio * 100:.1f}%)"
        )
        st.progress(progress_ratio)
    with p_col2:
        st.metric("Pending Open Items", f"{open_count:,}")

    # Manager Sign-Off Section (Flow 6)
    if is_manager():
        _render_manager_signoff(token, selected_run_id, is_signed_off, open_count)

    st.markdown("---")

    if not items:
        st.info("No flagged transactions match the specified filters.")
        return

    # Render Paginated Table
    st.subheader(f"Flagged Transactions ({total_items:,} total exceptions)")

    # Build display table
    display_rows = []
    for item in items:
        display_rows.append(
            {
                "Flagged ID": item["id"],
                "Transaction ID": item["transaction_id"],
                "Posting Date": format_datetime(item.get("posting_date")),
                "Amount": format_currency(item.get("amount")),
                "Vendor": item.get("vendor_id", "Unknown"),
                "Department": item.get("department") or "—",
                "Risk Score": item.get("risk_score", 0),
                "Risk Level": str(item.get("risk_level", "low")).upper(),
                "Rules": ", ".join(item.get("triggered_rules", [])),
                "Status": STATUS_LABELS.get(item["review_status"], item["review_status"]),
            }
        )

    st.dataframe(
        pd.DataFrame(display_rows),
        use_container_width=True,
        hide_index=True,
    )

    # Pagination controls
    pag_col1, pag_col2, pag_col3 = st.columns([1, 2, 1])
    with pag_col1:
        if st.button("⬅️ Previous", disabled=curr_page <= 1):
            st.session_state[f"review_page_{selected_run_id}"] = curr_page - 1
            st.rerun()
    with pag_col2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 6px;'>"
            f"Page <b>{curr_page}</b> of <b>{total_pages}</b> ({total_items:,} items)"
            f"</div>",
            unsafe_allow_html=True,
        )
    with pag_col3:
        if st.button("Next ➡️", disabled=curr_page >= total_pages):
            st.session_state[f"review_page_{selected_run_id}"] = curr_page + 1
            st.rerun()

    # 5. Detail & Review Panel (Flow 5)
    st.markdown("---")
    st.subheader("Transaction Investigation Panel")

    item_options = {
        f"ID #{it['id']} - {it['transaction_id']} "
        f"(Risk: {it['risk_score']} {it['risk_level'].upper()}, "
        f"{format_currency(it['amount'])})": it["id"]
        for it in items
    }
    sel_item_label = st.selectbox(
        "Select transaction to inspect:", options=list(item_options.keys())
    )
    sel_flagged_id = item_options[sel_item_label]

    with st.spinner("Loading transaction audit detail..."):
        try:
            detail = handle_api_call(
                api_client.get_flagged_detail, token, flagged_id=sel_flagged_id
            )
        except ApiClientError as err:
            st.error(f"Error loading transaction detail: {err.message}")
            return

    _render_detail_panel(token, detail, is_signed_off)


def _render_detail_panel(token: str, detail: dict[str, Any], is_signed_off: bool) -> None:
    """Render comprehensive transaction audit detail, duplicate group, history, and review form."""
    with st.container(border=True):
        d_top1, d_top2, d_top3 = st.columns([2, 1, 1])
        with d_top1:
            st.markdown(f"### Transaction `{detail.get('transaction_id')}`")
            post_date = format_datetime(detail.get("posting_date"))
            st.markdown(
                f"**Vendor:** `{detail.get('vendor_id')}` | **Posting Date:** `{post_date}`"
            )
        with d_top2:
            st.metric("Transaction Amount", format_currency(detail.get("amount")))
        with d_top3:
            badge_html = get_risk_badge_html(detail.get("risk_level", "low"))
            score_val = detail.get("risk_score")
            st.markdown(
                f"**Risk Score:** <span style='font-size: 1.4rem; font-weight: 700;'>"
                f"{score_val} / 100</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"Tier: {badge_html}", unsafe_allow_html=True)

        st.markdown("---")

        # Fields & Score Breakdown
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown("#### Transaction Metadata")
            st.write(f"- **Department:** {detail.get('department') or '—'}")
            st.write(f"- **Account Code:** {detail.get('account_code') or '—'}")
            st.write(f"- **Created By:** `{detail.get('created_by') or '—'}`")
            st.write(f"- **Approved By:** `{detail.get('approved_by') or '—'}`")
            st.write(f"- **Description:** {detail.get('description') or '—'}")

        with c_right:
            st.markdown("#### Risk Score Breakdown")
            rule_pts = detail.get("rule_points", 0)
            ml_pts = detail.get("ml_points", 0)
            ml_norm = detail.get("ml_norm", 0.0)

            st.write(f"- **Rule Points:** `{rule_pts}` (capped at 100)")
            st.write(f"- **ML Anomaly Points:** `{ml_pts}` (Norm Score: `{ml_norm:.4f}`)")
            comb_score = detail.get("risk_score")
            st.write(f"- **Combined Score:** `min(100, {rule_pts} + {ml_pts}) = {comb_score}`")

            st.markdown("##### Plain-English Reasons:")
            reasons = detail.get("reasons", [])
            if reasons:
                for r in reasons:
                    st.markdown(f"- 🔴 {r}")
            else:
                st.write("— None specified —")

        # Duplicate Group Members (if applicable)
        dup_members = detail.get("duplicate_group_members", [])
        if dup_members:
            st.markdown("---")
            st.markdown(
                f"#### 👥 Duplicate Payment Group ({len(dup_members)} related transaction(s))"
            )
            st.caption(f"Duplicate Group ID: `{detail.get('duplicate_group_id')}`")
            dup_rows = [
                {
                    "Transaction ID": m["transaction_id"],
                    "Posting Date": format_datetime(m.get("posting_date")),
                    "Amount": format_currency(m.get("amount")),
                    "Vendor": m.get("vendor_id"),
                    "Risk Score": m.get("risk_score"),
                    "Status": STATUS_LABELS.get(m["review_status"], m["review_status"]),
                }
                for m in dup_members
            ]
            st.dataframe(pd.DataFrame(dup_rows), use_container_width=True, hide_index=True)

        # Review History
        st.markdown("---")
        st.markdown("#### Audit Trail & Review Log")
        reviews = detail.get("reviews", [])
        if reviews:
            for rev in reviews:
                rev_date = format_datetime(rev.get("created_at"))
                st.markdown(
                    f"- **{rev.get('reviewer_name') or 'Auditor'}** marked as "
                    f"`{STATUS_LABELS.get(rev['status'], rev['status'])}` on "
                    f"`{rev_date}`: "
                    f"*{rev.get('comment') or 'No comment'}*"
                )
        else:
            st.caption("No prior review actions recorded for this transaction.")

        # Review Action Form
        st.markdown("---")
        st.markdown("#### Record Review Disposition")

        current_status = detail.get("review_status", "open")
        st.markdown(
            f"Current Status: {get_status_badge_html(current_status)}", unsafe_allow_html=True
        )

        if is_signed_off:
            st.info("🔒 This run has been signed off. Review decisions cannot be modified.")
            return

        with st.form(f"review_form_{detail['id']}"):
            new_status = st.selectbox(
                "Audit Disposition",
                options=["reviewed", "false_positive", "needs_follow_up", "open"],
                index=["reviewed", "false_positive", "needs_follow_up", "open"].index(
                    current_status
                    if current_status in ["reviewed", "false_positive", "needs_follow_up", "open"]
                    else "reviewed"
                ),
                format_func=lambda s: STATUS_LABELS.get(s, s),
            )
            comment = st.text_area(
                "Reviewer Justification & Audit Notes",
                placeholder="Required for False Positive. Explain testing performed.",
            )
            save_click = st.form_submit_button("💾 Save Review Decision", type="primary")

            if save_click:
                # Validation: comment mandatory for false_positive per API.md
                if new_status == "false_positive" and not comment.strip():
                    st.error("A justification comment is required for False Positive disposition.")
                else:
                    try:
                        handle_api_call(
                            api_client.review_flagged,
                            token,
                            flagged_id=detail["id"],
                            status=new_status,
                            comment=comment.strip() or None,
                        )
                        st.success("Review decision saved successfully.")
                        st.rerun()
                    except ValidationError as err:
                        st.error(f"Validation error: {err.message}")
                    except ConflictError as err:
                        st.error(f"Conflict error: {err.message}")
                    except ApiClientError as err:
                        st.error(f"Failed to record review: {err.message}")


def _render_manager_signoff(token: str, run_id: int, is_signed_off: bool, open_count: int) -> None:
    """Render manager-only sign-off controls (Flow 6)."""
    with st.container(border=True):
        st.markdown("#### ✍️ Manager Official Sign-Off")

        if is_signed_off:
            st.write("This audit run has been officially signed off and closed.")
            return

        user = get_current_user()
        st.caption(f"Logged in as Manager: **{user.get('full_name') if user else 'Manager'}**")

        if open_count > 0:
            st.warning(
                f"Cannot sign off run: **{open_count:,}** item(s) are still Open. "
                "All exceptions must be dispositioned prior to sign-off."
            )
            st.button("Official Sign-Off", disabled=True, help="Complete review of all items first")
        else:
            st.success(
                "All flagged exceptions have been dispositioned. Ready for manager sign-off."
            )
            with st.popover("Confirm Official Sign-Off", use_container_width=False):
                st.markdown(
                    "By clicking below, you officially certify that all flagged exceptions "
                    "have been audited and dispositioned per organizational policy. "
                    "**This action locks the run and cannot be undone.**"
                )
                if st.button("Confirm Sign-Off & Lock Run", type="primary"):
                    try:
                        handle_api_call(api_client.sign_off_run, token, run_id=run_id)
                        st.success("Analysis run successfully signed off and locked!")
                        st.rerun()
                    except ConflictError as err:
                        st.error(f"Cannot sign off: {err.message}")
                    except ApiClientError as err:
                        st.error(f"Sign-off failed: {err.message}")
