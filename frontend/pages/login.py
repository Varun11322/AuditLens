"""Login view (UX_FLOWS.md Flow 1)."""

import streamlit as st

from frontend.api_client import ApiClientError, api_client
from frontend.constants import COLOR_PRIMARY


def render_login_page() -> None:
    """Render the user login screen."""
    # If already logged in, redirect
    if st.session_state.get("token"):
        st.info("You are already logged in.")
        return

    # Check for session expiry or logout messages
    if "auth_error" in st.session_state and st.session_state["auth_error"]:
        st.warning(st.session_state["auth_error"])
        st.session_state.pop("auth_error", None)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f'<div style="text-align: center; margin-bottom: 24px; padding-top: 40px;">'
            f'<h1 style="color: {COLOR_PRIMARY}; margin-bottom: 4px; '
            f'font-weight: 700;">AuditLens</h1>'
            f'<p style="color: #5F6C74; font-size: 1rem;">'
            f"Financial Transaction Anomaly Detection & Audit Intelligence</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.subheader("Sign In")

            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("Email", placeholder="name@organization.com")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                if submit:
                    if not email or not password:
                        st.error("Invalid email or password")
                    else:
                        try:
                            res = api_client.login(email=email.strip(), password=password)
                            st.session_state["token"] = res["access_token"]
                            st.session_state["user"] = res["user"]
                            st.rerun()
                        except ApiClientError:
                            # UX_FLOWS.md Flow 1: generic message, no hint about which one was wrong
                            st.error("Invalid email or password")
