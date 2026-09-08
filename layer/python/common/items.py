"""Ordered Stage 0/A/B item sequencing.

The full spec eventually has ~20 Stage 0 items across four domains; v1 has
just the Linux CLI domain seeded, so this walks whichever domains have data
and treats the rest as empty -- nothing else needs to change here when more
domains get content.
"""
from . import db, scoring

STAGE_DOMAINS = {
    "stage0": [d for d in scoring.DOMAINS if d != "tooling_familiarity"],
    "stageA": scoring.DOMAINS,  # tooling_familiarity is Stage A only
    "stageB": [d for d in scoring.DOMAINS if d != "tooling_familiarity"],
}


def stage_items(stage: str) -> list[dict]:
    ordered = []
    for domain in STAGE_DOMAINS.get(stage, []):
        items = db.query_prefix(f"QUESTION#{domain}", "ITEM#")
        ordered.extend(i for i in items if i.get("stage") == stage)
    return ordered


def next_item(session: dict) -> tuple[dict | None, int, int]:
    """(item_or_None, 1-indexed position, total) for the session's current stage."""
    stage = session["stage"]
    items = stage_items(stage)
    answered = len([a for a in session.get("answers", []) if a.get("stage") == stage])
    total = len(items)
    if answered >= total:
        return None, answered, total
    return items[answered], answered + 1, total


def public_item(item: dict) -> dict:
    """Strip answer_key/scenario before an item ever reaches the client.

    The terminal's virtual filesystem (scenario.files) is re-derived
    server-side by terminal-exec from domain+itemId on first command, so
    the client never needs it sent over the wire either.
    """
    return {
        "itemId": item["SK"].replace("ITEM#", ""),
        "domain": item["PK"].replace("QUESTION#", ""),
        "prompt": item.get("prompt"),
        "type": item.get("type"),
    }
