"""POST /session/{sessionId}/answer

Records one answer, scores the current stage when it's complete, and applies
the branching rule from common.scoring:
  Stage 0  < 55%            -> finalize Basic
  Stage 0  55-70% (borderline) -> Stage B (short tie-break)
  Stage 0  >= 70%            -> Stage A (harder confirmation)
  Stage A / Stage B completed -> ALWAYS finalize. No retries, no manual flag.
"""
import json
import time
from common import db, auth, scoring

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def canonical(s: str) -> str:
    return " ".join(s.strip().lower().split())


def finalize(student: str, session_id: str, track: str, domain_scores: dict):
    result = {
        "PK": f"RESULT#{session_id}",
        "SK": "SUMMARY",
        "student_id": student,
        "composite_score": domain_scores.get("_overall", 0.0),
        "domain_scores": domain_scores,
        "track": track,
        "decided_at": int(time.time()),
    }
    db.put_item(result)
    db.update_item(
        f"STUDENT#{student}", f"SESSION#{session_id}",
        "SET stage = :s, track = :t",
        {":s": "done", ":t": track},
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
        return response(409, {"error": "session already finalized", "track": session.get("track")})

    domain = body.get("domain", "unknown")
    question = db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}")
    correct = bool(question) and canonical(submitted) == canonical(str(question.get("answer_key", "")))

    answers = session.get("answers", []) + [{
        "itemId": item_id, "domain": domain, "correct": correct, "stage": session["stage"],
    }]
    db.update_item(
        f"STUDENT#{student}", f"SESSION#{session_id}",
        "SET answers = :a", {":a": answers},
    )

    # NOTE: "stage complete" detection (has this student seen every item for
    # the current stage yet?) depends on the item bank size, which is Phase 0
    # content work. This returns the running score after every answer so the
    # caller (or a thin orchestration layer) can decide when a stage is done
    # and call the relevant branch below.
    stage_answers = [a for a in answers if a["stage"] == session["stage"]]
    stage_scores = scoring.score_domain_answers(stage_answers)
    stage_pct = stage_scores.get("_overall", 0.0)

    stage_complete = bool(body.get("stageComplete"))
    if not stage_complete:
        return response(200, {"stage": session["stage"], "running_score": stage_pct, "done": False})

    if session["stage"] == "stage0":
        route = scoring.route_after_stage0(stage_pct)
        if route == "basic":
            result = finalize(student, session_id, scoring.finalize_from_stage0_only(stage_pct), stage_scores)
            return response(200, {"done": True, "track": result["track"]})
        next_stage = "stageA" if route == "stageA" else "stageB"
        db.update_item(
            f"STUDENT#{student}", f"SESSION#{session_id}",
            "SET stage = :s, stage0_score = :sc",
            {":s": next_stage, ":sc": stage_pct},
        )
        return response(200, {"done": False, "nextStage": next_stage})

    if session["stage"] == "stageB":
        track = scoring.finalize_after_stage_b(stage_pct)
        result = finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "track": result["track"]})

    if session["stage"] == "stageA":
        stage0_pct = float(session.get("stage0_score", 0.0))
        track = scoring.finalize_after_stage_a(stage0_pct, stage_pct)
        result = finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "track": result["track"]})

    return response(400, {"error": f"unknown stage {session['stage']}"})
