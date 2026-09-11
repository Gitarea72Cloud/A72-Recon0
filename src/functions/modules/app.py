"""GET /modules

Student-facing list of the 11 module assessments, joined with the
caller's own sessions so each entry carries their status: locked (not
yet opened by the instructor), unlocked (open, not started), in_progress,
or done (with their score). Read-only, student-scoped -- never exposes
another student's data.
"""
import json
from common import db, auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    modules_meta = db.query_partition("MODULE_META")
    student_sessions = db.query_partition(f"STUDENT#{student}")
    sessions_by_checkpoint = {}
    for s in student_sessions:
        if not s["SK"].startswith("SESSION#"):
            continue
        checkpoint = s.get("checkpoint")
        if checkpoint:
            sessions_by_checkpoint.setdefault(checkpoint, []).append(s)

    rows = []
    for meta in modules_meta:
        module_id = meta["SK"]
        unlocked = meta.get("unlocked", False)
        m_sessions = sessions_by_checkpoint.get(module_id, [])
        if not unlocked:
            status, score = "locked", None
        elif not m_sessions:
            status, score = "unlocked", None
        else:
            session = next((s for s in m_sessions if s.get("stage") == "done"), None) \
                or max(m_sessions, key=lambda s: s.get("started_at", 0))
            if session.get("stage") == "done":
                status = "done"
                result = db.get_item(f"RESULT#{session['SK'].replace('SESSION#', '')}", "SUMMARY")
                score = result.get("composite_score") if result else None
            else:
                status, score = "in_progress", None
        rows.append({
            "moduleId": module_id, "title": meta.get("title"), "order": meta.get("order"),
            "dateRange": meta.get("dateRange"), "status": status, "score": score,
        })

    rows.sort(key=lambda r: r.get("order") or 0)
    return response(200, {"modules": rows})
