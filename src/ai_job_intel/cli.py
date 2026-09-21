from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .bitable import FeishuBitableSender
from .config import load_config
from .feishu import list_chats
from .llm import OpenAICompatibleLLM
from .pipeline import (
    collect_and_save,
    generate_from_saved,
    run_evening,
    run_morning,
)


DEFAULT_CONFIG = "config/config.json"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-job-intel")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("collect", help="Collect source items and save the raw JSON.")

    generate_parser = subparsers.add_parser("generate", help="Generate a digest from saved sources.")
    generate_parser.add_argument("--date", type=_date)

    send_parser = subparsers.add_parser("send", help="Send a digest to Feishu.")
    send_parser.add_argument("--date", type=_date)

    subparsers.add_parser("run-evening", help="Collect sources and generate today's digest.")
    subparsers.add_parser("run-morning", help="Send the latest previous digest to Feishu.")
    subparsers.add_parser("list-feishu-chats", help="List Feishu groups containing the bot.")
    subparsers.add_parser("check-llm", help="Test the configured LLM API connection.")
    subparsers.add_parser("check-bitable", help="List fields in the configured Bitable.")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    config_path = str(Path(args.config).expanduser().resolve())

    if args.command == "collect":
        items, path = collect_and_save(config_path)
        print(f"Collected {len(items)} items: {path}")
        return 0
    if args.command == "generate":
        path = generate_from_saved(config_path, args.date)
        print(path)
        return 0
    if args.command == "send":
        path = run_morning(config_path, args.date)
        print(f"Sent: {path}")
        return 0
    if args.command == "run-evening":
        sources_path, output_path = run_evening(config_path)
        print(f"Sources: {sources_path}")
        print(f"Digest: {output_path}")
        return 0
    if args.command == "run-morning":
        path = run_morning(config_path)
        print(f"Sent: {path}")
        return 0
    if args.command == "list-feishu-chats":
        config = load_config(config_path)
        chats = list_chats(config["feishu"])
        print(json.dumps(chats, ensure_ascii=False, indent=2))
        return 0
    if args.command == "check-llm":
        config = load_config(config_path)
        llm = OpenAICompatibleLLM(config["llm"])
        response = llm.complete(
            "这是一次连接测试。",
            "只回复四个字：连接成功",
        )
        print(response)
        return 0
    if args.command == "check-bitable":
        config = load_config(config_path)
        feishu = config["feishu"]
        bitable_config = {**feishu, **(feishu.get("bitable") or {})}
        fields = FeishuBitableSender(bitable_config).list_fields()
        print(
            json.dumps(
                [
                    {
                        "field_id": field.get("field_id"),
                        "field_name": field.get("field_name"),
                        "type": field.get("type"),
                    }
                    for field in fields
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    raise AssertionError(args.command)
