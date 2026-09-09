"""Admin/instructor dashboard API.

Every route here is gated by the `instructors` Cognito group
(auth.is_instructor) -- this is the only place that check matters, since
every route in this file reads or mutates data across ALL students, not
just the caller's own.

Routes (all through this one function, branched on event["routeKey"],
matching the one-function-many-routes pattern already used for the
original /admin/questions + /admin/results pair):
  GET  /admin/results                     cohort-wide dashboard metrics
  GET  /admin/students                    one row per student who has
                                            started or finished placement
  GET  /admin/students/{studentId}        full profile for one student
  POST /admin/students/{studentId}/reset  delete a student's placement
                                            session so they can retake it
  GET  /admin/feedback                    question feedback + exit survey
                                            responses submitted by students
  POST /admin/questions                   question-bank upload -- still
                                            not built, Phase 2 on the roadmap
"""
import json
import os
import boto3
from common import db, auth, scoring

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

_cognito = boto3.client("cognito-idp")
_USER_POOL_ID = os.environ.get("USER_POOL_ID")


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


def _cohort_data():
    items = db.scan_all()
    sessions = [i for i in items if i["SK"].startswith("SESSION#") and i.get("checkpoint") == "placement"]
    results = {i["PK"].replace("RESULT#", ""): i for i in items if i["PK"].startswith("RESULT#")}
    feedback = [i for i in items if i["PK"].startswith("FEEDBACK#")]
    surveys = [i for i in items if i["PK"].startswith("SURVEY#")]
    return sessions, results, feedback, surveys


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
        provisioned = len(_all_cognito_users())
    except Exception:
        provisioned = None

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
    sessions, results, _, _ = _cohort_data()
    student_sessions = [s for s in sessions if s["PK"] == f"STUDENT#{student_id}"]
    if not student_sessions:
        return response(404, {"error": "no placement session for this student"})

    # Prefer a finalized session if one exists; otherwise the most recent
    # in-progress one.
    session = next((s for s in student_sessions if s.get("stage") == "done"), None) \
        or max(student_sessions, key=lambda s: s.get("started_at", 0))

    try:
        users = _all_cognito_users()
    except Exception:
        users = {}
    row = _student_row(session, results, users)

    session_id = session["SK"].replace("SESSION#", "")
    result = results.get(session_id)
    recommendation = scoring.recommend(result["domain_scores"], result["track"]) if result else None

    return response(200, {**row, "answers": session.get("answers", []), "recommendation": recommendation})


def reset_student(student_id: str):
    items = db.query_partition(f"STUDENT#{student_id}")
    deleted = []
    for item in items:
        sk = item["SK"]
        if sk.startswith("SESSION#") and item.get("checkpoint") == "placement":
            result_session_id = sk.replace("SESSION#", "")
            if db.get_item(f"RESULT#{result_session_id}", "SUMMARY"):
                db.delete_item(f"RESULT#{result_session_id}", "SUMMARY")
                deleted.append(f"RESULT#{result_session_id}/SUMMARY")
            db.delete_item(item["PK"], sk)
            deleted.append(sk)
        elif sk.startswith("TERMSTATE#"):
            db.delete_item(item["PK"], sk)
            deleted.append(sk)
    return response(200, {"ok": True, "deleted": deleted})


def feedback_list():
    _, _, feedback, surveys = _cohort_data()
    feedback.sort(key=lambda f: f.get("submittedAt", 0), reverse=True)
    surveys.sort(key=lambda s: s.get("submittedAt", 0), reverse=True)
    return response(200, {"itemFeedback": feedback, "surveys": surveys})


def lambda_handler(event, context):
    if not auth.is_instructor(event):
        return response(403, {"error": "instructors only"})

    route = event.get("routeKey", "")
    path_params = event.get("pathParameters") or {}

    if route == "GET /admin/results":
        return dashboard()
    if route == "GET /admin/students":
        return students()
    if route == "GET /admin/students/{studentId}":
        return student_profile(path_params.get("studentId"))
    if route == "POST /admin/students/{studentId}/reset":
        return reset_student(path_params.get("studentId"))
    if route == "GET /admin/feedback":
        return feedback_list()
    if route == "POST /admin/questions":
        return response(501, {"error": "question-bank upload not implemented yet"})

    return response(404, {"error": f"unknown admin route: {route}"})
