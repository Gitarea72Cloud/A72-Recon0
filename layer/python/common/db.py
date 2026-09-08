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
import boto3
from boto3.dynamodb.conditions import Key

_TABLE_NAME = os.environ.get("TABLE_NAME")
_dynamodb = boto3.resource("dynamodb")


def table():
    return _dynamodb.Table(_TABLE_NAME)


def get_item(pk: str, sk: str):
    resp = table().get_item(Key={"PK": pk, "SK": sk})
    return resp.get("Item")


def put_item(item: dict):
    table().put_item(Item=item)
    return item


def update_item(pk: str, sk: str, update_expr: str, expr_values: dict, expr_names: dict | None = None):
    kwargs = {
        "Key": {"PK": pk, "SK": sk},
        "UpdateExpression": update_expr,
        "ExpressionAttributeValues": expr_values,
        "ReturnValues": "ALL_NEW",
    }
    if expr_names:
        kwargs["ExpressionAttributeNames"] = expr_names
    resp = table().update_item(**kwargs)
    return resp.get("Attributes")


def query_prefix(pk: str, sk_prefix: str):
    resp = table().query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix)
    )
    return resp.get("Items", [])
