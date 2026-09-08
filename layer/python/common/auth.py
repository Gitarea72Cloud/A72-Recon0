"""Pull the caller's identity out of the API Gateway HTTP API JWT authorizer context."""


def claims(event: dict) -> dict:
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return {}


def student_id(event: dict) -> str | None:
    return claims(event).get("sub")


def is_instructor(event: dict) -> bool:
    groups = claims(event).get("cognito:groups", "")
    # HTTP API JWT authorizer flattens list claims to a comma/space separated string
    return "instructors" in groups
