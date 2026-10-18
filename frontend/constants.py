"""Frontend constants, theme tokens, and default configuration values."""

# Brand colors from docs/DESIGN_SYSTEM.md
COLOR_PRIMARY = "#1F6F5C"
COLOR_SECONDARY = "#2F4858"
COLOR_BACKGROUND = "#FFFFFF"
COLOR_SURFACE = "#F5F7F8"
COLOR_TEXT = "#1B2A33"
COLOR_MUTED_TEXT = "#5F6C74"
COLOR_BORDER = "#DDE3E6"
COLOR_SUCCESS = "#2E8B57"
COLOR_WARNING = "#D9902F"
COLOR_ERROR = "#C0392B"

# Risk colors (always paired with text labels)
COLOR_RISK_HIGH = "#C0392B"
COLOR_RISK_MEDIUM = "#D9902F"
COLOR_RISK_LOW = "#E5C100"

RISK_COLORS = {
    "high": COLOR_RISK_HIGH,
    "medium": COLOR_RISK_MEDIUM,
    "low": COLOR_RISK_LOW,
}

# Review status labels & styling
STATUS_COLORS = {
    "open": "#5F6C74",
    "reviewed": "#2E8B57",
    "false_positive": "#2F4858",
    "needs_follow_up": "#D9902F",
}

STATUS_LABELS = {
    "open": "Open",
    "reviewed": "Reviewed",
    "false_positive": "False Positive",
    "needs_follow_up": "Needs Follow-up",
}

# Default audit rules thresholds from AUDIT_RULES.md section 2
DEFAULT_SETTINGS = {
    "approval_limit": 100000.0,
    "just_below_band": 0.90,
    "duplicate_window_days": 7,
    "round_multiple": 1000.0,
    "round_min_amount": 10000.0,
    "business_hours_start": 8,
    "business_hours_end": 20,
    "missing_approver_min_amount": 10000.0,
    "ml_contamination": 0.02,
    "ml_min_rows": 50,
    "flag_threshold": 30,
    "random_seed": 42,
}

RULE_DESCRIPTIONS = {
    "R1": "Self-approval: Created and approved by the same user",
    "R2": "Duplicate payment: Identical vendor and amount within window",
    "R3": "Missing approver: Empty approver for transaction >= limit",
    "R4": "Just below limit: Amount in 90%-99.9% band below approval limit",
    "R5": "Round amount: Round multiple amount >= threshold",
    "R6": "Weekend / After-hours: Posted outside business hours or on weekend",
}
