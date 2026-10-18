"""Plotly chart builders aligned with docs/DESIGN_SYSTEM.md."""

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from frontend.constants import (
    COLOR_BORDER,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY,
    COLOR_RISK_HIGH,
    COLOR_RISK_LOW,
    COLOR_RISK_MEDIUM,
    COLOR_SECONDARY,
    COLOR_SURFACE,
    COLOR_TEXT,
    RULE_DESCRIPTIONS,
)


def _apply_theme(fig: go.Figure, title: str, x_title: str = "", y_title: str = "") -> go.Figure:
    """Apply consistent AuditLens styling to a Plotly figure."""
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=14, color=COLOR_TEXT, family="sans-serif"),
            x=0.0,
            y=0.96,
        ),
        xaxis=dict(
            title=dict(text=x_title, font=dict(size=12, color=COLOR_MUTED_TEXT)),
            tickfont=dict(size=11, color=COLOR_TEXT),
            gridcolor=COLOR_BORDER,
            zerolinecolor=COLOR_BORDER,
        ),
        yaxis=dict(
            title=dict(text=y_title, font=dict(size=12, color=COLOR_MUTED_TEXT)),
            tickfont=dict(size=11, color=COLOR_TEXT),
            gridcolor=COLOR_BORDER,
            zerolinecolor=COLOR_BORDER,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=50, b=40),
        font=dict(family="sans-serif", color=COLOR_TEXT),
        hoverlabel=dict(
            bgcolor=COLOR_SURFACE,
            font_size=12,
            font_family="sans-serif",
            bordercolor=COLOR_BORDER,
        ),
    )
    return fig


def create_risk_distribution_chart(risk_level_counts: dict[str, int]) -> go.Figure:
    """Create a bar chart showing flagged count per risk tier."""
    levels = ["High", "Medium", "Low"]
    counts = [
        risk_level_counts.get("high", 0),
        risk_level_counts.get("medium", 0),
        risk_level_counts.get("low", 0),
    ]
    colors = [COLOR_RISK_HIGH, COLOR_RISK_MEDIUM, COLOR_RISK_LOW]

    fig = go.Figure(
        data=[
            go.Bar(
                x=levels,
                y=counts,
                marker_color=colors,
                text=counts,
                textposition="auto",
                hovertemplate="<b>%{x} Risk</b><br>Flagged: %{y:,}<extra></extra>",
            )
        ]
    )
    return _apply_theme(fig, "Risk Level Distribution", "Risk Level", "Count")


def create_rule_counts_chart(rule_counts: dict[str, int]) -> go.Figure:
    """Create a bar chart showing violation count per rule."""
    rule_codes = ["R1", "R2", "R3", "R4", "R5", "R6"]
    counts = [rule_counts.get(r, 0) for r in rule_codes]
    descriptions = [RULE_DESCRIPTIONS.get(r, r) for r in rule_codes]

    fig = go.Figure(
        data=[
            go.Bar(
                x=rule_codes,
                y=counts,
                marker_color=COLOR_PRIMARY,
                text=counts,
                textposition="auto",
                customdata=descriptions,
                hovertemplate="<b>%{x}</b>: %{customdata}<br>Violations: %{y:,}<extra></extra>",
            )
        ]
    )
    return _apply_theme(fig, "Flagged Count by Rule", "Audit Rule", "Violations")


def create_timeline_chart(timeline_records: list[dict[str, Any]]) -> go.Figure:
    """Create a line / bar chart of flagged items over posting dates."""
    if not timeline_records:
        fig = go.Figure()
        return _apply_theme(fig, "Flagged Items Over Time", "Posting Date", "Flagged Count")

    df = pd.DataFrame(timeline_records)
    # Sort by date
    if "date" in df.columns and "count" in df.columns:
        df = df.sort_values("date")
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=df["date"],
                    y=df["count"],
                    mode="lines+markers",
                    line=dict(color=COLOR_PRIMARY, width=2.5),
                    marker=dict(size=6, color=COLOR_SECONDARY),
                    hovertemplate="<b>%{x}</b><br>Flagged: %{y}<extra></extra>",
                )
            ]
        )
    else:
        fig = go.Figure()

    return _apply_theme(fig, "Flagged Items Over Time", "Posting Date", "Flagged Count")


def create_top_vendors_chart(vendors: list[dict[str, Any]]) -> go.Figure:
    """Create a horizontal bar chart of top vendors by flagged amount."""
    if not vendors:
        fig = go.Figure()
        return _apply_theme(fig, "Top Vendors by Flagged Amount", "Amount (₹)", "Vendor")

    # Limit to top 10 and sort ascending for horizontal bar chart
    top = vendors[:10][::-1]
    vendor_ids = [v.get("vendor_id", "Unknown") for v in top]
    amounts = [v.get("amount", 0.0) for v in top]

    fig = go.Figure(
        data=[
            go.Bar(
                x=amounts,
                y=vendor_ids,
                orientation="h",
                marker_color=COLOR_SECONDARY,
                hovertemplate="<b>Vendor %{y}</b><br>Flagged Amount: ₹%{x:,.2f}<extra></extra>",
            )
        ]
    )
    return _apply_theme(fig, "Top Vendors by Flagged Amount", "Amount (₹)", "Vendor")


def create_benford_chart(
    observed_pct: dict[int, float], expected_pct: dict[int, float]
) -> go.Figure:
    """Create a grouped bar chart comparing observed vs expected Benford
    frequencies for digits 1 through 9.
    """
    digits = list(range(1, 10))
    obs_vals = [observed_pct.get(d, 0.0) * 100 for d in digits]
    exp_vals = [expected_pct.get(d, 0.0) * 100 for d in digits]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[str(d) for d in digits],
            y=obs_vals,
            name="Observed",
            marker_color=COLOR_PRIMARY,
            hovertemplate="Digit %{x}<br>Observed: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[str(d) for d in digits],
            y=exp_vals,
            name="Expected (Benford)",
            mode="lines+markers",
            line=dict(color=COLOR_RISK_HIGH, width=2.5, dash="dash"),
            marker=dict(size=7, color=COLOR_RISK_HIGH),
            hovertemplate="Digit %{x}<br>Expected: %{y:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color=COLOR_TEXT),
        ),
    )
    return _apply_theme(
        fig,
        "First-Digit Distribution (Digits 1 to 9)",
        "Leading Digit",
        "Frequency (%)",
    )
