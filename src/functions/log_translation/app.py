"""POST /session/{sessionId}/translate

Logs that a student clicked "Translate to Spanish" on a question --
the button itself never actually translates anything (see frontend/
test.html): it shows a blocking nudge encouraging the student to work
through it in English instead, and fires this request in the
background so instructors can see who's hitting a language barrier.

Stored under the student (PK=STUDENT#<id>), unlike question feedback
(keyed by item) -- this is read by student profile and by the cohort-
wide "who needs language support" view, both student-centric, not
item-centric.
"""
import json
import time
import uuid
from common import db, auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    body = json.loads(event.get("body") or "{}")
    item_id = body.get("itemId")
    domain = body.get("domain")
    if not item_id or not domain:
        return response(400, {"error": "itemId and domain are required"})

    now = int(time.time())
    record = {
        "PK": f"STUDENT#{student}",
        "SK": f"TRANSLATION#{now}#{uuid.uuid4().hex[:8]}",
        "domain": domain,
        "itemId": item_id,
        "requestedAt": now,
    }
    db.put_item(record)
    return response(201, {"ok": True})
