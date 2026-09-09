"""POST /session/{sessionId}/powershell

The Windows-flavored sibling of terminal_exec: same deliberately-small,
simulated-filesystem design (see terminal_exec's docstring for why), just
speaking PowerShell verbs instead of bash. Kept as its own function/route
so the Linux engine stays untouched by anything Windows-specific.

Command set (Verb-Noun cmdlets + their common aliases), with real pipes:
  Get-Location (pwd), Set-Location (cd), Get-ChildItem (gci/dir/ls),
  Get-Item (gi), Get-Content (cat/type/gc), Measure-Object -Character,
  ConvertFrom-Base64String, ConvertTo-Base64String, Get-FileHash,
  Write-Output (echo).

Two of these — ConvertFrom/ConvertTo-Base64String — aren't real built-in
PowerShell cmdlets (the real equivalent is a [Convert]::...String() method
chain); they're a deliberate simplification so this stays a small,
pipe-based interpreter rather than a .NET expression parser, the same
tradeoff terminal_exec already makes for `base64`.
"""
import hashlib
import json
import time
from common import db, auth

HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def response(status: int, body: dict):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def gci_line(name: str, f: dict) -> str:
    size = len(f["content"])
    return f"-a----        {f['date']}  {size:>10}  {name}"


def flag_value(args: list[str], flag: str) -> str | None:
    if flag in args:
        idx = args.index(flag)
        return args[idx + 1] if idx + 1 < len(args) else None
    return None


def run_single(raw: str, files: dict, stdin: str | None):
    tokens = raw.strip().split()
    if not tokens:
        return {"out": ""}
    name = tokens[0]
    args = tokens[1:]
    flags = [t for t in args if t.startswith("-")]
    fname = next((t for t in args if t in files), None)

    if name == "help":
        return {"out": "Available: Get-ChildItem (gci/dir/ls) [-Name], Get-Item <file>, "
                        "Get-Content <file> (cat/type/gc), Get-Location (pwd), Set-Location (cd), "
                        "Measure-Object -Character, ConvertFrom-Base64String, ConvertTo-Base64String, "
                        "Get-FileHash <file> [-Algorithm SHA256|MD5], Write-Output (echo)"}
    if name in ("Get-Location", "pwd"):
        return {"out": "C:\\Users\\student"}
    if name in ("Set-Location", "cd"):
        return {"out": ""}
    if name in ("Get-ChildItem", "gci", "dir", "ls"):
        names = list(files.keys())
        if "-Name" in flags:
            return {"out": "\n".join(names)}
        header = "Mode                 LastWriteTime           Length  Name\n" \
                 "----                 -------------           ------  ----"
        rows = [gci_line(n, files[n]) for n in names]
        return {"out": header + "\n" + "\n".join(rows)}
    if name in ("Get-Item", "gi"):
        if not fname:
            return {"out": "Get-Item: Cannot find path — no matching file operand", "err": True}
        header = "Mode                 LastWriteTime           Length  Name\n" \
                 "----                 -------------           ------  ----"
        return {"out": header + "\n" + gci_line(fname, files[fname])}
    if name in ("Get-Content", "cat", "type", "gc"):
        if not fname:
            return {"out": f"Get-Content: Cannot find path '{args[0] if args else ''}'", "err": True}
        return {"out": files[fname]["content"], "stdout": files[fname]["content"]}
    if name in ("Measure-Object", "measure"):
        src = stdin if stdin is not None else ""
        if "-Character" in flags:
            return {"out": f"Characters : {len(src)}"}
        return {"out": "Count : 1"}
    if name == "ConvertFrom-Base64String":
        import base64 as b64
        src = stdin if stdin is not None else (files[fname]["content"] if fname else "")
        try:
            out = b64.b64decode(src.strip()).decode("utf-8", errors="replace")
            return {"out": out, "stdout": out}
        except Exception:
            return {"out": "ConvertFrom-Base64String: invalid input", "err": True}
    if name == "ConvertTo-Base64String":
        import base64 as b64
        src = stdin if stdin is not None else " ".join(args).strip('"').strip("'")
        out = b64.b64encode(src.encode("utf-8")).decode("ascii")
        return {"out": out, "stdout": out}
    if name == "Get-FileHash":
        if not fname:
            return {"out": "Get-FileHash: Cannot find path — no matching file operand", "err": True}
        algo = (flag_value(args, "-Algorithm") or "SHA256").upper()
        try:
            digest = hashlib.new(algo.lower(), files[fname]["content"].encode("utf-8")).hexdigest().upper()
        except ValueError:
            return {"out": f"Get-FileHash: unsupported algorithm '{algo}'", "err": True}
        return {"out": f"Algorithm : {algo}\nHash      : {digest}\nPath      : {fname}"}
    if name in ("Write-Output", "echo"):
        text = " ".join(args).strip('"').strip("'")
        return {"out": text, "stdout": text}
    return {"out": f"{name} : The term '{name}' is not recognized as a cmdlet.", "err": True}


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
    domain = body.get("domain")
    command = body.get("command", "")
    if not item_id or not domain or not command:
        return response(400, {"error": "itemId, domain and command are required"})

    session_key = f"SESSION#{session_id}"
    session = db.get_item(f"STUDENT#{student}", session_key)
    if not session:
        return response(404, {"error": "session not found"})

    term_key = f"TERMSTATE#{item_id}"
    state = db.get_item(f"STUDENT#{student}", term_key)
    if not state:
        question = db.get_item(f"QUESTION#{domain}", f"ITEM#{item_id}")
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
