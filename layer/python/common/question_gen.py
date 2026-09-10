"""AI-assisted question drafting (instructor-only, see src/functions/admin).

Design principle: the model drafts creative content (prompt wording,
scenario files, hint phrasing) but never gets trusted to do exact
arithmetic. For anything with a deterministic right answer -- a byte
count, a hash, a Base64 transform -- the model outputs a *directive*
saying which file and which transform, and this module computes the
actual answer_key in Python. An LLM inventing a byte count or hash by
"eyeballing" a string is exactly the kind of subtle-wrong-answer bug
that's easy to ship and brutal to debug once it's making students fail
an unanswerable question.

Free-text conceptual answers (no interpreter to check them against) and
scenario/prompt wording are trusted from the model directly, but the
route this feeds (POST /admin/questions/generate) always returns a DRAFT
for a human to review/edit -- nothing here writes to the question bank.
"""
import base64
import hashlib
import json
import re

LINUX_COMMANDS = """\
Linux terminal (terminal_exec) supports ONLY these commands, nothing else:
  pwd, cd, ls (bare, -l, -la), cat <file>, stat/wc/du <file> (report byte
  size), file <file> (reports "ASCII text (Base64)" if the filename ends
  in .b64, else "ASCII text" -- it does NOT actually inspect content),
  echo "text", base64 -d (decode) / base64 -e (encode), with real pipes
  (|) chaining any of these. stat/wc/du also accept piped stdin, not just
  a filename. There is no grep, find, chmod, or any other command."""

POWERSHELL_COMMANDS = """\
PowerShell terminal (powershell_exec) supports ONLY these cmdlets:
  Get-Location, Set-Location, Get-ChildItem (gci/dir/ls, bare or -Name),
  Get-Item <file> (shows Length), Get-Content <file> (cat/type/gc),
  Measure-Object -Character (character count of piped input),
  ConvertFrom-Base64String / ConvertTo-Base64String (decode/encode,
  piped or direct arg -- these are a sandbox simplification, not real
  PowerShell cmdlets), Get-FileHash <file> [-Algorithm SHA256|MD5]
  (defaults to SHA256), Write-Output (echo), with pipes. The
  (Expression).Length / .Count idiom also works. There is no real file
  type detection cmdlet."""

SCHEMA_INSTRUCTIONS = """\
Respond with ONLY a single JSON object, no markdown fences, no commentary.

Schema:
{
  "prompt": "the question text shown to the student",
  "hints": ["hint 1: a nudge, not the answer", "hint 2: names the command/concept", "hint 3: near-complete answer"],
  "scenario_files": {"filename.ext": "file content as a string", ...},
  "answer": {
    "mode": "compute" | "literal",
    // if mode is "compute": a deterministic transform of ONE file's
    // content, which the backend (not you) will actually execute --
    // do not attempt to compute the numeric/hash/encoded value yourself.
    "compute_type": "byte_length" | "decode_base64" | "encode_base64" | "sha256" | "md5",
    "file": "filename.ext",              // required for byte_length/decode_base64/sha256/md5
    "encode_text": "literal text",       // required for encode_base64 instead of "file"
    // if mode is "literal": you ARE the source of truth (e.g. a
    // filename, a permission string, a fact read directly from a file
    // you wrote, or a conceptual free-text answer) -- give the exact
    // expected student answer.
    "literal_value": "the exact expected answer, or a list of a few acceptable synonyms"
  }
}

Rules:
- For "terminal" type questions, scenario_files must contain every file
  the prompt references, with realistic, specific content (not
  placeholder lorem ipsum) -- and only commands from the allowed list
  above should be needed to answer it.
- For "free-text" type questions, omit scenario_files entirely and use
  answer.mode "literal" with a short, unambiguous answer (a term,
  acronym, or yes/no) -- something exact-match gradeable, not an
  open-ended explanation.
- sha256/md5 compute_type is only valid for PowerShell (windows_cli)
  questions -- the Linux interpreter has no hashing command.
- Pick answer.mode "compute" whenever the answer is a byte count, a
  decoded/encoded string, or a hash -- never hand-compute those yourself
  into answer.literal_value.
- Keep it appropriate for someone INITIATING in the field, not already
  expert -- no assumed jargon beyond what the prompt itself explains.
"""


def build_messages(domain: str, qtype: str, topic: str) -> tuple[str, str]:
    """Returns (system_prompt, user_message) for the Bedrock call."""
    if qtype == "terminal":
        if domain == "windows_cli":
            cmd_ref = POWERSHELL_COMMANDS
        elif domain == "linux_cli":
            cmd_ref = LINUX_COMMANDS
        else:
            cmd_ref = LINUX_COMMANDS + "\n\n" + POWERSHELL_COMMANDS
    else:
        cmd_ref = "(free-text question -- no terminal, no scenario_files needed)"

    system = (
        "You are drafting ONE placement-test question for a cybersecurity "
        "bootcamp's entry screening. This is a candidate draft an instructor "
        "will review and edit before it ever reaches a student -- be "
        "concrete and specific, not generic.\n\n"
        f"{cmd_ref}\n\n{SCHEMA_INSTRUCTIONS}"
    )
    user = f'Domain: {domain}\nQuestion type: {qtype}\nTopic/idea from the instructor: "{topic}"'
    return system, user


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def resolve_draft(raw_model_text: str, domain: str, qtype: str) -> dict:
    """Parses the model's JSON and computes any "compute" answer
    deterministically. Raises ValueError on anything malformed or
    inconsistent -- callers should surface that as a clear "try again"
    rather than silently shipping a broken question.
    """
    data = _extract_json(raw_model_text)

    prompt = data.get("prompt")
    hints = data.get("hints") or []
    if not prompt or not isinstance(hints, list) or len(hints) != 3:
        raise ValueError("model response missing prompt or exactly 3 hints")

    scenario_files = data.get("scenario_files") or {}
    answer = data.get("answer") or {}
    mode = answer.get("mode")

    if mode == "literal":
        value = answer.get("literal_value")
        if not value:
            raise ValueError("literal answer missing literal_value")
        answer_key = value
    elif mode == "compute":
        compute_type = answer.get("compute_type")
        if compute_type == "encode_base64":
            src = answer.get("encode_text")
            if src is None:
                raise ValueError("encode_base64 missing encode_text")
            answer_key = base64.b64encode(src.encode("utf-8")).decode("ascii")
        else:
            fname = answer.get("file")
            if fname not in scenario_files:
                raise ValueError(f"compute answer references unknown file {fname!r}")
            content = scenario_files[fname]
            if compute_type == "byte_length":
                answer_key = str(len(content))
            elif compute_type == "decode_base64":
                try:
                    answer_key = base64.b64decode(content.strip()).decode("utf-8", errors="strict")
                except Exception as e:
                    raise ValueError(f"decode_base64: file content isn't valid Base64 UTF-8: {e}")
            elif compute_type == "sha256":
                answer_key = hashlib.sha256(content.encode("utf-8")).hexdigest().upper()
            elif compute_type == "md5":
                answer_key = hashlib.md5(content.encode("utf-8")).hexdigest().upper()
            else:
                raise ValueError(f"unknown compute_type {compute_type!r}")
    else:
        raise ValueError(f"answer.mode must be 'compute' or 'literal', got {mode!r}")

    draft = {
        "type": qtype,
        "domain": domain,
        "prompt": prompt,
        "hints": hints,
        "answer_key": answer_key,
    }
    if qtype == "terminal":
        draft["scenario"] = {"files": {
            name: {"content": content, "date": "Jan 01 00:00"}
            for name, content in scenario_files.items()
        }}
    return draft


def next_item_id(domain: str, existing_ids: list) -> str:
    """domain-appropriate next id, e.g. linux-011, following the existing
    <shortname>-NNN convention so generated items sort predictably.
    """
    short = {
        "linux_cli": "linux", "windows_cli": "windows",
        "red_team": "red", "blue_team": "blue", "grey_team": "grey",
    }.get(domain, domain.split("_")[0])
    nums = []
    for iid in existing_ids:
        m = re.match(rf"^{re.escape(short)}-(\d+)$", iid)
        if m:
            nums.append(int(m.group(1)))
    return f"{short}-{(max(nums) + 1) if nums else 1:03d}"
