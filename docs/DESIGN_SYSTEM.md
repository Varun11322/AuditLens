# Design System (Streamlit UI)

## 1. Design Direction
Style: Clean, professional, data-focused (think audit/consulting dashboard).
Mood: Calm, trustworthy, uncluttered.
Design Principles:
- Data first: tables and charts get the space; decoration is minimal.
- Risk is communicated by label and color together, never color alone.
- Every screen explains what to do next.

## 2. Brand
Brand Name: AuditLens
Logo: Text wordmark only ("AuditLens"), no image needed.
Brand Voice: Plain, precise, neutral. Flags are "for review", never accusations of fraud.

## 3. Color Palette
Configure in `.streamlit/config.toml` (theme) and a small constants module for charts.
Primary: #1F6F5C
Secondary: #2F4858
Background: #FFFFFF
Surface: #F5F7F8
Text: #1B2A33
Muted Text: #5F6C74
Border: #DDE3E6
Success: #2E8B57
Warning: #D9902F
Error: #C0392B
Risk colors: High #C0392B, Medium #D9902F, Low #E5C100 (always paired with a text label)

## 4. Typography
Font Family: Streamlit default sans-serif (or Inter via theme config)
Headings: use Streamlit title/header/subheader consistently (one title per page)
Body: default size; use `st.caption` for secondary text
Numbers: use `st.metric` for key figures

## 5. Spacing
Use Streamlit columns and containers; keep a consistent rhythm: metrics row on top, charts in two columns, table below.

## 6. Border Radius / Shadows
Use Streamlit defaults; use `st.container(border=True)` for grouped sections. No custom shadows.

## 7. Buttons
Primary: one per screen for the main action (Upload, Run Analysis, Export).
Secondary: all other actions.
Danger: Delete upload requires a confirmation step.
Disabled: while a run is in progress.
Loading: show `st.spinner` or a status/progress element during uploads and runs.

## 8. Inputs
Default: labels always visible; help text for thresholds.
Error: use `st.error` with a specific, actionable message.
Thresholds: number inputs with defaults from AUDIT_RULES.md, inside an "Advanced settings" expander.

## 9. Tables
- Use `st.dataframe` with server-side pagination (page controls) - never load the whole population.
- Risk level column shows a text badge (High / Medium / Low).
- Default sort: risk_score descending.
- Amounts formatted with thousands separators and the currency symbol.

## 10. Charts (Plotly)
- Risk level distribution (bar), flagged count by rule (bar), flagged over time (line), top vendors by flagged amount (bar).
- Benford: grouped bars or bar + line, observed vs expected for digits 1-9.
- Titles and axis labels on every chart; use the palette above; colorblind-friendly (also differentiate by label/pattern).

## 11. Navigation
Streamlit multipage app, sidebar navigation: Upload, Dashboard, Review, Benford, Reports, (Evaluation). Show the logged-in user and role and a Logout button in the sidebar. Hide manager-only controls from auditors.

## 12. States
Loading: spinner with a short message.
Empty: friendly message and the next step (e.g. "No uploads yet - upload a file").
Error: clear message, retry option, no stack traces.
Success: `st.success` toast-style confirmation.
Disabled: greyed controls with a reason shown.

## 13. Accessibility
- Do not rely on color alone (risk labels in text).
- Sufficient contrast per the palette.
- Clear labels on all inputs.
- Keep layouts usable on a laptop screen; mobile is not a priority.
