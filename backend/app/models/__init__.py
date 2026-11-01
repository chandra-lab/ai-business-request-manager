"""ORM models package — import all models for Alembic metadata discovery."""

from app.models.assignment import Assignment
from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.hr_case_access import HRCaseAccess
from app.models.hr_case_note import HRCaseNote
from app.models.notification import Notification
from app.models.outbox_message import OutboxMessage
from app.models.request import Request
from app.models.request_comment import RequestComment
from app.models.request_history import RequestHistory
from app.models.request_review_queue import RequestReviewQueue
from app.models.role import Role, UserRole
from app.models.ai_analysis import AIAnalysis
from app.models.user import User

__all__ = [
    "User",
    "Department",
    "Role",
    "UserRole",
    "Request",
    "AIAnalysis",
    "Assignment",
    "RequestHistory",
    "RequestComment",
    "Attachment",
    "AuditLog",
    "HRCaseAccess",
    "HRCaseNote",
    "RequestReviewQueue",
    "OutboxMessage",
    "Notification",
]
