"""Unit tests for audit rules R1 through R6 and fallback behaviors."""

from __future__ import annotations

import pandas as pd
import pytest

from app.analytics.rules import evaluate_rules
from app.analytics.settings import Settings


@pytest.fixture
def base_df() -> pd.DataFrame:
    """Minimal base valid DataFrame for rule testing."""
    return pd.DataFrame(
        {
            "transaction_id": ["TXN-001"],
            "posting_date": [pd.Timestamp("2025-05-14 11:30:00")],  # Wednesday 11:30
            "amount": [5432.10],
            "vendor_id": ["VEND-001"],
            "department": ["Finance"],
            "account_code": ["600100"],
            "created_by": ["alice"],
            "approved_by": ["bob"],
            "description": ["Standard consulting payment"],
        }
    )


def test_r1_self_approval(base_df: pd.DataFrame) -> None:
    """Test R1 self-approval: case-insensitive, trimmed, both non-empty."""
    settings = Settings()
    df = pd.concat([base_df] * 5, ignore_index=True)
    df["transaction_id"] = [f"TXN-{i:03d}" for i in range(5)]
    df["created_by"] = ["alice", " Alice ", "ALICE", "", "alice"]
    df["approved_by"] = ["alice", "alice ", "alice", "", "bob"]

    results, _ = evaluate_rules(df, settings)
    codes = results["triggered_rule_codes"]

    # Rows 0, 1, 2 should trigger R1 (+40 pts)
    assert "R1" in codes[0]
    assert "R1" in codes[1]
    assert "R1" in codes[2]
    # Row 3 (both empty) and Row 4 (different users) should not trigger R1
    assert "R1" not in codes[3]
    assert "R1" not in codes[4]
    assert results.loc[0, "rule_points"] >= 40


def test_r1_fallback_missing_column(base_df: pd.DataFrame) -> None:
    """Test R1 is skipped and recorded when created_by or approved_by is missing."""
    settings = Settings()
    results, summary = evaluate_rules(base_df, settings, missing_optional_columns=["created_by"])
    assert "R1" in summary["skipped_rules"]
    assert "R1" not in results.loc[0, "triggered_rule_codes"]


def test_r2_duplicate_payment(base_df: pd.DataFrame) -> None:
    """Test R2 duplicate payment window: 7 days edge vs 8 days."""
    settings = Settings(duplicate_window_days=7)
    df = pd.DataFrame(
        {
            "transaction_id": ["TXN-1", "TXN-2", "TXN-3", "TXN-4"],
            "posting_date": [
                pd.Timestamp("2025-05-01 10:00:00"),
                pd.Timestamp("2025-05-08 10:00:00"),  # exactly 7 days after TXN-1
                pd.Timestamp("2025-05-16 10:00:00"),  # 8 days after TXN-2 -> separate
                pd.Timestamp("2025-05-01 10:00:00"),  # same date as TXN-1, but different vendor
            ],
            "amount": [2500.0, 2500.0, 2500.0, 2500.0],
            "vendor_id": ["VEND-A", "VEND-A", "VEND-A", "VEND-B"],
            "created_by": ["user1"] * 4,
            "approved_by": ["user2"] * 4,
            "department": ["IT"] * 4,
            "account_code": ["600200"] * 4,
            "description": ["Invoice"] * 4,
        }
    )

    results, _ = evaluate_rules(df, settings)
    codes = results["triggered_rule_codes"]
    group_ids = results["duplicate_group_id"]

    # TXN-1 and TXN-2 are duplicates (7 days apart, same vendor and amount)
    assert "R2" in codes[0]
    assert "R2" in codes[1]
    assert group_ids[0] != ""
    assert group_ids[0] == group_ids[1]

    # TXN-3 is 8 days apart from TXN-2 -> not duplicate
    assert "R2" not in codes[2]
    assert group_ids[2] == ""

    # TXN-4 has different vendor -> not duplicate
    assert "R2" not in codes[3]
    assert group_ids[3] == ""


def test_r3_missing_approver(base_df: pd.DataFrame) -> None:
    """Test R3 missing approver on amounts >= 10,000."""
    settings = Settings(missing_approver_min_amount=10000.0)
    df = pd.concat([base_df] * 4, ignore_index=True)
    df["transaction_id"] = [f"TXN-{i:03d}" for i in range(4)]
    df["amount"] = [9999.0, 10000.0, 50000.0, 50000.0]
    df["approved_by"] = ["", "", "   ", "mgr1"]

    results, _ = evaluate_rules(df, settings)
    codes = results["triggered_rule_codes"]

    # Row 0: amount < 10000 -> no flag even if approved_by is blank
    assert "R3" not in codes[0]
    # Row 1: amount == 10000 and blank -> flag R3 (+30)
    assert "R3" in codes[1]
    # Row 2: amount > 10000 and whitespace -> flag R3 (+30)
    assert "R3" in codes[2]
    # Row 3: amount > 10000 but approved -> no flag
    assert "R3" not in codes[3]


def test_r3_fallback_missing_column(base_df: pd.DataFrame) -> None:
    """Test R3 is skipped and recorded when approved_by is missing."""
    settings = Settings()
    results, summary = evaluate_rules(base_df, settings, missing_optional_columns=["approved_by"])
    assert "R3" in summary["skipped_rules"]
    assert "R3" not in results.loc[0, "triggered_rule_codes"]


def test_r4_just_below_limit(base_df: pd.DataFrame) -> None:
    """Test R4: exactly at 90% (flag), just under 100% (flag), exactly at limit (no flag)."""
    settings = Settings(approval_limit=100000.0, just_below_band=0.90)
    df = pd.concat([base_df] * 5, ignore_index=True)
    df["transaction_id"] = [f"TXN-{i:03d}" for i in range(5)]
    df["amount"] = [
        89999.99,  # Below 90% -> no flag
        90000.00,  # Exactly 90% of limit -> flag
        99999.99,  # Just under 100k -> flag
        100000.00,  # Exactly at limit -> no flag
        100001.00,  # Above limit -> no flag
    ]

    results, _ = evaluate_rules(df, settings)
    codes = results["triggered_rule_codes"]

    assert "R4" not in codes[0]
    assert "R4" in codes[1]
    assert "R4" in codes[2]
    assert "R4" not in codes[3]
    assert "R4" not in codes[4]


def test_r5_round_amount(base_df: pd.DataFrame) -> None:
    """Test R5: 9999 (no), 10000 (yes), 10500 (no), 20000 (yes)."""
    settings = Settings(round_min_amount=10000.0, round_multiple=1000.0)
    df = pd.concat([base_df] * 4, ignore_index=True)
    df["transaction_id"] = [f"TXN-{i:03d}" for i in range(4)]
    df["amount"] = [9999.0, 10000.0, 10500.0, 20000.0]

    results, _ = evaluate_rules(df, settings)
    codes = results["triggered_rule_codes"]

    assert "R5" not in codes[0]  # < 10000
    assert "R5" in codes[1]  # == 10000 multiple of 1000
    assert "R5" not in codes[2]  # not multiple of 1000
    assert "R5" in codes[3]  # == 20000 multiple of 1000


def test_r6_weekend_after_hours(base_df: pd.DataFrame) -> None:
    """Test R6: Saturday, Sunday, 07:59, 08:00, 20:00, date-only input."""
    settings = Settings(business_hours_start=8, business_hours_end=20)
    df = pd.concat([base_df] * 6, ignore_index=True)
    df["transaction_id"] = [f"TXN-{i:03d}" for i in range(6)]
    df["posting_date"] = [
        pd.Timestamp("2025-05-17 12:00:00"),  # Saturday -> flag
        pd.Timestamp("2025-05-18 12:00:00"),  # Sunday -> flag
        pd.Timestamp("2025-05-14 07:59:59"),  # Wednesday 07:59:59 (before 8 AM) -> flag
        pd.Timestamp("2025-05-14 08:00:00"),  # Wednesday 08:00:00 (start of business) -> no flag
        pd.Timestamp("2025-05-14 19:59:59"),  # Wednesday 19:59:59 (in business hours) -> no flag
        pd.Timestamp("2025-05-14 20:00:00"),  # Wednesday 20:00:00 (end of business) -> flag
    ]

    results, _ = evaluate_rules(df, settings, has_time_part=True)
    codes = results["triggered_rule_codes"]

    assert "R6" in codes[0]
    assert "R6" in codes[1]
    assert "R6" in codes[2]
    assert "R6" not in codes[3]
    assert "R6" not in codes[4]
    assert "R6" in codes[5]


def test_r6_date_only_skips_hour_check(base_df: pd.DataFrame) -> None:
    """Test R6 skips hour check when date-only, but weekend check still triggers."""
    settings = Settings()
    df = pd.concat([base_df] * 2, ignore_index=True)
    df["transaction_id"] = ["TXN-1", "TXN-2"]
    df["posting_date"] = [
        pd.Timestamp("2025-05-14 00:00:00"),  # Wednesday (no time) -> no flag
        pd.Timestamp("2025-05-18 00:00:00"),  # Sunday (no time) -> flag (weekend)
    ]

    results, summary = evaluate_rules(df, settings, has_time_part=False)
    codes = results["triggered_rule_codes"]

    assert "R6_hour_check" in summary["skipped_rules"]
    assert "R6" not in codes[0]
    assert "R6" in codes[1]


def test_rule_points_cap_at_100(base_df: pd.DataFrame) -> None:
    """Test rule points add up and are capped at 100."""
    settings = Settings(approval_limit=100000.0, just_below_band=0.90)
    # Craft a transaction that triggers R1 (40), R3 (30), R4 (25), R5 (10), R6 (10) -> sum 115
    df = base_df.copy()
    df["created_by"] = "alice"
    df["approved_by"] = "alice"  # R1 (+40)
    df["amount"] = 95000.0  # R4 (+25), R5 (+10: 95000 is multiple of 1000)
    df["posting_date"] = pd.Timestamp("2025-05-18 03:00:00")  # R6 (+10)

    results, _ = evaluate_rules(df, settings)
    # Sum: 40 + 25 + 10 + 10 = 85.
    # Now let's trigger R1 (40) + R4 (25) + R5 (10) + R6 (10) + R2 (30) = 115
    df2 = pd.concat([df, df], ignore_index=True)
    df2["transaction_id"] = ["TXN-A", "TXN-B"]
    results2, _ = evaluate_rules(df2, settings)

    assert results2.loc[0, "rule_points"] == 100  # Capped at 100
