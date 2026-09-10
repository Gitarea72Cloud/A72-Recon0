#!/usr/bin/env python3
"""Seed the Stage 0 item bank.

  10 Linux CLI items      (type: terminal, domain: linux_cli)
  10 PowerShell items     (type: terminal, domain: windows_cli)
   5 Red Team concepts    (type: free-text, domain: red_team)
   5 Blue Team concepts   (type: free-text, domain: blue_team)
   5 Grey Team/ethics     (type: free-text, domain: grey_team)

This is NOT the real item bank — that's Phase 0 content work with the
Module 1 professors. Each item carries 3 progressive hints (nudge ->
names the command/concept -> near-complete answer), unlocked on demand
via get_hint and never sent to the client up front. Using a hint costs
credit on that item (see common/scoring.py's credit_for).

Terminal items use only commands the interpreters actually implement:
  Linux (terminal_exec):     cd, pwd, ls (-l/-la), cat, stat/wc/du
                              (file arg OR piped stdin), file, echo,
                              base64 (-d/-e), with pipes.
  PowerShell (powershell_exec): Get-ChildItem/gci/dir/ls, Get-Item,
                              Get-Content/cat/type/gc, Get-Location,
                              Set-Location, Measure-Object -Character,
                              ConvertFrom/ConvertTo-Base64String,
                              Get-FileHash [-Algorithm SHA256|MD5],
                              Write-Output, pipes, and the
                              (Expression).Length/.Count idiom.

Free-text items have no scenario/terminal at all -- short, unambiguous
canonical answers (a term or acronym), graded the same way as everything
else (case/whitespace-insensitive exact match).

Usage:
    python3 scripts/seed_questions.py --table a72-recon0-dev --region eu-south-2
"""
import argparse
import base64
import hashlib
import boto3


def b64(s) -> str:
    if isinstance(s, str):
        s = s.encode()
    return base64.b64encode(s).decode()


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

    # ------------------------------------------------------------------
    # Linux CLI (10) -- varied task shapes, not "decode another file"
    # repeated ten times: comparison, misleading extensions, counting,
    # permissions reasoning, decode+extract-a-field, pick-the-real-one,
    # decoy filenames, and a chained multi-stage pipe.
    # ------------------------------------------------------------------
    secret_phrase = "you just automated your first placement task"
    secret_b64 = b64(secret_phrase)

    access_log = "GET /index.html 200\nGET /login.html 200\nPOST /login 302\n" * 3
    small_note = "Reminder: rotate the API keys."

    config_phrase_raw = "host=10.0.0.5;port=2222;user=root"
    config_b64 = b64(config_phrase_raw)

    decoy_a = "Just a plain english sentence, definitely not encoded."
    decoy_c = "Another decoy sentence sitting here in this file."
    real_candidate_phrase = "the third file was the real one all along"
    real_candidate_b64 = b64(real_candidate_phrase)

    report_v1 = "Draft — pricing numbers not final yet."
    report_v2 = "Final approved report — Q3 pricing confirmed at $42 per seat."

    secret2_phrase = "measuring a decoded pipe is just another command away"
    secret2_b64 = b64(secret2_phrase)

    invoice_phrase = "this invoice is not really a pdf, it is base64 text"
    invoice_b64 = b64(invoice_phrase)

    linux_items = [
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-001",
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
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-002",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Two files are here: access.log and notes.txt. Which one is larger, in bytes?",
            "answer_key": "access.log" if len(access_log) > len(small_note) else "notes.txt",
            "hints": [
                "You'll need to check both files' sizes and compare them.",
                "`stat`, `wc`, or `du` each report a file's size.",
                "Run `stat access.log` and `stat notes.txt`, then compare the two numbers.",
            ],
            "scenario": {"files": {
                "access.log": {"content": access_log, "perms": "-rw-r--r--", "date": "Sep 08 08:00"},
                "notes.txt": {"content": small_note, "perms": "-rw-r--r--", "date": "Sep 08 08:00"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-003",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Which file does `file` report as Base64-encoded, even though its name suggests otherwise?",
            "answer_key": "photo.jpg",
            "hints": [
                "Don't trust a filename's extension — check what the content actually is.",
                "There's a command that identifies content type regardless of filename.",
                "Run `file photo.jpg` and `file readme.txt` and compare the outputs.",
            ],
            "scenario": {"files": {
                "photo.jpg": {"content": secret_b64, "perms": "-rw-r--r--", "date": "Sep 08 08:30"},
                "readme.txt": {"content": "Nothing special in here.", "perms": "-rw-r--r--", "date": "Sep 08 08:31"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-004",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many total entries does `ls -la` show in this directory (including . and ..)?",
            "answer_key": "5",
            "hints": [
                "There's a flag combination that also shows the hidden . and .. entries.",
                "Try `ls -la` instead of a plain `ls`.",
                "Run `ls -la` and count every line, including the two that start with a dot.",
            ],
            "scenario": {"files": {
                "app.log": {"content": "ok", "perms": "-rw-r--r--", "date": "Sep 01 08:00"},
                "config.yml": {"content": "env: staging", "perms": "-rw-r--r--", "date": "Sep 01 08:00"},
                "notes.md": {"content": "# TODO", "perms": "-rw-r--r--", "date": "Sep 01 08:01"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-005",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Three files are here with different permissions. Which one is NOT readable by other users (no read bit in the last group)?",
            "answer_key": "internal.txt",
            "hints": [
                "You need the long-form listing to see permission bits.",
                "The permissions string has three groups: owner, group, others. Look at the last three characters.",
                "Run `ls -l` — internal.txt's permissions end in `---`, meaning others have no access at all.",
            ],
            "scenario": {"files": {
                "public.txt": {"content": "anyone can read this", "perms": "-rw-r--r--", "date": "Sep 08 09:00"},
                "shared.txt": {"content": "team can read this", "perms": "-rw-rw-rw-", "date": "Sep 08 09:00"},
                "internal.txt": {"content": "owner only", "perms": "-rw-r-----", "date": "Sep 08 09:00"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-006",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "config.b64 is Base64-encoded and contains connection settings. What port number does it specify?",
            "answer_key": "2222",
            "hints": [
                "Decode the file first, then read the specific value you need out of it.",
                "Pipe the file's contents into the Base64 decoder, then look for `port=`.",
                "Run `cat config.b64 | base64 -d` and read the port value from the decoded text.",
            ],
            "scenario": {"files": {"config.b64": {"content": config_b64, "perms": "-rw-r--r--", "date": "Sep 08 09:30"}}},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-007",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Exactly one of these three files is actually valid Base64. Decode each one — which one works, and what does it say?",
            "answer_key": real_candidate_phrase,
            "hints": [
                "Try decoding all three — most will fail or produce garbage, only one gives real text.",
                "Use `base64 -d` on each candidate file in turn.",
                "Run `cat candidate_a.txt | base64 -d`, then candidate_b and candidate_c — only one produces a readable sentence.",
            ],
            "scenario": {"files": {
                "candidate_a.txt": {"content": decoy_a, "perms": "-rw-r--r--", "date": "Sep 08 10:00"},
                "candidate_b.b64": {"content": real_candidate_b64, "perms": "-rw-r--r--", "date": "Sep 08 10:00"},
                "candidate_c.log": {"content": decoy_c, "perms": "-rw-r--r--", "date": "Sep 08 10:01"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-008",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "There are two similarly-named report files. Read report_final_v2.txt (the current one, not the draft) — how many bytes is it?",
            "answer_key": str(len(report_v2)),
            "hints": [
                "Two files look almost identical by name — make sure you check the right one.",
                "`stat`, `wc`, or `du` report a file's size; run it against the v2 file specifically.",
                "Run `stat report_final_v2.txt` (not report_final.txt) and read the number.",
            ],
            "scenario": {"files": {
                "report_final.txt": {"content": report_v1, "perms": "-rw-r--r--", "date": "Sep 08 10:10"},
                "report_final_v2.txt": {"content": report_v2, "perms": "-rw-r--r--", "date": "Sep 08 10:20"},
            }},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-009",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Decode secret2.b64, then tell me how many characters the decoded message contains.",
            "answer_key": str(len(secret2_phrase)),
            "hints": [
                "This one takes two steps chained together: decode, then measure.",
                "`base64 -d` decodes; `wc` can measure whatever's piped into it, not just a named file.",
                "Run `cat secret2.b64 | base64 -d | wc` and read the resulting number.",
            ],
            "scenario": {"files": {"secret2.b64": {"content": secret2_b64, "perms": "-rw-r--r--", "date": "Sep 08 10:30"}}},
        },
        {
            "PK": "QUESTION#linux_cli", "SK": "ITEM#linux-010",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "invoice.pdf isn't really a PDF — it's Base64 text with a misleading name. Decode it. What does it say?",
            "answer_key": invoice_phrase,
            "hints": [
                "Ignore the .pdf extension — check what `file` actually reports, then decode accordingly.",
                "Once you know it's text, `base64 -d` reverses the encoding.",
                "Run `cat invoice.pdf | base64 -d` and read the result.",
            ],
            "scenario": {"files": {"invoice.pdf": {"content": invoice_b64, "perms": "-rw-r--r--", "date": "Sep 08 10:40"}}},
        },
    ]

    # ------------------------------------------------------------------
    # PowerShell (10) -- same variety principle: comparison, integrity
    # verification via hashing, decoy/misleading names, decode+extract,
    # pick-the-real-one, and a chained pipe.
    # ------------------------------------------------------------------
    ps_secret_phrase = "welcome to the powershell placement track"
    ps_secret_b64 = b64(ps_secret_phrase)

    ps_report_a = "Short memo."
    ps_report_b = "This is a considerably longer status report with more detail in it."

    ps_backup_1 = "Backup snapshot A — checksum baseline."
    ps_backup_2 = "Backup snapshot A — checksum baseline!"  # one character different, on purpose

    ps_config_raw = "env=production;region=eu-south-2;replicas=4"
    ps_config_b64 = b64(ps_config_raw)

    ps_decoy_a = "This file just holds a short unencoded status line."
    ps_decoy_c = "Another plain status update, nothing encoded here."
    ps_real_phrase = "candidate two was the one that actually decoded"
    ps_real_b64 = b64(ps_real_phrase)

    ps_scan_txt = "Scan queued for host 10.0.0.9, priority normal."
    ps_scan_exe = "AppInstaller v4 — not really, this is text disguised as an installer."

    ps_secret2_phrase = "chaining cmdlets together is the whole point of the pipe"
    ps_secret2_b64 = b64(ps_secret2_phrase)

    windows_items = [
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-001",
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
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-002",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "report_a.txt and report_b.txt are here. Which one has the greater Length?",
            "answer_key": "report_b.txt" if len(ps_report_b) > len(ps_report_a) else "report_a.txt",
            "hints": [
                "There's a cmdlet that reports one file's metadata, including its size.",
                "Try `Get-Item` on each file and compare the Length column.",
                "Run `Get-Item report_a.txt` and `Get-Item report_b.txt`, then compare the two Length values.",
            ],
            "scenario": {"files": {
                "report_a.txt": {"content": ps_report_a, "date": "Sep 08 10:00"},
                "report_b.txt": {"content": ps_report_b, "date": "Sep 08 10:00"},
            }},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-003",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "backup_1.txt and backup_2.txt are both supposed to be identical copies. Using Get-FileHash, are they actually identical? Answer yes or no.",
            "answer_key": "no" if ps_backup_1 != ps_backup_2 else "yes",
            "hints": [
                "Don't just eyeball the content — verify it properly.",
                "There's a cmdlet for computing a cryptographic hash of a file's contents.",
                "Run `Get-FileHash backup_1.txt` and `Get-FileHash backup_2.txt` — compare the Hash values, not just the text.",
            ],
            "scenario": {"files": {
                "backup_1.txt": {"content": ps_backup_1, "date": "Sep 08 10:10"},
                "backup_2.txt": {"content": ps_backup_2, "date": "Sep 08 10:10"},
            }},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-004",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "config.b64 is Base64-encoded and holds deployment settings. How many replicas does it specify?",
            "answer_key": "4",
            "hints": [
                "Decode the file first, then read out the specific value you need.",
                "Pipe the file's contents into the Base64-decoding cmdlet, then look for `replicas=`.",
                "Run `Get-Content config.b64 | ConvertFrom-Base64String` and read the replicas value.",
            ],
            "scenario": {"files": {"config.b64": {"content": ps_config_b64, "date": "Sep 08 10:20"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-005",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Exactly one of these three files is actually valid Base64. Decode each one — which works, and what does it say?",
            "answer_key": ps_real_phrase,
            "hints": [
                "Try decoding all three — most will fail or produce garbage, only one gives real text.",
                "Pipe each candidate's contents into the Base64-decoding cmdlet.",
                "Run `Get-Content candidate_a.txt | ConvertFrom-Base64String`, then b and c — only one gives a readable sentence.",
            ],
            "scenario": {"files": {
                "candidate_a.txt": {"content": ps_decoy_a, "date": "Sep 08 10:30"},
                "candidate_b.b64": {"content": ps_real_b64, "date": "Sep 08 10:30"},
                "candidate_c.log": {"content": ps_decoy_c, "date": "Sep 08 10:31"},
            }},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-006",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "installer_v4.exe isn't really an executable — it's plain text with a misleading name. Read it. What does it say?",
            "answer_key": ps_scan_exe,
            "hints": [
                "Ignore the .exe extension — this sandbox has no real executables, only text and Base64.",
                "There's a cmdlet that just prints a file's raw contents.",
                "Run `Get-Content installer_v4.exe` and read the output.",
            ],
            "scenario": {"files": {
                "installer_v4.exe": {"content": ps_scan_exe, "date": "Sep 08 10:40"},
                "scan_notes.txt": {"content": ps_scan_txt, "date": "Sep 08 10:41"},
            }},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-007",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Decode secret2.b64, then tell me how many characters the decoded message contains.",
            "answer_key": str(len(ps_secret2_phrase)),
            "hints": [
                "This one chains two steps: decode, then measure.",
                "Pipe the decoded output into `Measure-Object -Character`.",
                "Run `Get-Content secret2.b64 | ConvertFrom-Base64String | Measure-Object -Character`.",
            ],
            "scenario": {"files": {"secret2.b64": {"content": ps_secret2_b64, "date": "Sep 08 10:50"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-008",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Using Get-FileHash -Algorithm MD5 vs the default algorithm on the same file, which hash is longer: the SHA256 hex string or the MD5 hex string?",
            "answer_key": "sha256",
            "hints": [
                "You don't need a file for this one — think about what each algorithm actually produces.",
                "SHA256 produces a 256-bit digest, MD5 a 128-bit digest — in hex, that's twice the characters for one of them.",
                "SHA256 in hex is 64 characters; MD5 in hex is 32 characters. SHA256 is the longer one.",
            ],
            "scenario": {"files": {"integrity.txt": {"content": "Any file works for this one.", "date": "Sep 08 11:00"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-009",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": 'Encode the text "unlock-me" to Base64 using this terminal. What do you get?',
            "answer_key": b64("unlock-me"),
            "hints": [
                "There's a cmdlet in this sandbox that does the opposite of decoding.",
                "Try `ConvertTo-Base64String`.",
                'Run `Write-Output "unlock-me" | ConvertTo-Base64String`.',
            ],
            "scenario": {"files": {}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-010",
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
    ]

    # ------------------------------------------------------------------
    # Security concepts (5 + 5 + 5) -- free-text, no terminal.
    #
    # Pitched at someone INITIATING in security, not someone already in
    # the field: general tech/security literacy a curious beginner could
    # plausibly know or reason out, not specialist jargon a placement
    # test shouldn't assume (SIEM, OSINT, threat hunting, rules of
    # engagement, grey hat, responsible disclosure, etc. are things the
    # curriculum itself teaches -- testing for them here would penalize
    # genuine beginners, not measure CLI/reasoning readiness).
    #
    # answer_key can be a string or a list of acceptable synonyms --
    # free-text concept answers are inherently more ambiguous than a
    # terminal's deterministic output, so a few of these accept more
    # than one common phrasing.
    # ------------------------------------------------------------------
    red_team_items = [
        {
            "PK": "QUESTION#red_team", "SK": "ITEM#red-001",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the common term for a fake email or message pretending to be from someone trustworthy, trying to trick you into clicking a bad link or giving up a password?",
            "answer_key": "phishing",
            "hints": ["It's named after a real-world activity involving bait.", "You've probably seen a warning about this in your own inbox.", "The answer is \"phishing\"."],
        },
        {
            "PK": "QUESTION#red_team", "SK": "ITEM#red-002",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the general term for malicious software — things like viruses, worms, and trojans all fall under this one word?",
            "answer_key": "malware",
            "hints": ["It's a blend of two words: \"malicious\" and \"software\".", "It's the umbrella term that viruses and trojans are both types of.", "The answer is \"malware\"."],
        },
        {
            "PK": "QUESTION#red_team", "SK": "ITEM#red-003",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the term for malicious software that locks or encrypts your files and demands payment to get them back?",
            "answer_key": "ransomware",
            "hints": ["Think about what the attacker is demanding.", "It's named directly after what it holds — for a payment.", "The answer is \"ransomware\"."],
        },
        {
            "PK": "QUESTION#red_team", "SK": "ITEM#red-004",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the term for trying every possible password combination until one of them works?",
            "answer_key": ["brute force", "brute-force"],
            "hints": ["It's not clever or targeted — it's pure repetition.", "The name describes using raw force rather than a shortcut.", "The answer is \"brute force\"."],
        },
        {
            "PK": "QUESTION#red_team", "SK": "ITEM#red-005",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "When a company legally hires someone to try to break into their own systems to find weaknesses before real attackers do, what's that activity generally called?",
            "answer_key": ["penetration testing", "pen testing", "pentesting"],
            "hints": ["It's abbreviated \"pen test\" for short.", "The tester is probing (\"penetrating\") the defenses on purpose, with permission.", "The answer is \"penetration testing\" (pen testing)."],
        },
    ]
    blue_team_items = [
        {
            "PK": "QUESTION#blue_team", "SK": "ITEM#blue-001",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the common term for software that detects and blocks malicious programs on a computer?",
            "answer_key": ["antivirus", "anti-virus"],
            "hints": ["It's software most people have installed without thinking much about it.", "It's named directly after the threat it fights.", "The answer is \"antivirus\"."],
        },
        {
            "PK": "QUESTION#blue_team", "SK": "ITEM#blue-002",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the term for a security barrier that controls what network traffic is allowed in or out?",
            "answer_key": "firewall",
            "hints": ["Think of it as a protective wall between trusted and untrusted networks.", "The name literally describes a wall that stops fire (threats) from spreading.", "The answer is \"firewall\"."],
        },
        {
            "PK": "QUESTION#blue_team", "SK": "ITEM#blue-003",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the practice called where you regularly copy your data somewhere safe so you can recover it if something goes wrong?",
            "answer_key": ["backup", "backups", "backing up"],
            "hints": ["It's something you should be doing with your own photos and documents too.", "Ransomware attacks are a lot less scary if you have a recent one of these.", "The answer is \"backup\"."],
        },
        {
            "PK": "QUESTION#blue_team", "SK": "ITEM#blue-004",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's it called when logging in requires a second form of verification (like a code sent to your phone) in addition to your password?",
            "answer_key": ["two-factor authentication", "2fa", "multi-factor authentication", "mfa"],
            "hints": ["Most banking and email apps make you set this up now.", "It's often shortened to an acronym starting with \"2\" or \"M\".", "The answer is \"two-factor authentication\" (2FA) / \"multi-factor authentication\" (MFA)."],
        },
        {
            "PK": "QUESTION#blue_team", "SK": "ITEM#blue-005",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the term for keeping software updated with the latest fixes for known security issues?",
            "answer_key": ["patching", "patch", "patches", "updating"],
            "hints": ["It's the reason your phone or laptop nags you to install updates.", "Security researchers find a hole, the vendor releases a fix, and you apply it — that action is called this.", "The answer is \"patching\"."],
        },
    ]
    grey_team_items = [
        {
            "PK": "QUESTION#grey_team", "SK": "ITEM#grey-001",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "Is it legal to access someone else's computer system without their permission, even if you're \"just looking around\" and don't cause any damage?",
            "answer_key": "no",
            "hints": ["Think about whether good intentions change the legal answer.", "Permission is what makes access to a system lawful, not your intent.", "The answer is \"no\"."],
        },
        {
            "PK": "QUESTION#grey_team", "SK": "ITEM#grey-002",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What word describes hacking skills used for good, protective purposes (with permission) rather than for harm?",
            "answer_key": ["ethical", "ethical hacking"],
            "hints": ["It's the same word used to describe morally right behavior in general.", "\"___ hacking\" is a widely used job title/skill area.", "The answer is \"ethical\" (as in \"ethical hacking\")."],
        },
        {
            "PK": "QUESTION#grey_team", "SK": "ITEM#grey-003",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's it called when a company invites the public to find and report security bugs in exchange for a cash reward?",
            "answer_key": "bug bounty",
            "hints": ["Companies like Google and Meta run these publicly.", "It's named after a reward for finding something specific.", "The answer is \"bug bounty\"."],
        },
        {
            "PK": "QUESTION#grey_team", "SK": "ITEM#grey-004",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "True or false: it's okay to test a company's security without asking first, as long as you don't cause any damage.",
            "answer_key": "false",
            "hints": ["Think back to the earlier question about accessing systems without permission.", "Good intentions and no damage still don't make it authorized.", "The answer is \"false\"."],
        },
        {
            "PK": "QUESTION#grey_team", "SK": "ITEM#grey-005",
            "checkpoint": "placement", "stage": "stage0", "type": "free-text",
            "prompt": "What's the single most important thing you need before testing any system's security, even with good intentions?",
            "answer_key": ["permission", "authorization"],
            "hints": ["It's not about skill level.", "It's what turns \"hacking\" into \"authorized testing\".", "The answer is \"permission\" (authorization)."],
        },
    ]

    all_items = linux_items + windows_items + red_team_items + blue_team_items + grey_team_items
    for item in all_items:
        table.put_item(Item=item)
        print(f"seeded {item['PK']} / {item['SK']}")


if __name__ == "__main__":
    main()
