"""GET /notifications, POST /notifications/{notificationId}/read

Student-scoped, same ownership pattern as every /session/* route --
only ever reads/writes the calling student's own NOTIFICATION# items
(PK=STUDENT#<id>). Written by admin.module_update's unlock fan-out
(see common/notifications.py).
"""
import json
from common import db, auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def list_notifications(student: str):
    items = db.query_prefix(f"STUDENT#{student}", "NOTIFICATION#")
    items.sort(key=lambda i: i.get("createdAt", 0), reverse=True)
    items = items[:50]
    rows = [{
        "notificationId": i["SK"].replace("NOTIFICATION#", ""),
        "title": i.get("title"), "body": i.get("body"),
        "moduleId": i.get("moduleId"), "isRead": i.get("isRead", False),
        "createdAt": i.get("createdAt"),
    } for i in items]
    unread = sum(1 for r in rows if not r["isRead"])
    return response(200, {"notifications": rows, "unread": unread})


def mark_read(student: str, notification_id: str):
    sk = f"NOTIFICATION#{notification_id}"
    if not db.get_item(f"STUDENT#{student}", sk):
        return response(404, {"error": "notification not found"})
    db.update_item(f"STUDENT#{student}", sk, "SET isRead = :t", {":t": True})
    return response(200, {"ok": True})


def lambda_handler(event, context):
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    route = event.get("routeKey", "")
    path_params = event.get("pathParameters") or {}

    if route == "GET /notifications":
        return list_notifications(student)
    if route == "POST /notifications/{notificationId}/read":
        return mark_read(student, path_params.get("notificationId"))

    return response(404, {"error": f"unknown route: {route}"})
