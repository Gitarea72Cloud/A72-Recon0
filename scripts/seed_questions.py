#!/usr/bin/env python3
"""Seed a couple of real Stage 0 items so the pipeline is testable end to
end right after the first deploy. This is NOT the real item bank — that's
Phase 0 content work with the Module 1 professors (~30-40 items). It's
just enough to prove start-session -> terminal -> answer -> result works.

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

    items = [
        {
            "PK": "QUESTION#linux_cli",
            "SK": "ITEM#linux-size-001",
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
            "SK": "ITEM#linux-decode-001",
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
    ]

    for item in items:
        table.put_item(Item=item)
        print(f"seeded {item['PK']} / {item['SK']}")


if __name__ == "__main__":
    main()
