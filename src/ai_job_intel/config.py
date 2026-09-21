from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "timezone": "Asia/Shanghai",
    "window_hours": 24,
    "inbox_dir": "data/inbox",
    "raw_dir": "data/raw",
    "output_dir": "outputs",
    "llm": {
        "api_style": "chat_completions",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "AI_JOB_INTEL_LLM_API_KEY",
        "timeout_seconds": 120,
    },
    "wechat": {"rss_feeds": []},
    "feishu": {
        "app_id_env": "FEISHU_APP_ID",
        "app_secret_env": "FEISHU_APP_SECRET",
        "group_chats": [],
        "webhook_url_env": "FEISHU_WEBHOOK_URL",
        "receive_id_env": "FEISHU_RECEIVE_ID",
        "receive_id_type": "chat_id",
    },
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        supplied = json.load(handle)
    config = _merge(DEFAULT_CONFIG, supplied)

    project_root_value = config.get("project_root")
    project_root = (
        Path(project_root_value).expanduser().resolve()
        if project_root_value
        else config_path.parent.parent
    )
    for key in ("inbox_dir", "raw_dir", "output_dir"):
        path_value = Path(str(config[key])).expanduser()
        if not path_value.is_absolute():
            path_value = project_root / path_value
        config[key] = str(path_value.resolve())

    config["project_root"] = str(project_root)
    config["config_path"] = str(config_path)
    return config


def get_secret(section: dict[str, Any], env_key: str, value_key: str = "value") -> str:
    env_name = str(section.get(env_key, "")).strip()
    direct_value = str(section.get(value_key, "")).strip()
    if env_name:
        environment_value = os.getenv(env_name, "").strip()
        if environment_value:
            return environment_value
    return direct_value
