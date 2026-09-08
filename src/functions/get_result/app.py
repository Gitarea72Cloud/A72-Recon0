"""GET /session/{sessionId}/result"""
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

    session = db.get_item(f"STUDENT#{student}", f"SESSION#{session_id}")
    if not session:
        return response(404, {"error": "session not found"})
    if session.get("stage") != "done":
        return response(202, {"done": False, "stage": session.get("stage")})

    result = db.get_item(f"RESULT#{session_id}", "SUMMARY")
    return response(200, result or {"done": True, "track": session.get("track")})
