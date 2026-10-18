"""Authentication guard, session management, and sidebar rendering."""

from collections.abc import Callable
from typing import Any

import streamlit as st

from frontend.api_client import AuthenticationError
from frontend.constants import COLOR_PRIMARY, COLOR_SURFACE, COLOR_TEXT


def get_token() -> str | None:
    """Retrieve current JWT token from Streamlit session state."""
    return st.session_state.get("token")


def get_current_user() -> dict[str, Any] | None:
    """Retrieve currently authenticated user profile from Streamlit session state."""
    return st.session_state.get("user")


def is_manager() -> bool:
    """Check if current user has the 'manager' role."""
    user = get_current_user()
    return bool(user and user.get("role") == "manager")


def logout() -> None:
    """Clear credentials from session state and reload."""
    st.session_state.pop("token", None)
    st.session_state.pop("user", None)
    st.session_state["auth_error"] = "You have been logged out."
    st.rerun()


def handle_api_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Execute an API client call and catch 401 session expiry to return to Login."""
    try:
        return func(*args, **kwargs)
    except AuthenticationError:
        st.session_state.pop("token", None)
        st.session_state.pop("user", None)
        st.session_state["auth_error"] = "Your session has expired. Please log in again."
        st.rerun()


def render_sidebar() -> None:
    """Render consistent sidebar with AuditLens branding, user profile, and logout button."""
    user = get_current_user()
    with st.sidebar:
        st.markdown(
            f'<div style="padding: 8px 0 16px 0;">'
            f'<h2 style="margin: 0; color: {COLOR_PRIMARY}; '
            f'font-weight: 700; letter-spacing: -0.5px;">AuditLens</h2>'
            f'<p style="margin: 2px 0 0 0; color: {COLOR_TEXT}; '
            f'font-size: 0.85rem; opacity: 0.7;">Audit Anomaly Detection</p>'
            f"</div>",
            unsafe_allow_html=True,
        )

        if user:
            role = user.get("role", "auditor").capitalize()
            role_badge_color = "#1F6F5C" if role == "Manager" else "#2F4858"
            name = user.get("full_name", "User")
            email = user.get("email", "")
            st.markdown(
                f'<div style="background-color: {COLOR_SURFACE}; border-radius: 8px; '
                f'padding: 12px; margin-bottom: 16px; border: 1px solid #DDE3E6;">'
                f'<div style="font-weight: 600; color: {COLOR_TEXT};">{name}</div>'
                f'<div style="font-size: 0.8rem; color: #5F6C74; margin-bottom: 6px;">{email}</div>'
                f'<span style="background-color: {role_badge_color}20; color: {role_badge_color}; '
                f"font-weight: 600; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; "
                f'border: 1px solid {role_badge_color}40;">{role}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

            if st.button("Logout", key="sidebar_logout_btn", use_container_width=True):
                logout()

        st.divider()
