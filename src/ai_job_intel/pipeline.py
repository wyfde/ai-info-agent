from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .bitable import FeishuBitableSender
from .collectors import collect_sources
from .config import load_config
from .digest import EMPTY_DIGEST, DigestGenerator
from .feishu import FeishuSender
from .llm import OpenAICompatibleLLM
from .models import SourceItem


def now_in_timezone(config: dict) -> datetime:
    timezone_name = str(config.get("timezone", "Asia/Shanghai"))
    try:
        return datetime.now(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone()


def raw_path(config: dict, coverage_date: date) -> Path:
    return Path(config["raw_dir"]) / f"sources-{coverage_date.isoformat()}.json"


def digest_path(config: dict, coverage_date: date) -> Path:
    return Path(config["output_dir"]) / f"AI日报-{coverage_date.isoformat()}.md"


def save_items(config: dict, coverage_date: date, items: list[SourceItem]) -> Path:
    path = raw_path(config, coverage_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_items(config: dict, coverage_date: date) -> list[SourceItem]:
    path = raw_path(config, coverage_date)
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return [SourceItem.from_dict(item) for item in value if isinstance(item, dict)]


def collect_and_save(config_path: str, at: datetime | None = None) -> tuple[list[SourceItem], Path]:
    config = load_config(config_path)
    current = at or now_in_timezone(config)
    items = collect_sources(config, current)
    return items, save_items(config, current.date(), items)


def generate_from_saved(config_path: str, coverage_date: date | None = None) -> Path:
    config = load_config(config_path)
    target_date = coverage_date or now_in_timezone(config).date()
    items = load_items(config, target_date)
    digest = (
        DigestGenerator(OpenAICompatibleLLM(config["llm"])).generate(items, target_date)
        if items
        else EMPTY_DIGEST
    )
    path = digest_path(config, target_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(digest.rstrip() + "\n", encoding="utf-8")
    return path


def run_evening(config_path: str) -> tuple[Path, Path]:
    config = load_config(config_path)
    current = now_in_timezone(config)
    items = collect_sources(config, current)
    sources_path = save_items(config, current.date(), items)
    digest = (
        DigestGenerator(OpenAICompatibleLLM(config["llm"])).generate(items, current.date())
        if items
        else EMPTY_DIGEST
    )
    output_path = digest_path(config, current.date())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(digest.rstrip() + "\n", encoding="utf-8")
    return sources_path, output_path


def latest_previous_digest(config: dict, today: date) -> Path:
    output_dir = Path(config["output_dir"])
    candidates: list[tuple[date, Path]] = []
    for path in output_dir.glob("AI日报-*.md"):
        value = path.stem.removeprefix("AI日报-")
        try:
            candidate_date = date.fromisoformat(value)
        except ValueError:
            continue
        if candidate_date < today:
            candidates.append((candidate_date, path))
    if not candidates:
        raise FileNotFoundError(f"No previous digest found in {output_dir}")
    return max(candidates, key=lambda pair: pair[0])[1]


def run_morning(config_path: str, coverage_date: date | None = None) -> Path:
    config = load_config(config_path)
    current = now_in_timezone(config)
    target_date = coverage_date or current.date()
    path = (
        digest_path(config, target_date)
        if coverage_date
        else latest_previous_digest(config, target_date)
    )
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8").strip()
    feishu = config["feishu"]
    if str(feishu.get("delivery", "message")).lower() == "bitable":
        delivered_date = coverage_date or date.fromisoformat(path.stem.removeprefix("AI日报-"))
        bitable_config = {**feishu, **(feishu.get("bitable") or {})}
        FeishuBitableSender(bitable_config).send_digest(text, delivered_date)
    else:
        FeishuSender(feishu).send(text)
    return path


def previous_date(config_path: str) -> date:
    config = load_config(config_path)
    return (now_in_timezone(config) - timedelta(days=1)).date()
