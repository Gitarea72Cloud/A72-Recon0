"""In-app + best-effort email notifications for students.

Kept intentionally simple: one DynamoDB item per notification
(PK=STUDENT#<id>, SK=NOTIFICATION#<epoch>#<uuid8>) so the existing
db.query_prefix pattern (same as TERMSTATE#/SESSION# lookups) works
unchanged, plus a best-effort SES email. Email failures never raise and
never block the in-app notification or the caller's main action (e.g.
unlocking a module) -- see fan_out_module_unlock.
"""
import os
import time
import uuid
import boto3
from . import db

_SES_REGION = os.environ.get("NOTIFICATION_SES_REGION", "eu-west-1")
_FROM_EMAIL = os.environ.get("NOTIFICATION_FROM_EMAIL", "")
_ses = boto3.client("ses", region_name=_SES_REGION) if _FROM_EMAIL else None


def write_notification(student_id: str, title: str, body: str, module_id: str | None = None):
    item = {
        "PK": f"STUDENT#{student_id}",
        "SK": f"NOTIFICATION#{int(time.time())}#{uuid.uuid4().hex[:8]}",
        "title": title,
        "body": body,
        "moduleId": module_id,
        "isRead": False,
        "createdAt": int(time.time()),
    }
    db.put_item(item)


def send_email(to_email: str, subject: str, body_text: str) -> bool:
    if not _ses or not _FROM_EMAIL or not to_email:
        return False
    try:
        _ses.send_email(
            Source=_FROM_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body_text}}},
        )
        return True
    except Exception:
        return False


def fan_out_module_unlock(module_id: str, module_title: str, users: dict, instructor_subs: set) -> int:
    """users: sub -> {email, username} for every Cognito user (from
    admin._all_cognito_users). Notifies everyone except instructors --
    best-effort per recipient, one bad address never blocks the rest.
    Returns how many emails actually sent (the in-app notification is
    written for every recipient regardless of email outcome).
    """
    title = f"{module_title} is now open"
    body = (
        f"Your instructor has unlocked the assessment for {module_title}. "
        f"Sign in to A72-Recon0 and head to Modules to take it."
    )
    emailed = 0
    for sub, info in users.items():
        if sub in instructor_subs:
            continue
        write_notification(sub, title, body, module_id)
        if send_email(info.get("email"), title, body):
            emailed += 1
    return emailed
