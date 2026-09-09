"""POST /session/{sessionId}/hint

Reveals one hint for the student's current item, on demand. Hints are
never sent to the client up front (only hintCount, from items.public_item)
-- this is the only way their text ever leaves the server, and the level
requested is recorded so submit_answer can apply the hint penalty when the
answer for this item is graded, regardless of what the client claims.

Levels must be unlocked in order (can't skip to level 3) -- enforced here,
not just in the UI, since this determines the score.
"""
import json
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
    level = body.get("level")
    if not item_id or not domain or level not in (1, 2, 3):
        return response(400, {"error": "itemId, domain and level (1-3) are required"})

    session = db.get_item(f"STUDENT#{student}", f"SESSION#{session_id}")
    if not session:
        return response(404, {"error": "session not found"})
    if session.get("stage") == "done":
        return response(409, {"error": "session already finalized"})

    question = db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}")
    hints = (question or {}).get("hints", [])
    if level > len(hints):
        return response(404, {"error": "no hint at that level for this item"})

    term_key = f"TERMSTATE#{item_id}"
    state = db.get_item(f"STUDENT#{student}", term_key) or {
        "PK": f"STUDENT#{student}", "SK": term_key,
        "files": (question or {}).get("scenario", {}).get("files", {}),
        "transcript": [],
        "hints_unlocked": 0,
    }
    unlocked = state.get("hints_unlocked", 0)
    if level > unlocked + 1:
        return response(400, {"error": f"unlock hint {unlocked + 1} first", "hintsUnlocked": unlocked})

    state["hints_unlocked"] = max(unlocked, level)
    db.put_item(state)

    return response(200, {"hint": hints[level - 1], "hintsUnlocked": state["hints_unlocked"]})
