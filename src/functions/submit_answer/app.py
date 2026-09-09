"""POST /session/{sessionId}/answer

Records one answer and returns either the next item in the current stage, or
— once the stage is exhausted — the routing/finalization result:
  Stage 0  < 55%               -> finalize Basic
  Stage 0  55-70% (borderline) -> Stage B (short tie-break)
  Stage 0  >= 70%               -> Stage A (harder confirmation)
  Stage A / Stage B exhausted  -> ALWAYS finalize. No retries, no manual flag.

Stage completion is decided server-side (whether itembank.next_item finds
another item), not by a client-supplied flag — nothing to spoof or get wrong
from the browser.
"""
import json
import time
from common import db, auth, scoring
from common import items as itembank

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def canonical(s: str) -> str:
    return " ".join(s.strip().lower().split())


def finalize(student: str, session_id: str, track: str, domain_scores: dict):
    decided_at = int(time.time())
    result = {
        "PK": f"RESULT#{session_id}",
        "SK": "SUMMARY",
        "student_id": student,
        "composite_score": domain_scores.get("_overall", 0.0),
        "domain_scores": domain_scores,
        "track": track,
        "decided_at": decided_at,
    }
    db.put_item(result)
    db.update_item(
        f"STUDENT#{student}", f"SESSION#{session_id}",
        "SET stage = :s, track = :t, completed_at = :ca",
        {":s": "done", ":t": track, ":ca": decided_at},
    )
    return result


def lambda_handler(event, context):
    session_id = event["pathParameters"]["sessionId"]
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    body = json.loads(event.get("body") or "{}")
    item_id = body.get("itemId")
    submitted = body.get("answer", "")

    session = db.get_item(f"STUDENT#{student}", f"SESSION#{session_id}")
    if not session:
        return response(404, {"error": "session not found"})
    if session.get("stage") == "done":
        return response(409, {"error": "session already finalized"})

    domain = body.get("domain", "unknown")
    question = db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}")
    correct = bool(question) and canonical(submitted) == canonical(str(question.get("answer_key", "")))

    # Hints used is read from server-recorded state (set by get_hint), never
    # from the request -- the client can't just claim it used none.
    term_state = db.get_item(f"STUDENT#{student}", f"TERMSTATE#{item_id}")
    hints_used = (term_state or {}).get("hints_unlocked", 0)
    credit = scoring.credit_for(correct, hints_used)

    answers = session.get("answers", []) + [{
        "itemId": item_id, "domain": domain, "correct": correct,
        "hintsUsed": hints_used, "credit": credit, "stage": session["stage"],
    }]
    session["answers"] = answers
    db.update_item(
        f"STUDENT#{student}", f"SESSION#{session_id}",
        "SET answers = :a", {":a": answers},
    )

    stage_answers = [a for a in answers if a["stage"] == session["stage"]]
    stage_scores = scoring.score_domain_answers(stage_answers)
    stage_pct = stage_scores.get("_overall", 0.0)

    next_item, index, total = itembank.next_item(session)
    if next_item:
        return response(200, {
            "done": False, "stage": session["stage"], "running_score": stage_pct,
            "lastAnswerCorrect": correct, "lastAnswerCredit": credit, "lastAnswerHintsUsed": hints_used,
            "item": itembank.public_item(next_item), "itemIndex": index, "totalItems": total,
        })

    # Current stage exhausted -- route to the next stage, or finalize.
    # Track/scores are never sent back here: placement is instructor-facing
    # information, not shown to the student (see /admin/students/{id}).
    if session["stage"] == "stage0":
        route = scoring.route_after_stage0(stage_pct)
        if route == "basic":
            finalize(student, session_id, scoring.finalize_from_stage0_only(stage_pct), stage_scores)
            return response(200, {"done": True, "lastAnswerCorrect": correct})

        next_stage = "stageA" if route == "stageA" else "stageB"
        db.update_item(
            f"STUDENT#{student}", f"SESSION#{session_id}",
            "SET stage = :s, stage0_score = :sc",
            {":s": next_stage, ":sc": stage_pct},
        )
        session["stage"] = next_stage
        nxt, idx, tot = itembank.next_item(session)
        if nxt:
            return response(200, {
                "done": False, "nextStage": next_stage, "lastAnswerCorrect": correct,
                "item": itembank.public_item(nxt), "itemIndex": idx, "totalItems": tot,
            })
        # No Stage A/B content loaded yet (Phase 0 content work) -- finalize
        # from Stage 0 alone rather than leaving the session stuck with
        # nothing to serve. Remove once Stage A/B items exist.
        track = scoring.ADVANCED if stage_pct >= scoring.STAGE0_HIGH_THRESHOLD else scoring.BASIC
        finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "lastAnswerCorrect": correct})

    if session["stage"] == "stageB":
        track = scoring.finalize_after_stage_b(stage_pct)
        finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "lastAnswerCorrect": correct})

    if session["stage"] == "stageA":
        stage0_pct = float(session.get("stage0_score", 0.0))
        track = scoring.finalize_after_stage_a(stage0_pct, stage_pct)
        finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "lastAnswerCorrect": correct})

    return response(400, {"error": f"unknown stage {session['stage']}"})
