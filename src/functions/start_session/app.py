"""POST /session/start

Creates a Stage 0 session for the calling student and returns the first item
(plus its position in the stage, so the client can show "1 of 5" etc without
knowing the item bank size itself).
"""
import json
import time
import uuid
from common import db, auth
from common import items as itembank

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    # Placement is one-shot per student: if a prior session already
    # finalized, point back at it instead of allowing a fresh retake.
    existing = db.query_prefix(f"STUDENT#{student}", "SESSION#")
    done = next((s for s in existing if s.get("checkpoint") == "placement" and s.get("stage") == "done"), None)
    if done:
        return response(409, {
            "error": "placement already completed",
            "sessionId": done["SK"].replace("SESSION#", ""),
            "track": done.get("track"),
        })

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

    item, index, total = itembank.next_item(session)
    if not item:
        return response(200, {
            "sessionId": session_id,
            "item": None,
            "note": "No items loaded yet — seed the question bank (QUESTION#<domain> / ITEM#<qid>) first.",
        })

    return response(200, {
        "sessionId": session_id, "item": itembank.public_item(item),
        "itemIndex": index, "totalItems": total,
    })
