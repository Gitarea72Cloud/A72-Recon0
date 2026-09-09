"""POST /session/{sessionId}/survey

The end-of-test exit survey: a mix of predefined ratings and a free-text
field. One response per session -- resubmitting just overwrites it.
"""
import json
import time
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
    ratings = body.get("ratings") or {}
    free_text = (body.get("freeText") or "").strip()[:2000]
    if not isinstance(ratings, dict):
        return response(400, {"error": "ratings must be an object"})

    session = db.get_item(f"STUDENT#{student}", f"SESSION#{session_id}")
    if not session:
        return response(404, {"error": "session not found"})

    db.put_item({
        "PK": f"SURVEY#{session_id}",
        "SK": "RESPONSE",
        "studentId": student,
        "ratings": ratings,
        "freeText": free_text,
        "submittedAt": int(time.time()),
    })
    return response(201, {"ok": True})
