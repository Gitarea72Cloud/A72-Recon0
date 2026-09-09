#!/usr/bin/env python3
"""Seed the Stage 0 item bank — 15 Linux CLI items + 15 PowerShell items.

This is NOT the real item bank — that's Phase 0 content work with the
Module 1 professors (~30-40 items). It's enough to give real variety
across attempts instead of the same handful of questions every time.

Linux items use only commands terminal_exec implements: cd, pwd, ls
(-l/-la), cat, stat/wc/du, file, echo, base64 (-d/-e), with pipes.

PowerShell items use only cmdlets powershell_exec implements:
Get-ChildItem/gci/dir/ls, Get-Item, Get-Content/cat/type/gc,
Get-Location/pwd, Set-Location/cd, Measure-Object -Character,
ConvertFrom-Base64String, ConvertTo-Base64String, Get-FileHash
[-Algorithm SHA256|MD5], Write-Output/echo, with pipes.

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

    ctf_flag = "FLAG{terminal_recon_complete}"
    ctf_flag_b64 = b64(ctf_flag)

    encode_target = "unlock-me"
    encode_result = b64(encode_target)

    audit_content = "id,user,action\n1,alice,login\n2,bob,logout\n3,alice,logout"
    cert_content = "-----BEGIN CERTIFICATE-----\nMIIBmock1234567890EXAMPLE\n-----END CERTIFICATE-----"

    items = [
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-001",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "What is the size, in bytes, of secret.b64?",
            "answer_key": str(len(secret_b64)),
            "scenario": {
                "files": {
                    "notes.txt": {
                        "content": "Reminder: rotate the API keys before Friday.",
                        "perms": "-rw-r--r--",
                        "date": "Oct 20 09:14",
                    },
                    "secret.b64": {
                        "content": secret_b64,
                        "perms": "-rw-r--r--",
                        "date": "Oct 20 09:15",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-002",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "secret.b64 is Base64-encoded. What does it say?",
            "answer_key": secret_phrase,
            "scenario": {
                "files": {
                    "secret.b64": {
                        "content": secret_b64,
                        "perms": "-rw-r--r--",
                        "date": "Oct 20 09:15",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-003",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "Two files are here. Which one does `file` report as Base64-encoded?",
            "answer_key": "payload.b64",
            "scenario": {
                "files": {
                    "report.txt": {
                        "content": "Quarterly access review — no findings.",
                        "perms": "-rw-r--r--",
                        "date": "Oct 19 14:02",
                    },
                    "payload.b64": {
                        "content": flag_b64,
                        "perms": "-rw-r--r--",
                        "date": "Oct 19 14:03",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-004",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "How many bytes is readme.txt?",
            "answer_key": str(len(readme_content)),
            "scenario": {
                "files": {
                    "readme.txt": {
                        "content": readme_content,
                        "perms": "-rw-r--r--",
                        "date": "Oct 18 10:30",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-005",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "payload.b64 is Base64-encoded. What's the flag inside it?",
            "answer_key": flag_phrase,
            "scenario": {
                "files": {
                    "payload.b64": {
                        "content": flag_b64,
                        "perms": "-rw-r--r--",
                        "date": "Oct 19 14:03",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-006",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "How many files are in this directory?",
            "answer_key": "3",
            "scenario": {
                "files": {
                    "app.log": {"content": "server started ok", "perms": "-rw-r--r--", "date": "Sep 01 08:00"},
                    "config.yml": {"content": "env: staging", "perms": "-rw-r--r--", "date": "Sep 01 08:00"},
                    "notes.md": {"content": "# TODO\n- rotate creds", "perms": "-rw-r--r--", "date": "Sep 01 08:01"},
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-007",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "What permissions does `ls -l` show for deploy_key.pem?",
            "answer_key": "-r--------",
            "scenario": {
                "files": {
                    "deploy_key.pem": {
                        "content": "-----BEGIN PRIVATE KEY-----\nMOCKKEYDATA\n-----END PRIVATE KEY-----",
                        "perms": "-r--------",
                        "date": "Aug 30 11:12",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-008",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "According to incident.log, what's the ticket number?",
            "answer_key": "INC-4471",
            "scenario": {
                "files": {
                    "incident.log": {
                        "content": "2026-09-01 03:14 ALERT ticket=INC-4471 status=open",
                        "perms": "-rw-r--r--",
                        "date": "Sep 01 03:14",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-009",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "Three files are here. Which one does `file` report as Base64-encoded?",
            "answer_key": "keys.b64",
            "scenario": {
                "files": {
                    "manifest.txt": {"content": "v1.4.0 release manifest", "perms": "-rw-r--r--", "date": "Sep 02 09:00"},
                    "keys.b64": {"content": vault_b64, "perms": "-rw-r--r--", "date": "Sep 02 09:01"},
                    "readme2.txt": {"content": "See manifest.txt for details.", "perms": "-rw-r--r--", "date": "Sep 02 09:02"},
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-010",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "vault.b64 is Base64-encoded. What's inside it?",
            "answer_key": vault_phrase,
            "scenario": {
                "files": {
                    "vault.b64": {"content": vault_b64, "perms": "-rw-r--r--", "date": "Sep 02 09:01"},
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-011",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "How many bytes is audit.csv?",
            "answer_key": str(len(audit_content)),
            "scenario": {
                "files": {
                    "audit.csv": {"content": audit_content, "perms": "-rw-r--r--", "date": "Sep 03 16:20"},
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-012",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": f'Encode the text "{encode_target}" to Base64 using this terminal. What do you get?',
            "answer_key": encode_result,
            "scenario": {
                "files": {
                    "hint.txt": {
                        "content": 'Try: echo "' + encode_target + '" | base64 -e',
                        "perms": "-rw-r--r--",
                        "date": "Sep 04 10:00",
                    },
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-013",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "ctf_flag.b64 is Base64-encoded. What's the flag?",
            "answer_key": ctf_flag,
            "scenario": {
                "files": {
                    "ctf_flag.b64": {"content": ctf_flag_b64, "perms": "-rw-r--r--", "date": "Sep 05 12:00"},
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-014",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "What is the size, in bytes, of server.cert?",
            "answer_key": str(len(cert_content)),
            "scenario": {
                "files": {
                    "server.cert": {"content": cert_content, "perms": "-rw-r--r--", "date": "Sep 06 08:45"},
                }
            },
        },
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-015",
            "checkpoint": "placement",
            "stage": "stage0",
            "type": "terminal",
            "prompt": "Based on `file`, how many of these files are Base64-encoded?",
            "answer_key": "2",
            "scenario": {
                "files": {
                    "a.b64": {"content": b64("part one"), "perms": "-rw-r--r--", "date": "Sep 07 09:00"},
                    "b.b64": {"content": b64("part two"), "perms": "-rw-r--r--", "date": "Sep 07 09:00"},
                    "c.txt": {"content": "just plain text here", "perms": "-rw-r--r--", "date": "Sep 07 09:01"},
                    "d.log": {"content": "nothing interesting", "perms": "-rw-r--r--", "date": "Sep 07 09:01"},
                }
            },
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
    ps_flag_phrase = "FLAG{gci_and_gc_are_your_friends}"
    ps_flag_b64 = b64(ps_flag_phrase)
    ps_audit_trail = ("Audit trail: 14 configuration changes logged between 2026-08-01 "
                       "and 2026-09-01, all approved by change management.")
    ps_invoice = "Invoice #4471 — net 30 terms, due 2026-10-08."
    ps_vendor_exe = "MZ-mock-binary-placeholder-content-for-hash-exercise"
    ps_final_flag = "FLAG{powershell_convertfrom_base64string}"

    windows_items = [
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-001",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many characters are in readme.txt?",
            "answer_key": str(len(ps_readme)),
            "scenario": {"files": {"readme.txt": {"content": ps_readme, "date": "Sep 08 09:00"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-002",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "secret.b64 is Base64-encoded. Decode it — what does it say?",
            "answer_key": ps_secret_phrase,
            "scenario": {"files": {"secret.b64": {"content": ps_secret_b64, "date": "Sep 08 09:05"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-003",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many files are in this directory?",
            "answer_key": "3",
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
            "scenario": {"files": {"payload.b64": {"content": ps_payload_b64, "date": "Sep 08 10:10"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-006",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "According to service.log, how many failed logins are recorded?",
            "answer_key": "7",
            "scenario": {"files": {"service.log": {"content": ps_service_log, "date": "Sep 08 11:00"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-007",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "What's the SHA256 hash of integrity.txt (Get-FileHash)?",
            "answer_key": sha256(ps_integrity),
            "scenario": {"files": {"integrity.txt": {"content": ps_integrity, "date": "Sep 08 11:30"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-008",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "Using Get-FileHash -Algorithm MD5, what's the MD5 hash of installer.log?",
            "answer_key": md5(ps_installer_log),
            "scenario": {"files": {"installer.log": {"content": ps_installer_log, "date": "Sep 08 11:45"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-009",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": f'Encode the text "{ps_encode_target}" to Base64 using this terminal. What do you get?',
            "answer_key": ps_encode_result,
            "scenario": {"files": {"hint.txt": {
                "content": f'Try: Write-Output "{ps_encode_target}" | ConvertTo-Base64String',
                "date": "Sep 08 12:00",
            }}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-010",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "According to changelog.txt, what version was released?",
            "answer_key": "v2.3.0",
            "scenario": {"files": {"changelog.txt": {"content": ps_changelog, "date": "Sep 08 12:15"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-011",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "flag.b64 is Base64-encoded. What's the flag?",
            "answer_key": ps_flag_phrase,
            "scenario": {"files": {"flag.b64": {"content": ps_flag_b64, "date": "Sep 08 12:30"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-012",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "How many characters are in audit_trail.txt?",
            "answer_key": str(len(ps_audit_trail)),
            "scenario": {"files": {"audit_trail.txt": {"content": ps_audit_trail, "date": "Sep 08 13:00"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-013",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "What Length does Get-Item report for invoice.pdf?",
            "answer_key": str(len(ps_invoice)),
            "scenario": {"files": {
                "invoice.pdf": {"content": ps_invoice, "date": "Sep 08 13:15"},
                "invoice_draft.pdf": {"content": "DRAFT — do not send.", "date": "Sep 08 13:10"},
                "notes.txt": {"content": "Follow up with finance.", "date": "Sep 08 13:16"},
            }},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-014",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "What's the SHA256 hash of vendor_installer.exe (Get-FileHash, default algorithm)?",
            "answer_key": sha256(ps_vendor_exe),
            "scenario": {"files": {"vendor_installer.exe": {"content": ps_vendor_exe, "date": "Sep 08 13:45"}}},
        },
        {
            "PK": "QUESTION#windows_cli", "SK": "ITEM#windows-015",
            "checkpoint": "placement", "stage": "stage0", "type": "terminal",
            "prompt": "final_flag.b64 is Base64-encoded. What's the flag?",
            "answer_key": ps_final_flag,
            "scenario": {"files": {"final_flag.b64": {"content": b64(ps_final_flag), "date": "Sep 08 14:00"}}},
        },
    ]

    all_items = items + windows_items
    for item in all_items:
        table.put_item(Item=item)
        print(f"seeded {item['PK']} / {item['SK']}")


if __name__ == "__main__":
    main()
