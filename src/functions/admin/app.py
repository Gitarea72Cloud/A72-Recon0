"""POST /admin/questions, GET /admin/results

Phase 2 work (instructor dashboard) per the roadmap — stubbed here so the
routes and the `instructors` Cognito-group gate exist from day one, without
pretending the admin UI is built yet.
"""
import json
from common import auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    if not auth.is_instructor(event):
        return response(403, {"error": "instructors only"})
    return response(501, {"error": "not implemented yet — Phase 2 on the roadmap"})
