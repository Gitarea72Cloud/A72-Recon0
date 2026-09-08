"""POST /session/{sessionId}/terminal

Runs one command against the virtual filesystem seeded for the student's
current item, and returns the simulated output. State (fs + full transcript)
lives server-side in DynamoDB under TERMSTATE#<itemId> — the client only
ever sends a raw command string, so there's nothing to spoof from devtools.

This is a deliberately small interpreter: real string processing, no real
OS/container/network underneath it at all — see the proposal for why that's
the point, not a shortcut. Command set: cd, pwd, ls (-l/-la), cat, stat/wc/du,
file, echo, base64 (-d/-e), with real pipes between them.
"""
import json
import time
from common import db, auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def ls_line(name: str, f: dict) -> str:
    size = len(f["content"])
    return f"{f['perms']}  1 student student  {size:>5} {f['date']} {name}"


def run_single(raw: str, files: dict, stdin: str | None):
    tokens = raw.strip().split()
    if not tokens:
        return {"out": ""}
    name = tokens[0]
    args = tokens[1:]
    flags = "".join(t for t in args if t.startswith("-"))
    fname = next((t for t in args if t in files), None)

    if name == "help":
        return {"out": "Available: ls, ls -l, ls -la, pwd, cd, cat <file>, stat|wc -c|du -b <file>, "
                        "file <file>, echo \"text\" | base64 -d, cat <file> | base64 -d"}
    if name == "pwd":
        return {"out": "/home/student"}
    if name == "cd":
        return {"out": ""}
    if name == "ls":
        names = list(files.keys())
        if "l" in flags:
            lines = [ls_line(n, files[n]) for n in names]
            if "a" in flags:
                lines = [
                    "drwxr-xr-x  2 student student   64 Oct 20 09:10 .",
                    "drwxr-xr-x  5 student student  160 Oct 18 11:02 ..",
                    *lines,
                ]
            return {"out": "\n".join(lines)}
        return {"out": "  ".join(names)}
    if name == "cat":
        if not fname:
            return {"out": f"cat: {args[0] if args else ''}: No such file or directory", "err": True}
        return {"out": files[fname]["content"], "stdout": files[fname]["content"]}
    if name in ("stat", "wc", "du"):
        if not fname:
            return {"out": f"{name}: missing file operand", "err": True}
        size = len(files[fname]["content"])
        return {"out": f"{size} {fname}" if name == "wc" else str(size)}
    if name == "file":
        if not fname:
            return {"out": "file: missing file operand", "err": True}
        kind = "ASCII text (Base64)" if fname.endswith(".b64") else "ASCII text"
        return {"out": f"{fname}: {kind}"}
    if name == "echo":
        text = " ".join(args).strip('"').strip("'")
        return {"out": text, "stdout": text}
    if name == "base64":
        import base64 as b64
        src = stdin if stdin is not None else (files[fname]["content"] if fname else "")
        try:
            if "d" in flags:
                out = b64.b64decode(src.strip()).decode("utf-8", errors="replace")
            else:
                out = b64.b64encode(src.encode("utf-8")).decode("ascii")
            return {"out": out}
        except Exception:
            return {"out": "base64: invalid input", "err": True}
    return {"out": f"bash: {name}: command not found", "err": True}


def run(raw: str, files: dict):
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    if not parts:
        return {"out": ""}
    stdin = None
    result = {"out": ""}
    for part in parts:
        result = run_single(part, files, stdin)
        stdin = result.get("stdout", result.get("out", ""))
    return result


def lambda_handler(event, context):
    session_id = event["pathParameters"]["sessionId"]
    student = auth.student_id(event)
    if not student:
        return response(401, {"error": "unauthorized"})

    body = json.loads(event.get("body") or "{}")
    item_id = body.get("itemId")
    command = body.get("command", "")
    if not item_id or not command:
        return response(400, {"error": "itemId and command are required"})

    session_key = f"SESSION#{session_id}"
    session = db.get_item(f"STUDENT#{student}", session_key)
    if not session:
        return response(404, {"error": "session not found"})

    term_key = f"TERMSTATE#{item_id}"
    state = db.get_item(f"STUDENT#{student}", term_key)
    if not state:
        # first command against this item: seed the virtual fs from the question bank
        question = next(
            (q for q in db.query_prefix("QUESTION#", f"ITEM#{item_id}") if q),
            None,
        )
        files = question["scenario"]["files"] if question else {}
        state = {
            "PK": f"STUDENT#{student}",
            "SK": term_key,
            "files": files,
            "transcript": [],
        }

    result = run(command, state["files"])
    state["transcript"] = state.get("transcript", []) + [
        {"command": command, "output": result["out"], "ts": int(time.time())}
    ]
    db.put_item(state)

    return response(200, {"output": result["out"], "isError": bool(result.get("err"))})
