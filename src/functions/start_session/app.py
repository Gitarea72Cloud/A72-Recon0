"""POST /session/start

Creates a Stage 0 session for the calling student and returns the first item.
Item selection here is intentionally simple (first item per domain, in a
fixed order) — the real item bank / randomized variant pool is Phase 0
content work, not infrastructure; swap this out once that exists.
"""
import json
import time
import uuid
from common import db, auth, scoring

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    session_id = str(uuid.uuid4())
    session = {
        "PK": f"STUDENT#{student}",
        "SK": f"SESSION#{session_id}",
        "checkpoint": "placement",
        "stage": "stage0",
        "started_at": int(time.time()),
        "answers": [],
    }
    db.put_item(session)

    first_items = []
    for domain in scoring.DOMAINS:
        if domain == "tooling_familiarity":
            continue  # Stage A only
        items = db.query_prefix(f"QUESTION#{domain}", "ITEM#")
        if items:
            first_items.append(items[0])

    if not first_items:
        return response(200, {
            "sessionId": session_id,
            "item": None,
            "note": "No items loaded yet — seed the question bank (QUESTION#<domain> / ITEM#<qid>) first.",
        })

    return response(200, {"sessionId": session_id, "item": first_items[0]})
