"""POST /session/{sessionId}/answer

Records one answer and returns either the next item in the current stage, or
— once the stage is exhausted — the routing/finalization result:
  Stage 0  < 55%               -> finalize (routing only; see below)
  Stage 0  55-70% (borderline) -> Stage B (short tie-break)
  Stage 0  >= 70%               -> Stage A (harder confirmation)
  Stage A / Stage B exhausted  -> ALWAYS finalize. No retries, no manual flag.

The 55/70 thresholds above only gate ROUTING now -- how many questions a
student sees. The actual Basic/Advanced call is decided by
scoring.gaussian_track: a student's composite score compared against the
distribution of everyone who has already completed placement in this
cohort (rolling, norm-referenced), not a fixed absolute bar. See that
function's docstring for the bootstrap behavior before enough students
have finished.

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


def prior_composite_scores() -> list:
    """Composite scores of every student who has already finalized in
    this cohort -- the population gaussian_track compares against. The
    current student's own RESULT# doesn't exist yet at call time, so
    this naturally excludes them.
    """
    results = db.scan_all(pk_prefix="RESULT#")
    return [r["composite_score"] for r in results if "composite_score" in r]


def finalize(student: str, session_id: str, track: str, domain_scores: dict):
    decided_at = int(time.time())
    result = {
        "PK": f"RESULT#{session_id}",
        "SK": "SUMMARY",
        "student_id": student,
        "checkpoint": "placement",
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


def finalize_module(student: str, session_id: str, checkpoint: str, domain_scores: dict):
    """Module assessments are diagnostic, not a Basic/Advanced branch --
    same RESULT shape minus `track`, tagged with the module's checkpoint
    so admin queries can bucket it separately from placement.
    """
    decided_at = int(time.time())
    result = {
        "PK": f"RESULT#{session_id}",
        "SK": "SUMMARY",
        "student_id": student,
        "checkpoint": checkpoint,
        "composite_score": domain_scores.get("_overall", 0.0),
        "domain_scores": domain_scores,
        "decided_at": decided_at,
    }
    db.put_item(result)
    db.update_item(
        f"STUDENT#{student}", f"SESSION#{session_id}",
        "SET stage = :s, completed_at = :ca",
        {":s": "done", ":ca": decided_at},
    )
    return result


def handle_module_answer(student: str, session_id: str, session: dict, checkpoint: str,
                          correct: bool, credit: float, hints_used: int):
    scores = scoring.score_domain_answers(session["answers"])
    next_item, index, total = itembank.next_module_item(session)
    if next_item:
        return response(200, {
            "done": False, "running_score": scores.get("_overall", 0.0),
            "lastAnswerCorrect": correct, "lastAnswerCredit": credit, "lastAnswerHintsUsed": hints_used,
            "item": itembank.public_item(next_item), "itemIndex": index, "totalItems": total,
        })
    finalize_module(student, session_id, checkpoint, scores)
    return response(200, {"done": True, "lastAnswerCorrect": correct})


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
    correct = False
    if question:
        answer_key = question.get("answer_key", "")
        # A question's answer_key can be one string or a list of
        # acceptable synonyms (e.g. "MFA" / "2FA" / "two-factor
        # authentication") -- free-text concept answers are inherently
        # more ambiguous than a terminal's deterministic output.
        acceptable = answer_key if isinstance(answer_key, list) else [answer_key]
        submitted_canon = canonical(submitted)
        correct = any(submitted_canon == canonical(str(k)) for k in acceptable)

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

    checkpoint = session.get("checkpoint", "placement")
    if checkpoint != "placement":
        return handle_module_answer(student, session_id, session, checkpoint, correct, credit, hints_used)

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
            track = scoring.gaussian_track(stage_pct, prior_composite_scores())
            finalize(student, session_id, track, stage_scores)
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
        track = scoring.gaussian_track(stage_pct, prior_composite_scores())
        finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "lastAnswerCorrect": correct})

    if session["stage"] == "stageB":
        track = scoring.gaussian_track(stage_pct, prior_composite_scores())
        finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "lastAnswerCorrect": correct})

    if session["stage"] == "stageA":
        stage0_pct = float(session.get("stage0_score", 0.0))
        combined = scoring.combine_stage0_and_stage_a(stage0_pct, stage_pct)
        track = scoring.gaussian_track(combined, prior_composite_scores())
        finalize(student, session_id, track, stage_scores)
        return response(200, {"done": True, "lastAnswerCorrect": correct})

    return response(400, {"error": f"unknown stage {session['stage']}"})
