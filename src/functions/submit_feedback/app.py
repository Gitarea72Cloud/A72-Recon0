"""POST /session/{sessionId}/feedback

Lets a student flag a problem with a specific question, or just leave a
comment on it -- separate from their answer, doesn't affect scoring.
Stored under its own FEEDBACK#<domain>_<itemId> namespace (not nested
under the student, since instructors browse this by question, not by
student) so an instructor can review what's been flagged per item.
"""
import json
import time
import uuid
from common import db, auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    session_id = event["pathParameters"]["sessionId"]
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    body = json.loads(event.get("body") or "{}")
    item_id = body.get("itemId")
    domain = body.get("domain")
    comment = (body.get("comment") or "").strip()
    flagged = bool(body.get("flagged"))
    if not item_id or not domain or not comment:
        return response(400, {"error": "itemId, domain and comment are required"})

    session = db.get_item(f"STUDENT#{student}", f"SESSION#{session_id}")
    if not session:
        return response(404, {"error": "session not found"})

    now = int(time.time())
    feedback = {
        "PK": f"FEEDBACK#{domain}_{item_id}",
        "SK": f"{now}#{uuid.uuid4().hex[:8]}",
        "studentId": student,
        "sessionId": session_id,
        "domain": domain,
        "itemId": item_id,
        "comment": comment[:2000],
        "flagged": flagged,
        "submittedAt": now,
    }
    db.put_item(feedback)
    return response(201, {"ok": True})
