"""Database access repository layer."""

from app.repositories.audit_log_repo import create_audit_log, get_audit_logs
from app.repositories.flagged_repo import (
    bulk_create_flagged_transactions,
    count_open_flagged_by_run,
    get_duplicate_group_members,
    get_flagged_by_id,
    get_flagged_transactions_by_run,
    get_flagged_transactions_filtered,
)
from app.repositories.review_repo import create_review, get_reviews_by_flagged_id
from app.repositories.run_repo import (
    create_analysis_run,
    get_analysis_run_by_id,
    get_runs_by_upload,
    sign_off_run,
    update_analysis_run_status,
)
from app.repositories.transaction_repo import (
    bulk_create_transactions,
    get_all_transactions_for_analysis,
    get_transactions_by_upload,
)
from app.repositories.upload_repo import (
    create_upload,
    delete_upload,
    get_upload_by_id,
    list_uploads,
)
from app.repositories.user_repo import create_user, get_user_by_email, get_user_by_id

__all__ = [
    "bulk_create_flagged_transactions",
    "bulk_create_transactions",
    "count_open_flagged_by_run",
    "create_analysis_run",
    "create_audit_log",
    "create_review",
    "create_upload",
    "create_user",
    "delete_upload",
    "get_all_transactions_for_analysis",
    "get_analysis_run_by_id",
    "get_audit_logs",
    "get_duplicate_group_members",
    "get_flagged_by_id",
    "get_flagged_transactions_by_run",
    "get_flagged_transactions_filtered",
    "get_reviews_by_flagged_id",
    "get_runs_by_upload",
    "get_transactions_by_upload",
    "get_upload_by_id",
    "get_user_by_email",
    "get_user_by_id",
    "list_uploads",
    "sign_off_run",
    "update_analysis_run_status",
]
