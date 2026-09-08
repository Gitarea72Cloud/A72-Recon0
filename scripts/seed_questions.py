#!/usr/bin/env python3
"""Seed the Stage 0 Linux CLI item bank — 5 items for the first MVP.

This is NOT the real item bank — that's Phase 0 content work with the
Module 1 professors (~30-40 items). It's enough to prove the full path
(sign in -> 5-question test -> result) works end to end. Every item uses
only commands terminal_exec actually implements: cd, pwd, ls (-l/-la),
cat, stat/wc/du, file, echo, base64 (-d/-e), with pipes.

Usage:
    python3 scripts/seed_questions.py --table a72-recon0-dev --region eu-south-2
"""
import argparse
import base64
import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--region", default="eu-south-2")
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(args.table)

    secret_phrase = "you just automated your first placement task"
    secret_b64 = base64.b64encode(secret_phrase.encode()).decode()

    flag_phrase = "the flag is base64 all the way down"
    flag_b64 = base64.b64encode(flag_phrase.encode()).decode()

    readme_content = "Placement test sandbox. Nothing here is a real filesystem."

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
    ]

    for item in items:
        table.put_item(Item=item)
        print(f"seeded {item['PK']} / {item['SK']}")


if __name__ == "__main__":
    main()
