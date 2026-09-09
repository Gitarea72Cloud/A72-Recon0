"""Thin DynamoDB helpers for the A72-Recon0 single-table schema.

Schema (see /README.md for the full picture):
  STUDENT#<id>        PROFILE                name, email, cohort, status
  STUDENT#<id>        SESSION#<sessionId>     checkpoint, stage, answers[], stage_scores
  STUDENT#<id>        TERMSTATE#<itemId>      virtual fs snapshot, transcript[]
  QUESTION#<domain>   ITEM#<qid>              checkpoint, stage, type, scenario, prompt, answer_key
  RESULT#<sessionId>  SUMMARY                 composite_score, domain_scores, track, decided_at
  COHORT#<intake>     META                    open_at, close_at, roster
"""
import os
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key

_TABLE_NAME = os.environ.get("TABLE_NAME")
_dynamodb = boto3.resource("dynamodb")


def table():
    return _dynamodb.Table(_TABLE_NAME)


def _floats_to_decimal(value):
    """DynamoDB's resource API rejects Python float outright -- Decimal only.

    Scoring produces plain floats (percentages), so every write goes
    through this rather than trusting each call site to remember.
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _floats_to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_floats_to_decimal(v) for v in value]
    return value


def _decimal_to_native(value):
    """Inverse of _floats_to_decimal, applied on read so nothing above this
    layer -- scoring, business logic, JSON responses -- ever has to deal
    with Decimal (json.dumps() can't serialize it without a custom encoder).
    """
    if isinstance(value, Decimal):
        as_int = int(value)
        return as_int if as_int == value else float(value)
    if isinstance(value, dict):
        return {k: _decimal_to_native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decimal_to_native(v) for v in value]
    return value


def get_item(pk: str, sk: str):
    resp = table().get_item(Key={"PK": pk, "SK": sk})
    item = resp.get("Item")
    return _decimal_to_native(item) if item is not None else None


def put_item(item: dict):
    table().put_item(Item=_floats_to_decimal(item))
    return item


def update_item(pk: str, sk: str, update_expr: str, expr_values: dict, expr_names: dict | None = None):
    kwargs = {
        "Key": {"PK": pk, "SK": sk},
        "UpdateExpression": update_expr,
        "ExpressionAttributeValues": _floats_to_decimal(expr_values),
        "ReturnValues": "ALL_NEW",
    }
    if expr_names:
        kwargs["ExpressionAttributeNames"] = expr_names
    resp = table().update_item(**kwargs)
    attrs = resp.get("Attributes")
    return _decimal_to_native(attrs) if attrs is not None else None


def query_prefix(pk: str, sk_prefix: str):
    resp = table().query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix)
    )
    return _decimal_to_native(resp.get("Items", []))


def delete_item(pk: str, sk: str):
    table().delete_item(Key={"PK": pk, "SK": sk})


def query_partition(pk: str) -> list[dict]:
    """Every item under one partition key -- e.g. everything for one
    student -- via Query (cheap, indexed) rather than Scan.
    """
    resp = table().query(KeyConditionExpression=Key("PK").eq(pk))
    return _decimal_to_native(resp.get("Items", []))


def scan_all(pk_prefix: str | None = None) -> list[dict]:
    """Full-table scan, paginated. Fine at this scale (one cohort's worth
    of students, a few thousand items at most) -- the admin dashboard is
    the only caller, and it's not on any student-facing latency path. If
    this table ever gets big enough for Scan to be a real cost/latency
    concern, that's the point to add a GSI instead of reaching for this.
    """
    items = []
    filter_expr = None
    if pk_prefix:
        from boto3.dynamodb.conditions import Attr
        filter_expr = Attr("PK").begins_with(pk_prefix)

    last_key = None
    while True:
        kwargs = {}
        if filter_expr is not None:
            kwargs["FilterExpression"] = filter_expr
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        resp = table().scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
    return _decimal_to_native(items)
