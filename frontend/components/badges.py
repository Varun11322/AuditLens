"""Formatting helpers and visual badges for risk levels and review statuses."""

from frontend.constants import COLOR_SURFACE, COLOR_TEXT, RISK_COLORS, STATUS_COLORS, STATUS_LABELS


def format_currency(amount: float | int | None) -> str:
    """Format an amount into INR currency representation with thousands separators."""
    if amount is None:
        return "₹ 0.00"
    return f"₹ {amount:,.2f}"


def get_risk_badge_html(level: str) -> str:
    """Return inline HTML for a risk badge with explicit text label and brand color.

    Per docs/DESIGN_SYSTEM.md, risk is always communicated by label and color together.
    """
    clean_level = (level or "low").lower()
    color = RISK_COLORS.get(clean_level, "#5F6C74")
    label = clean_level.upper()
    return (
        f'<span style="background-color: {color}20; color: {color}; '
        f"border: 1px solid {color}60; padding: 2px 8px; border-radius: 4px; "
        f'font-weight: 600; font-size: 0.85rem; letter-spacing: 0.5px;">'
        f"{label}</span>"
    )


def get_status_badge_html(status: str) -> str:
    """Return inline HTML for a review status badge."""
    clean_status = (status or "open").lower()
    color = STATUS_COLORS.get(clean_status, "#5F6C74")
    label = STATUS_LABELS.get(clean_status, clean_status.replace("_", " ").title())
    return (
        f'<span style="background-color: {COLOR_SURFACE}; color: {COLOR_TEXT}; '
        f"border: 1px solid {color}; padding: 2px 8px; border-radius: 4px; "
        f'font-size: 0.85rem; display: inline-flex; align-items: center; gap: 4px;">'
        f'<span style="width: 8px; height: 8px; border-radius: 50%; '
        f'background-color: {color}; display: inline-block;"></span>'
        f"{label}</span>"
    )
