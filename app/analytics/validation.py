"""Input validation and cleaning for financial transaction ledgers."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: list[str] = [
    "transaction_id",
    "posting_date",
    "amount",
    "vendor_id",
]

OPTIONAL_COLUMNS: list[str] = [
    "department",
    "account_code",
    "created_by",
    "approved_by",
    "description",
]

CANONICAL_COLUMNS: list[str] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def validate_and_clean_ledger(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate and clean an input DataFrame against the canonical schema.

    Enforces canonical input schema from AUDIT_RULES.md section 1.
    Rejects rows with non-positive or invalid amounts, invalid posting dates,
    or duplicate transaction_ids. Identifies missing optional columns.

    Args:
        df: Raw input DataFrame.

    Returns:
        Tuple of (clean_df, validation_summary).

    Raises:
        ValueError: If any required canonical column is completely missing.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("Input data must be a pandas DataFrame.")

    total_rows = len(df)
    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        raise ValueError(
            f"Input DataFrame is missing required canonical columns: {missing_required}"
        )

    # Identify missing optional columns
    missing_optional = [col for col in OPTIONAL_COLUMNS if col not in df.columns]

    # Work on a copy to prevent mutating the input DataFrame
    work_df = df.copy()

    # 1. Parse amount as numeric float
    numeric_amount = pd.to_numeric(work_df["amount"], errors="coerce")
    valid_amount_mask = numeric_amount.notna() & (numeric_amount > 0)

    # 2. Parse posting_date as datetime
    parsed_date = pd.to_datetime(work_df["posting_date"], errors="coerce")
    valid_date_mask = parsed_date.notna()

    # 3. Transaction ID validation (non-empty string and unique)
    clean_txn_id = work_df["transaction_id"].astype(str).str.strip()
    valid_id_mask = (
        work_df["transaction_id"].notna() & (clean_txn_id != "") & (clean_txn_id != "nan")
    )
    # Mark duplicate transaction IDs as rejected
    duplicate_id_mask = clean_txn_id.duplicated(keep=False) & valid_id_mask

    # Row validity mask
    is_valid_row = valid_amount_mask & valid_date_mask & valid_id_mask & (~duplicate_id_mask)

    # Count rejection causes
    invalid_amount_count = int((~valid_amount_mask).sum())
    invalid_date_count = int((~valid_date_mask).sum())
    missing_id_count = int((~valid_id_mask).sum())
    duplicate_id_count = int(duplicate_id_mask.sum())
    rejected_rows_count = int((~is_valid_row).sum())

    # Build clean DataFrame
    clean_df = work_df.loc[is_valid_row].copy()
    clean_df["transaction_id"] = clean_txn_id.loc[is_valid_row]
    clean_df["amount"] = numeric_amount.loc[is_valid_row].astype(float)
    clean_df["posting_date"] = parsed_date.loc[is_valid_row]
    clean_df["vendor_id"] = clean_df["vendor_id"].astype(str).str.strip()

    # Normalize optional columns if present, otherwise set to default empty string
    for opt_col in OPTIONAL_COLUMNS:
        if opt_col in clean_df.columns:
            clean_df[opt_col] = clean_df[opt_col].fillna("").astype(str).str.strip()
        else:
            clean_df[opt_col] = ""

    clean_df = clean_df.reset_index(drop=True)

    # Check whether posting_date contains time components or is date-only
    has_time_part = False
    if len(clean_df) > 0:
        time_seconds = (
            clean_df["posting_date"].dt.hour * 3600
            + clean_df["posting_date"].dt.minute * 60
            + clean_df["posting_date"].dt.second
        )
        has_time_part = bool((time_seconds > 0).any())

    summary: dict[str, Any] = {
        "total_rows": total_rows,
        "valid_rows": len(clean_df),
        "rejected_rows": rejected_rows_count,
        "rejection_counts": {
            "invalid_amount": invalid_amount_count,
            "invalid_date": invalid_date_count,
            "missing_transaction_id": missing_id_count,
            "duplicate_transaction_id": duplicate_id_count,
        },
        "missing_optional_columns": missing_optional,
        "has_time_part": has_time_part,
    }

    logger.info(
        "Validation completed: %d valid rows, %d rejected rows out of %d total",
        len(clean_df),
        rejected_rows_count,
        total_rows,
    )
    return clean_df, summary
