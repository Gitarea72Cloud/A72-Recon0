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


def start_module_session(student: str, module_id: str):
    module = db.get_item("MODULE_META", module_id)
    if not module:
        return response(404, {"error": "unknown module"})
    if not module.get("unlocked"):
        return response(403, {"error": "this module isn't unlocked yet"})

    # Same one-shot/resume shape as placement below, scoped to this module.
    existing = db.query_prefix(f"STUDENT#{student}", "SESSION#")
    module_sessions = [s for s in existing if s.get("checkpoint") == module_id]
    done = next((s for s in module_sessions if s.get("stage") == "done"), None)
    if done:
        return response(409, {
            "error": "module already completed",
            "sessionId": done["SK"].replace("SESSION#", ""),
        })

    in_progress = next(iter(module_sessions), None)
    if in_progress:
        item, index, total = itembank.next_module_item(in_progress)
        session_id = in_progress["SK"].replace("SESSION#", "")
        if item:
            return response(200, {
                "sessionId": session_id, "item": itembank.public_item(item),
                "itemIndex": index, "totalItems": total,
                "moduleId": module_id, "moduleTitle": module.get("title"),
            })

    session_id = str(uuid.uuid4())
    session = {
        "PK": f"STUDENT#{student}",
        "SK": f"SESSION#{session_id}",
        "checkpoint": module_id,
        "stage": "active",
        "started_at": int(time.time()),
        "answers": [],
    }
    db.put_item(session)

    item, index, total = itembank.next_module_item(session)
    if not item:
        return response(200, {
            "sessionId": session_id, "item": None,
            "note": "No questions loaded for this module yet.",
        })

    return response(200, {
        "sessionId": session_id, "item": itembank.public_item(item),
        "itemIndex": index, "totalItems": total,
        "moduleId": module_id, "moduleTitle": module.get("title"),
    })


def start_placement_session(student: str):
    # Placement is one-shot per student: if a prior session already
    # finalized, point back at it instead of allowing a fresh retake.
    existing = db.query_prefix(f"STUDENT#{student}", "SESSION#")
    placement_sessions = [s for s in existing if s.get("checkpoint") == "placement"]
    done = next((s for s in placement_sessions if s.get("stage") == "done"), None)
    if done:
        return response(409, {
            "error": "placement already completed",
            "sessionId": done["SK"].replace("SESSION#", ""),
        })

    # A refresh or re-navigation to the test page shouldn't restart from
    # question 1 -- resume whatever's already in progress instead of
    # abandoning it for a brand new session (that's what was showing
    # students the same early questions repeatedly).
    in_progress = next(iter(placement_sessions), None)
    if in_progress:
        item, index, total = itembank.next_item(in_progress)
        session_id = in_progress["SK"].replace("SESSION#", "")
        if item:
            return response(200, {
                "sessionId": session_id, "item": itembank.public_item(item),
                "itemIndex": index, "totalItems": total,
            })
        # Stage exhausted but never finalized (e.g. the process was
        # interrupted right at that boundary) -- nothing sensible to
        # resume into; fall through and start a fresh session.

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


def lambda_handler(event, context):
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    body = json.loads(event.get("body") or "{}")
    module_id = body.get("moduleId")
    if module_id:
        return start_module_session(student, module_id)
    return start_placement_session(student)
