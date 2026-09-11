"""POST /session/{sessionId}/translate

A student clicking "Translate to Spanish" always logs the request (so
instructors can see who's hitting a language barrier -- see
student profile / Overview's "Language support signals"), and best-
effort translates the question text they're looking at via Amazon
Translate if they choose to continue past the English-encouragement
nudge (see frontend/test.html's two-button modal).

Stored under the student (PK=STUDENT#<id>), unlike question feedback
(keyed by item) -- this is read by student profile and by the cohort-
wide "who needs language support" view, both student-centric, not
item-centric.
"""
import json
import os
import time
import uuid
import boto3
from common import db, auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

# Amazon Translate isn't available in every region (eu-south-2, this
# project's home region, is one of the ones it's missing from) -- same
# region-quirk pattern as SES needing eu-west-1 (see
# bootstrap/ses-notification-identity.yaml), so pinned there rather than
# assumed to follow the stack's own region.
_TRANSLATE_REGION = os.environ.get("TRANSLATE_REGION", "eu-west-1")
_translate = boto3.client("translate", region_name=_TRANSLATE_REGION)


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    body = json.loads(event.get("body") or "{}")
    item_id = body.get("itemId")
    domain = body.get("domain")
    text = (body.get("text") or "").strip()
    if not item_id or not domain:
        return response(400, {"error": "itemId and domain are required"})

    now = int(time.time())
    record = {
        "PK": f"STUDENT#{student}",
        "SK": f"TRANSLATION#{now}#{uuid.uuid4().hex[:8]}",
        "domain": domain,
        "itemId": item_id,
        "requestedAt": now,
    }
    db.put_item(record)

    translated_text = None
    if text:
        try:
            result = _translate.translate_text(
                Text=text[:5000], SourceLanguageCode="en", TargetLanguageCode="es",
            )
            translated_text = result.get("TranslatedText")
        except Exception:
            translated_text = None  # best-effort -- the request is still logged either way

    return response(201, {"ok": True, "translatedText": translated_text})
