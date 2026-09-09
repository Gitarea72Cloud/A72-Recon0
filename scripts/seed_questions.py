#!/usr/bin/env python3
"""Seed the Stage 0 item bank — 10 Linux CLI items + 10 PowerShell items.

This is NOT the real item bank — that's Phase 0 content work with the
Module 1 professors (~30-40 items). It's enough to give real variety
without making the test too long.

Each item carries 3 progressive hints (nudge -> names the command ->
near-complete command), unlocked on demand via GET_HINT and never sent to
the client up front — see common/items.py's public_item and
src/functions/get_hint. Using a hint costs the student credit on that
item (see common/scoring.py's credit_for), so hints are a real trade-off,
not free information.

Linux items use only commands terminal_exec implements: cd, pwd, ls
(-l/-la), cat, stat/wc/du, file, echo, base64 (-d/-e), with pipes.

PowerShell items use only cmdlets powershell_exec implements:
Get-ChildItem/gci/dir/ls, Get-Item, Get-Content/cat/type/gc,
Get-Location/pwd, Set-Location/cd, Measure-Object -Character,
ConvertFrom-Base64String, ConvertTo-Base64String, Get-FileHash
[-Algorithm SHA256|MD5], Write-Output/echo, with pipes, plus the
(Expression).Length / .Count idiom.

Usage:
    python3 scripts/seed_questions.py --table a72-recon0-dev --region eu-south-2
"""
import argparse
import base64
import hashlib
import boto3


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest().upper()


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest().upper()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--region", default="eu-south-2")
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(args.table)

    secret_phrase = "you just automated your first placement task"
    secret_b64 = b64(secret_phrase)
    flag_phrase = "the flag is base64 all the way down"
    flag_b64 = b64(flag_phrase)
    readme_content = "Placement test sandbox. Nothing here is a real filesystem."
    vault_phrase = "you found the hidden note under the doormat"
    vault_b64 = b64(vault_phrase)

    linux_items = [
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-001",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "What is the size, in bytes, of secret.b64?",
            "answer_key": str(len(secret_b64)),
            "hints": [
                "Think about which commands report a file's size rather than its contents.",
                "Try `stat`, `wc`, or `du` on the file.",
                "Run `stat secret.b64` (or `wc secret.b64` / `du secret.b64`) and read the number it prints.",
            ],
            "scenario": {"files": {
                "notes.txt": {"content": "Reminder: rotate the API keys before Friday.", "perms": "-rw-r--r--", "date": "Oct 20 09:14"},
                "secret.b64": {"content": secret_b64, "perms": "-rw-r--r--", "date": "Oct 20 09:15"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-002",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "secret.b64 is Base64-encoded. What does it say?",
            "answer_key": secret_phrase,
            "hints": [
                "You'll need to read the file's contents, then reverse the encoding.",
                "`cat` shows raw content; `base64 -d` reverses Base64 encoding.",
                "Run `cat secret.b64 | base64 -d` and read the decoded text.",
            ],
            "scenario": {"files": {"secret.b64": {"content": secret_b64, "perms": "-rw-r--r--", "date": "Oct 20 09:15"}}},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-003",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Two files are here. Which one does `file` report as Base64-encoded?",
            "answer_key": "payload.b64",
            "hints": [
                "There's a command that identifies what kind of content a file holds.",
                "Try running `file` on each of the two files.",
                "Run `file payload.b64` and `file report.txt` and compare the two outputs.",
            ],
            "scenario": {"files": {
                "report.txt": {"content": "Quarterly access review — no findings.", "perms": "-rw-r--r--", "date": "Oct 19 14:02"},
                "payload.b64": {"content": flag_b64, "perms": "-rw-r--r--", "date": "Oct 19 14:03"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-004",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many bytes is readme.txt?",
            "answer_key": str(len(readme_content)),
            "hints": [
                "Same idea as any file-size question — one command reports it directly.",
                "`stat`, `wc`, or `du` all report a file's size.",
                "Run `stat readme.txt` and read the number.",
            ],
            "scenario": {"files": {"readme.txt": {"content": readme_content, "perms": "-rw-r--r--", "date": "Oct 18 10:30"}}},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-005",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "payload.b64 is Base64-encoded. What's the flag inside it?",
            "answer_key": flag_phrase,
            "hints": [
                "Reverse the encoding on this file the same way you would any Base64 file.",
                "Pipe the file's contents into the Base64 decoder.",
                "Run `cat payload.b64 | base64 -d`.",
            ],
            "scenario": {"files": {"payload.b64": {"content": flag_b64, "perms": "-rw-r--r--", "date": "Oct 19 14:03"}}},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-006",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many files are in this directory?",
            "answer_key": "3",
            "hints": [
                "There's a command that lists what's in the current directory.",
                "Try `ls` with no arguments.",
                "Run `ls` and count the names it prints.",
            ],
            "scenario": {"files": {
                "app.log": {"content": "server started ok", "perms": "-rw-r--r--", "date": "Sep 01 08:00"},
                "config.yml": {"content": "env: staging", "perms": "-rw-r--r--", "date": "Sep 01 08:00"},
                "notes.md": {"content": "# TODO\n- rotate creds", "perms": "-rw-r--r--", "date": "Sep 01 08:01"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-007",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "What permissions does `ls -l` show for deploy_key.pem?",
            "answer_key": "-r--------",
            "hints": [
                "You need the long-form listing, not the plain one.",
                "Add the `-l` flag to `ls`.",
                "Run `ls -l` and read the permissions field (leftmost column) for deploy_key.pem.",
            ],
            "scenario": {"files": {"deploy_key.pem": {
                "content": "-----BEGIN PRIVATE KEY-----\nMOCKKEYDATA\n-----END PRIVATE KEY-----",
                "perms": "-r--------", "date": "Aug 30 11:12",
            }}},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-008",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "According to incident.log, what's the ticket number?",
            "answer_key": "INC-4471",
            "hints": [
                "Read the file and look for something formatted like an ID.",
                "Use `cat` to print incident.log's contents.",
                "Run `cat incident.log` — the ticket number appears after `ticket=`.",
            ],
            "scenario": {"files": {"incident.log": {
                "content": "2026-09-01 03:14 ALERT ticket=INC-4471 status=open",
                "perms": "-rw-r--r--", "date": "Sep 01 03:14",
            }}},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-009",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Three files are here. Which one does `file` report as Base64-encoded?",
            "answer_key": "keys.b64",
            "hints": [
                "One command tells you what type of content a file actually holds.",
                "Run `file` on each of the three files.",
                "Run `file keys.b64`, `file manifest.txt`, and `file readme2.txt` and compare.",
            ],
            "scenario": {"files": {
                "manifest.txt": {"content": "v1.4.0 release manifest", "perms": "-rw-r--r--", "date": "Sep 02 09:00"},
                "keys.b64": {"content": vault_b64, "perms": "-rw-r--r--", "date": "Sep 02 09:01"},
                "readme2.txt": {"content": "See manifest.txt for details.", "perms": "-rw-r--r--", "date": "Sep 02 09:02"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-010",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "vault.b64 is Base64-encoded. What's inside it?",
            "answer_key": vault_phrase,
            "hints": [
                "Same decoding approach as the other .b64 files here.",
                "Pipe its contents into the Base64 decoder.",
                "Run `cat vault.b64 | base64 -d`.",
            ],
            "scenario": {"files": {"vault.b64": {"content": vault_b64, "perms": "-rw-r--r--", "date": "Sep 02 09:01"}}},
        },
    ]

    ps_readme = "PowerShell placement sandbox. Nothing here is a real filesystem."
    ps_secret_phrase = "welcome to the powershell placement track"
    ps_secret_b64 = b64(ps_secret_phrase)
    ps_report = "Q3 executive summary draft — confidential, do not distribute externally."
    ps_payload_phrase = "root access confirmed on host web01"
    ps_payload_b64 = b64(ps_payload_phrase)
    ps_service_log = "2026-09-08 SERVICE health=ok failed_logins=7 uptime_days=42"
    ps_integrity = "Build artifact checksum verification passed for release 4.2.1."
    ps_installer_log = "Setup completed with 0 errors and 2 warnings."
    ps_encode_target = "admin-reset"
    ps_encode_result = b64(ps_encode_target)
    ps_changelog = "v2.3.0 — added SSO login, fixed session timeout bug, improved audit logging."

    windows_items = [
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-001",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many characters are in readme.txt?",
            "answer_key": str(len(ps_readme)),
            "hints": [
                "There's a cmdlet that measures things like character/word/line counts.",
                "Pipe the file's contents into `Measure-Object`.",
                "Run `Get-Content readme.txt | Measure-Object -Character` and read the Characters value.",
            ],
            "scenario": {"files": {"readme.txt": {"content": ps_readme, "date": "Sep 08 09:00"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-002",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "secret.b64 is Base64-encoded. Decode it — what does it say?",
            "answer_key": ps_secret_phrase,
            "hints": [
                "Read the file's contents, then reverse the Base64 encoding.",
                "This sandbox provides a cmdlet specifically for decoding Base64.",
                "Run `Get-Content secret.b64 | ConvertFrom-Base64String`.",
            ],
            "scenario": {"files": {"secret.b64": {"content": ps_secret_b64, "date": "Sep 08 09:05"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-003",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many files are in this directory?",
            "answer_key": "3",
            "hints": [
                "There's a cmdlet for listing what's in the current directory.",
                "Try `Get-ChildItem` (or its alias `dir` / `ls`).",
                "Run `Get-ChildItem` and count the rows, or use `Get-ChildItem -Name`.",
            ],
            "scenario": {"files": {
                "service.log": {"content": "health check ok", "date": "Sep 08 07:00"},
                "policy.xml": {"content": "<policy version=\"1\"/>", "date": "Sep 08 07:01"},
                "inventory.csv": {"content": "id,host\n1,web01\n2,web02", "date": "Sep 08 07:02"},
            }},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-004",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "What Length does Get-Item report for report.docx?",
            "answer_key": str(len(ps_report)),
            "hints": [
                "There's a cmdlet that reports a single file's metadata, including its size.",
                "Try `Get-Item` on report.docx.",
                "Run `Get-Item report.docx` and read the Length column.",
            ],
            "scenario": {"files": {
                "report.docx": {"content": ps_report, "date": "Sep 08 10:00"},
                "summary.txt": {"content": "See report.docx for the full write-up.", "date": "Sep 08 10:01"},
            }},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-005",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "payload.b64 is Base64-encoded. What does it say?",
            "answer_key": ps_payload_phrase,
            "hints": [
                "Same decoding approach as any other Base64 file here.",
                "Pipe its contents into the Base64-decoding cmdlet.",
                "Run `Get-Content payload.b64 | ConvertFrom-Base64String`.",
            ],
            "scenario": {"files": {"payload.b64": {"content": ps_payload_b64, "date": "Sep 08 10:10"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-006",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "According to service.log, how many failed logins are recorded?",
            "answer_key": "7",
            "hints": [
                "Read the file's contents and look for a labeled value.",
                "Use `Get-Content` to print service.log.",
                "Run `Get-Content service.log` — look for `failed_logins=`.",
            ],
            "scenario": {"files": {"service.log": {"content": ps_service_log, "date": "Sep 08 11:00"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-007",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "What's the SHA256 hash of integrity.txt (Get-FileHash)?",
            "answer_key": sha256(ps_integrity),
            "hints": [
                "There's a cmdlet for computing cryptographic hashes of a file.",
                "Try `Get-FileHash` on integrity.txt.",
                "Run `Get-FileHash integrity.txt` (SHA256 is the default) and read the Hash value.",
            ],
            "scenario": {"files": {"integrity.txt": {"content": ps_integrity, "date": "Sep 08 11:30"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-008",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Using Get-FileHash -Algorithm MD5, what's the MD5 hash of installer.log?",
            "answer_key": md5(ps_installer_log),
            "hints": [
                "Same hashing cmdlet as before, just a different algorithm.",
                "`Get-FileHash` takes an `-Algorithm` parameter.",
                "Run `Get-FileHash installer.log -Algorithm MD5`.",
            ],
            "scenario": {"files": {"installer.log": {"content": ps_installer_log, "date": "Sep 08 11:45"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-009",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": f'Encode the text "{ps_encode_target}" to Base64 using this terminal. What do you get?',
            "answer_key": ps_encode_result,
            "hints": [
                "There's a cmdlet in this sandbox that does the opposite of decoding.",
                "Try `ConvertTo-Base64String`.",
                f'Run `Write-Output "{ps_encode_target}" | ConvertTo-Base64String`.',
            ],
            "scenario": {"files": {"hint.txt": {"content": "Encoding cmdlets live in this sandbox's help.", "date": "Sep 08 12:00"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-010",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "According to changelog.txt, what version was released?",
            "answer_key": "v2.3.0",
            "hints": [
                "Read the file and look for a version-looking string.",
                "Use `Get-Content` to print changelog.txt.",
                "Run `Get-Content changelog.txt` — the version appears right at the start.",
            ],
            "scenario": {"files": {"changelog.txt": {"content": ps_changelog, "date": "Sep 08 12:15"}}},
        },
    ]

    all_items = linux_items + windows_items
    for item in all_items:
        table.put_item(Item=item)
        print(f"seeded {item['PK']} / {item['SK']}")


if __name__ == "__main__":
    main()
