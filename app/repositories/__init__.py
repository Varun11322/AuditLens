"""Database access repository layer."""

from app.repositories.audit_log_repo import create_audit_log, get_audit_logs
from app.repositories.flagged_repo import (
    bulk_create_flagged_transactions,
    get_flagged_transactions_by_run,
)
from app.repositories.review_repo import create_review, get_reviews_by_flagged_id
from app.repositories.run_repo import (
    create_analysis_run,
    get_analysis_run_by_id,
    update_analysis_run_status,
)
from app.repositories.transaction_repo import (
    bulk_create_transactions,
    get_transactions_by_upload,
)
from app.repositories.upload_repo import create_upload, delete_upload, get_upload_by_id
from app.repositories.user_repo import create_user, get_user_by_email, get_user_by_id

__all__ = [
    "bulk_create_flagged_transactions",
    "bulk_create_transactions",
    "create_analysis_run",
    "create_audit_log",
    "create_review",
    "create_upload",
    "create_user",
    "delete_upload",
    "get_analysis_run_by_id",
    "get_audit_logs",
    "get_flagged_transactions_by_run",
    "get_reviews_by_flagged_id",
    "get_transactions_by_upload",
    "get_upload_by_id",
    "get_user_by_email",
    "get_user_by_id",
    "update_analysis_run_status",
]
