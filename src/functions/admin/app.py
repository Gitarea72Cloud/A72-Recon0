"""Admin/instructor dashboard API.

Every route here is gated by the `instructors` Cognito group
(auth.is_instructor) -- this is the only place that check matters, since
every route in this file reads or mutates data across ALL students, not
just the caller's own.

Routes (all through this one function, branched on event["routeKey"],
matching the one-function-many-routes pattern already used since the
original /admin/questions + /admin/results pair):
  GET    /admin/results                     cohort-wide dashboard metrics
  GET    /admin/students                    one row per student who has
                                              started or finished placement
  GET    /admin/students/{studentId}        full profile for one student
  POST   /admin/students/{studentId}/reset  delete a student's session for
                                              one checkpoint (body:
                                              {checkpoint}, default
                                              "placement") so they can retake it
  GET    /admin/feedback                    question feedback + exit survey
                                              responses submitted by students
  GET    /admin/modules                     the 11 module assessments +
                                              per-module stats (unlocked,
                                              started, completed, avgScore)
  PUT    /admin/modules/{moduleId}          edit a module (unlocked, title)
                                              -- unlocking fans out an
                                              in-app + best-effort email
                                              notification to every student
  GET    /admin/questions                   full question bank (answer_key
                                              and hints included -- this is
                                              the one place that's true)
  POST   /admin/questions                   create a question
  GET    /admin/questions/{domain}/{itemId} one question, full detail
  PUT    /admin/questions/{domain}/{itemId} update a question
  DELETE /admin/questions/{domain}/{itemId} delete a question
  POST   /admin/questions/generate          AI-assisted draft (Bedrock,
                                              Claude Haiku 4.5) -- returns a
                                              draft, never writes to the
                                              question bank itself; see
                                              common/question_gen.py for the
                                              why-Haiku-and-not-trusted-math
                                              design notes
"""
import json
import os
import time
import boto3
from common import db, auth, scoring, question_gen, notifications

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

_cognito = boto3.client("cognito-idp")
_USER_POOL_ID = os.environ.get("USER_POOL_ID")
_bedrock = boto3.client("bedrock-runtime")
_BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
)
# Bedrock EU inference-profile rate card for Haiku 4.5, $/token (from
# list-foundation-model-agreement-offers) -- partner pricing, not the
# same as Anthropic's direct API rates.
_BEDROCK_INPUT_USD_PER_TOKEN = 1.10 / 1_000_000
_BEDROCK_OUTPUT_USD_PER_TOKEN = 5.50 / 1_000_000
_BEDROCK_MAX_SPEND_USD = float(os.environ.get("BEDROCK_MAX_SPEND_USD", "20"))


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def _all_cognito_users() -> dict:
    """sub -> {email, username} for every user in the pool (paginated) --
    lets the dashboard show emails instead of raw Cognito sub UUIDs.
    Best-effort: callers fall back to showing the raw id if this fails.
    """
    users = {}
    kwargs = {"UserPoolId": _USER_POOL_ID}
    while True:
        resp = _cognito.list_users(**kwargs)
        for u in resp.get("Users", []):
            attrs = {a["Name"]: a["Value"] for a in u.get("Attributes", [])}
            sub = attrs.get("sub")
            if sub:
                users[sub] = {"email": attrs.get("email", u["Username"]), "username": u["Username"]}
        token = resp.get("PaginationToken")
        if not token:
            break
        kwargs["PaginationToken"] = token
    return users


def _instructor_subs() -> set:
    """subs of every user in the `instructors` group -- used to exclude
    instructors from module-unlock notification fan-out.
    """
    subs = set()
    kwargs = {"UserPoolId": _USER_POOL_ID, "GroupName": "instructors"}
    while True:
        resp = _cognito.list_users_in_group(**kwargs)
        for u in resp.get("Users", []):
            attrs = {a["Name"]: a["Value"] for a in u.get("Attributes", [])}
            if attrs.get("sub"):
                subs.add(attrs["sub"])
        token = resp.get("NextToken")
        if not token:
            break
        kwargs["NextToken"] = token
    return subs


def _all_sessions_and_results():
    """One unfiltered scan, covering every checkpoint (placement + every
    module) -- the placement-only _cohort_data below is a thin filter on
    top of this, so existing placement call sites stay byte-for-byte
    unchanged while module-aware call sites can use this directly.
    """
    items = db.scan_all()
    sessions = [i for i in items if i["SK"].startswith("SESSION#")]
    results = {i["PK"].replace("RESULT#", ""): i for i in items if i["PK"].startswith("RESULT#")}
    feedback = [i for i in items if i["PK"].startswith("FEEDBACK#")]
    surveys = [i for i in items if i["PK"].startswith("SURVEY#")]
    translations = [i for i in items if i["SK"].startswith("TRANSLATION#")]
    return sessions, results, feedback, surveys, translations


def _cohort_data():
    sessions, results, feedback, surveys, _ = _all_sessions_and_results()
    placement_sessions = [s for s in sessions if s.get("checkpoint", "placement") == "placement"]
    return placement_sessions, results, feedback, surveys


def _translation_signals(users: dict) -> list:
    """One row per student who's clicked "Translate" at least once --
    count + most recent request -- for the Overview tab's language-
    support panel and each student's own profile.
    """
    _, _, _, _, translations = _all_sessions_and_results()
    by_student: dict = {}
    for t in translations:
        student_id = t["PK"].replace("STUDENT#", "")
        row = by_student.setdefault(student_id, {"studentId": student_id, "count": 0, "lastRequestedAt": 0, "items": []})
        row["count"] += 1
        row["lastRequestedAt"] = max(row["lastRequestedAt"], t.get("requestedAt", 0))
        row["items"].append({"domain": t.get("domain"), "itemId": t.get("itemId"), "requestedAt": t.get("requestedAt")})
    rows = list(by_student.values())
    for row in rows:
        row["email"] = users.get(row["studentId"], {}).get("email", row["studentId"])
        row["items"].sort(key=lambda i: i.get("requestedAt", 0), reverse=True)
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


# Module assessments are diagnostic, not a placement decision (see
# finalize_module in submit_answer) -- this threshold only drives the
# admin dashboard's passed/failed breakdown, it never gates or blocks a
# student from anything. Shares its value with scoring.MODULE_BADGE_BRONZE
# so "passed" and "earned a badge" never drift apart.
MODULE_PASS_THRESHOLD = scoring.MODULE_BADGE_BRONZE


def module_dashboard_stats() -> dict:
    """moduleId -> {moduleId, title, order, unlocked, started, completed,
    inProgress, passed, failed, avgScore} -- joins MODULE_META with every
    module session/result. Feeds GET /admin/modules (Modules tab, incl.
    its started/in-progress/passed/failed status bar) and the Overview
    cohort-trend chart.
    """
    sessions, results, _, _, _ = _all_sessions_and_results()
    module_sessions = [s for s in sessions if str(s.get("checkpoint", "")).startswith("module-")]
    modules_meta = {i["SK"]: i for i in db.query_partition("MODULE_META")}

    stats = {}
    for module_id, meta in modules_meta.items():
        m_sessions = [s for s in module_sessions if s.get("checkpoint") == module_id]
        done = [s for s in m_sessions if s.get("stage") == "done"]
        scores = []
        for s in done:
            session_id = s["SK"].replace("SESSION#", "")
            result = results.get(session_id)
            if result and "composite_score" in result:
                scores.append(result["composite_score"])
        passed = sum(1 for sc in scores if sc >= MODULE_PASS_THRESHOLD)
        stats[module_id] = {
            "moduleId": module_id,
            "title": meta.get("title"),
            "order": meta.get("order"),
            "dateRange": meta.get("dateRange"),
            "unlocked": meta.get("unlocked", False),
            "started": len(m_sessions),
            "completed": len(done),
            "inProgress": len(m_sessions) - len(done),
            "passed": passed,
            "failed": len(scores) - passed,
            "avgScore": round(sum(scores) / len(scores), 1) if scores else None,
        }
    return stats


def modules_list():
    stats = module_dashboard_stats()
    rows = sorted(stats.values(), key=lambda m: m.get("order") or 0)
    return response(200, {"modules": rows})


def module_update(module_id: str, body: dict):
    module = db.get_item("MODULE_META", module_id)
    if not module:
        return response(404, {"error": "unknown module"})

    updates = {}
    if "unlocked" in body:
        updates["unlocked"] = bool(body["unlocked"])
    if "title" in body and body["title"]:
        updates["title"] = body["title"]
    if not updates:
        return response(400, {"error": "nothing to update"})

    was_unlocked = module.get("unlocked", False)
    set_parts = []
    values = {}
    for i, (k, v) in enumerate(updates.items()):
        set_parts.append(f"{k} = :v{i}")
        values[f":v{i}"] = v
    if updates.get("unlocked") is True and not was_unlocked:
        set_parts.append("unlockedAt = :ua")
        values[":ua"] = int(time.time())
    db.update_item("MODULE_META", module_id, "SET " + ", ".join(set_parts), values)

    notified = 0
    if updates.get("unlocked") is True and not was_unlocked:
        title = updates.get("title", module.get("title"))
        try:
            users = _all_cognito_users()
            instructor_subs = _instructor_subs()
            notified = notifications.fan_out_module_unlock(module_id, title, users, instructor_subs)
        except Exception:
            notified = 0

    return response(200, {"ok": True, "notified": notified})


def _student_row(session: dict, results: dict, users: dict) -> dict:
    student_id = session["PK"].replace("STUDENT#", "")
    session_id = session["SK"].replace("SESSION#", "")
    result = results.get(session_id)
    user = users.get(student_id, {})
    started_at = session.get("started_at")
    completed_at = session.get("completed_at")
    return {
        "studentId": student_id,
        "email": user.get("email", student_id),
        "sessionId": session_id,
        "status": "done" if session.get("stage") == "done" else "in_progress",
        "stage": session.get("stage"),
        "track": result.get("track") if result else session.get("track"),
        "compositeScore": result.get("composite_score") if result else None,
        "domainScores": result.get("domain_scores") if result else None,
        "startedAt": started_at,
        "completedAt": completed_at,
        "durationSeconds": (completed_at - started_at) if (completed_at and started_at) else None,
        "hintsUsedTotal": sum(a.get("hintsUsed", 0) for a in session.get("answers", [])),
    }


def dashboard():
    sessions, results, feedback, surveys = _cohort_data()
    total_started = len(sessions)
    done_sessions = [s for s in sessions if s.get("stage") == "done"]
    total_completed = len(done_sessions)

    tracks: dict = {}
    domain_totals: dict = {}
    composite_scores = []
    durations = []
    for s in done_sessions:
        session_id = s["SK"].replace("SESSION#", "")
        result = results.get(session_id)
        if not result:
            continue
        tracks[result["track"]] = tracks.get(result["track"], 0) + 1
        composite_scores.append(result.get("composite_score", 0.0))
        for domain, pct in result.get("domain_scores", {}).items():
            if domain == "_overall":
                continue
            domain_totals.setdefault(domain, []).append(pct)
        if s.get("completed_at") and s.get("started_at"):
            durations.append(s["completed_at"] - s["started_at"])

    domain_avgs = {d: round(sum(v) / len(v), 1) for d, v in domain_totals.items() if v}
    avg_composite = round(sum(composite_scores) / len(composite_scores), 1) if composite_scores else 0.0
    avg_duration = round(sum(durations) / len(durations)) if durations else None

    # Per-question stats across every recorded answer, regardless of
    # session status -- shows which items are hardest / need the most
    # hints, even from students still mid-test.
    item_stats: dict = {}
    for s in sessions:
        for a in s.get("answers", []):
            key = f"{a.get('domain')}#{a.get('itemId')}"
            st = item_stats.setdefault(key, {
                "domain": a.get("domain"), "itemId": a.get("itemId"),
                "answered": 0, "correct": 0, "hints": 0,
            })
            st["answered"] += 1
            st["correct"] += 1 if a.get("correct") else 0
            st["hints"] += a.get("hintsUsed", 0)
    item_stats_list = sorted(
        (
            {**v, "passRate": round(100 * v["correct"] / v["answered"], 1),
             "avgHints": round(v["hints"] / v["answered"], 2)}
            for v in item_stats.values() if v["answered"]
        ),
        key=lambda x: x["passRate"],
    )

    try:
        users = _all_cognito_users()
        provisioned = len(users)
    except Exception:
        users = {}
        provisioned = None

    module_stats = module_dashboard_stats()
    module_performance = [
        {"moduleId": m["moduleId"], "title": m["title"], "order": m["order"],
         "avgScore": m["avgScore"], "completed": m["completed"]}
        for m in sorted(module_stats.values(), key=lambda m: m.get("order") or 0)
    ]

    return response(200, {
        "provisionedAccounts": provisioned,
        "totalStarted": total_started,
        "totalCompleted": total_completed,
        "completionRate": round(100 * total_completed / total_started, 1) if total_started else 0.0,
        "trackDistribution": tracks,
        "avgCompositeScore": avg_composite,
        "domainAverages": domain_avgs,
        "avgDurationSeconds": avg_duration,
        "itemStats": item_stats_list,
        "feedbackCount": len(feedback),
        "surveyCount": len(surveys),
        "modulePerformance": module_performance,
        "translationSignals": _translation_signals(users),
    })


def students():
    sessions, results, _, _ = _cohort_data()
    try:
        users = _all_cognito_users()
    except Exception:
        users = {}
    rows = [_student_row(s, results, users) for s in sessions]
    rows.sort(key=lambda r: r.get("startedAt") or 0, reverse=True)
    return response(200, {"students": rows})


def student_profile(student_id: str):
    sessions, results, _, _, translations = _all_sessions_and_results()
    all_student_sessions = [s for s in sessions if s["PK"] == f"STUDENT#{student_id}"]
    if not all_student_sessions:
        return response(404, {"error": "no sessions for this student"})

    try:
        users = _all_cognito_users()
    except Exception:
        users = {}
    email = users.get(student_id, {}).get("email", student_id)

    placement_sessions = [s for s in all_student_sessions if s.get("checkpoint", "placement") == "placement"]
    placement = None
    if placement_sessions:
        # Prefer a finalized session if one exists; otherwise the most
        # recent in-progress one.
        session = next((s for s in placement_sessions if s.get("stage") == "done"), None) \
            or max(placement_sessions, key=lambda s: s.get("started_at", 0))
        row = _student_row(session, results, users)
        session_id = session["SK"].replace("SESSION#", "")
        result = results.get(session_id)
        recommendation = scoring.recommend(result["domain_scores"], result["track"]) if result else None
        placement = {**row, "answers": session.get("answers", []), "recommendation": recommendation}

    modules_meta = {i["SK"]: i for i in db.query_partition("MODULE_META")}
    module_sessions = [s for s in all_student_sessions if str(s.get("checkpoint", "")).startswith("module-")]
    modules = {}
    for module_id, meta in sorted(modules_meta.items(), key=lambda kv: kv[1].get("order") or 0):
        m_sessions = [s for s in module_sessions if s.get("checkpoint") == module_id]
        if not m_sessions:
            modules[module_id] = {
                "moduleId": module_id, "title": meta.get("title"), "order": meta.get("order"),
                "status": "not_started" if meta.get("unlocked") else "locked",
            }
            continue
        session = next((s for s in m_sessions if s.get("stage") == "done"), None) \
            or max(m_sessions, key=lambda s: s.get("started_at", 0))
        session_id = session["SK"].replace("SESSION#", "")
        result = results.get(session_id)
        score = result.get("composite_score") if result else None
        modules[module_id] = {
            "moduleId": module_id, "title": meta.get("title"), "order": meta.get("order"),
            "status": "done" if session.get("stage") == "done" else "in_progress",
            "compositeScore": score,
            "badge": scoring.module_badge(score) if session.get("stage") == "done" else None,
            "startedAt": session.get("started_at"),
            "completedAt": session.get("completed_at"),
            "hintsUsed": sum(a.get("hintsUsed", 0) for a in session.get("answers", [])),
            "answers": session.get("answers", []),
        }

    student_translations = [t for t in translations if t["PK"] == f"STUDENT#{student_id}"]
    student_translations.sort(key=lambda t: t.get("requestedAt", 0), reverse=True)
    translation_requests = {
        "count": len(student_translations),
        "items": [{"domain": t.get("domain"), "itemId": t.get("itemId"), "requestedAt": t.get("requestedAt")}
                  for t in student_translations],
    }

    return response(200, {
        "studentId": student_id, "email": email, "placement": placement, "modules": modules,
        "translationRequests": translation_requests,
    })


def reset_student(student_id: str, checkpoint: str = "placement"):
    items = db.query_partition(f"STUDENT#{student_id}")
    deleted = []
    for item in items:
        sk = item["SK"]
        if sk.startswith("SESSION#") and item.get("checkpoint", "placement") == checkpoint:
            result_session_id = sk.replace("SESSION#", "")
            if db.get_item(f"RESULT#{result_session_id}", "SUMMARY"):
                db.delete_item(f"RESULT#{result_session_id}", "SUMMARY")
                deleted.append(f"RESULT#{result_session_id}/SUMMARY")
            db.delete_item(item["PK"], sk)
            deleted.append(sk)
        elif sk.startswith("TERMSTATE#") and checkpoint == "placement":
            # TERMSTATE items aren't tagged with a checkpoint -- only
            # today's terminal-type questions (placement) create them, so
            # only a placement reset should clear them.
            db.delete_item(item["PK"], sk)
            deleted.append(sk)
    return response(200, {"ok": True, "deleted": deleted})


def feedback_list():
    _, _, feedback, surveys = _cohort_data()
    feedback.sort(key=lambda f: f.get("submittedAt", 0), reverse=True)
    surveys.sort(key=lambda s: s.get("submittedAt", 0), reverse=True)
    return response(200, {"itemFeedback": feedback, "surveys": surveys})


def _question_view(item: dict) -> dict:
    """Full detail for the author's own view -- unlike items.public_item,
    answer_key/hints/scenario are exactly what an author needs to see to
    edit a question. Never reuse this for a student-facing response.
    """
    return {
        "domain": item["PK"].replace("QUESTION#", ""),
        "itemId": item["SK"].replace("ITEM#", ""),
        "type": item.get("type"),
        "prompt": item.get("prompt"),
        "answer_key": item.get("answer_key"),
        "hints": item.get("hints", []),
        "scenario": item.get("scenario"),
        "checkpoint": item.get("checkpoint", "placement"),
        "stage": item.get("stage", "stage0"),
    }


def questions_list():
    items = db.scan_all(pk_prefix="QUESTION#")
    rows = [_question_view(i) for i in items]
    rows.sort(key=lambda r: (r["domain"], r["itemId"]))
    return response(200, {"questions": rows})


def question_get(domain: str, item_id: str):
    item = db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}")
    if not item:
        return response(404, {"error": "question not found"})
    return response(200, _question_view(item))


def _validate_question_body(body: dict) -> str | None:
    if not body.get("domain") or not body.get("itemId"):
        return "domain and itemId are required"
    if body.get("type") not in ("terminal", "free-text"):
        return "type must be 'terminal' or 'free-text'"
    if not body.get("prompt"):
        return "prompt is required"
    answer_key = body.get("answer_key")
    if not answer_key or (isinstance(answer_key, list) and not any(answer_key)):
        return "answer_key is required (a string, or a list of acceptable synonyms)"
    hints = body.get("hints", [])
    if not isinstance(hints, list) or len(hints) not in (0, 3):
        return "hints must be a list of exactly 3 strings (or omitted)"
    if body["type"] == "terminal":
        files = (body.get("scenario") or {}).get("files")
        if not files:
            return "terminal questions need scenario.files"
    return None


def question_create(body: dict):
    err = _validate_question_body(body)
    if err:
        return response(400, {"error": err})
    domain, item_id = body["domain"], body["itemId"]
    if db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}"):
        return response(409, {"error": f"{domain}/{item_id} already exists -- use PUT to edit it"})
    item = {
        "PK": f"QUESTION#{domain}", "SK": f"ITEM#{item_id}",
        "checkpoint": body.get("checkpoint", "placement"),
        "stage": body.get("stage", "stage0"),
        "type": body["type"], "prompt": body["prompt"],
        "answer_key": body["answer_key"], "hints": body.get("hints", []),
    }
    if body["type"] == "terminal":
        item["scenario"] = body["scenario"]
    db.put_item(item)
    return response(201, _question_view(item))


def question_update(domain: str, item_id: str, body: dict):
    if not db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}"):
        return response(404, {"error": "question not found"})
    body = {**body, "domain": domain, "itemId": item_id}
    err = _validate_question_body(body)
    if err:
        return response(400, {"error": err})
    item = {
        "PK": f"QUESTION#{domain}", "SK": f"ITEM#{item_id}",
        "checkpoint": body.get("checkpoint", "placement"),
        "stage": body.get("stage", "stage0"),
        "type": body["type"], "prompt": body["prompt"],
        "answer_key": body["answer_key"], "hints": body.get("hints", []),
    }
    if body["type"] == "terminal":
        item["scenario"] = body["scenario"]
    db.put_item(item)
    return response(200, _question_view(item))


def question_delete(domain: str, item_id: str):
    if not db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}"):
        return response(404, {"error": "question not found"})
    db.delete_item(f"QUESTION#{domain}", f"ITEM#{item_id}")
    return response(200, {"ok": True})


_USAGE_PK, _USAGE_SK = "BEDROCK_USAGE", "QUESTION_GEN"


def _bedrock_spend_so_far() -> float:
    usage = db.get_item(_USAGE_PK, _USAGE_SK)
    return (usage or {}).get("spendUsd", 0.0)


def _record_bedrock_spend(input_tokens: int, output_tokens: int) -> float:
    """Atomically accumulates real spend from this call's actual token
    usage (never estimated ahead of time) and returns the new running
    total. This is the enforcement path for BEDROCK_MAX_SPEND_USD -- it's
    instant, unlike AWS Budgets/Cost Explorer data which lags real spend
    by up to ~24h and is only used here for the email notifications.
    """
    cost = input_tokens * _BEDROCK_INPUT_USD_PER_TOKEN + output_tokens * _BEDROCK_OUTPUT_USD_PER_TOKEN
    updated = db.update_item(
        _USAGE_PK, _USAGE_SK,
        "ADD spendUsd :c, callCount :one",
        {":c": round(cost, 6), ":one": 1},
    )
    return updated.get("spendUsd", cost)


def question_generate(body: dict):
    domain = body.get("domain")
    qtype = body.get("type")
    topic = (body.get("topic") or "").strip()
    if not domain or qtype not in ("terminal", "free-text") or not topic:
        return response(400, {"error": "domain, type ('terminal'|'free-text'), and topic are required"})
    if qtype == "terminal" and domain not in ("linux_cli", "windows_cli"):
        return response(400, {"error": "terminal questions are only supported for linux_cli or windows_cli"})

    spent = _bedrock_spend_so_far()
    if spent >= _BEDROCK_MAX_SPEND_USD:
        return response(402, {
            "error": f"AI question-generation budget reached (${spent:.2f} of ${_BEDROCK_MAX_SPEND_USD:.2f}). "
                     f"Write this question by hand, or raise BEDROCK_MAX_SPEND_USD to continue using AI drafting.",
        })

    system_prompt, user_message = question_gen.build_messages(domain, qtype, topic)
    try:
        # Bounded max_tokens: one question's JSON is small, and this
        # caps spend per click regardless of what the model tries to write.
        resp = _bedrock.converse(
            modelId=_BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            inferenceConfig={"maxTokens": 1200, "temperature": 0.7},
        )
        raw_text = resp["output"]["message"]["content"][0]["text"]
        usage = resp.get("usage", {})
        running_spend = _record_bedrock_spend(usage.get("inputTokens", 0), usage.get("outputTokens", 0))
    except Exception as e:
        return response(502, {"error": f"Bedrock call failed: {e}"})

    try:
        draft = question_gen.resolve_draft(raw_text, domain, qtype)
    except ValueError as e:
        return response(422, {"error": f"model draft wasn't usable, try again: {e}", "raw": raw_text})

    existing = db.query_prefix(f"QUESTION#{domain}", "ITEM#")
    draft["itemId"] = question_gen.next_item_id(domain, [i["SK"].replace("ITEM#", "") for i in existing])
    return response(200, {
        "draft": draft,
        "budgetSpentUsd": round(running_spend, 4),
        "budgetMaxUsd": _BEDROCK_MAX_SPEND_USD,
    })


def lambda_handler(event, context):
    if not auth.is_instructor(event):
        return response(403, {"error": "instructors only"})

    route = event.get("routeKey", "")
    path_params = event.get("pathParameters") or {}
    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (TypeError, ValueError):
            return response(400, {"error": "invalid JSON body"})

    if route == "GET /admin/results":
        return dashboard()
    if route == "GET /admin/students":
        return students()
    if route == "GET /admin/students/{studentId}":
        return student_profile(path_params.get("studentId"))
    if route == "POST /admin/students/{studentId}/reset":
        return reset_student(path_params.get("studentId"), body.get("checkpoint", "placement"))
    if route == "GET /admin/feedback":
        return feedback_list()
    if route == "GET /admin/modules":
        return modules_list()
    if route == "PUT /admin/modules/{moduleId}":
        return module_update(path_params.get("moduleId"), body)
    if route == "GET /admin/questions":
        return questions_list()
    if route == "POST /admin/questions":
        return question_create(body)
    if route == "POST /admin/questions/generate":
        return question_generate(body)
    if route == "GET /admin/questions/{domain}/{itemId}":
        return question_get(path_params.get("domain"), path_params.get("itemId"))
    if route == "PUT /admin/questions/{domain}/{itemId}":
        return question_update(path_params.get("domain"), path_params.get("itemId"), body)
    if route == "DELETE /admin/questions/{domain}/{itemId}":
        return question_delete(path_params.get("domain"), path_params.get("itemId"))

    return response(404, {"error": f"unknown admin route: {route}"})
