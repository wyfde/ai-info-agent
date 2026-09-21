from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import get_secret


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            **({"Content-Type": "application/json; charset=utf-8"} if body is not None else {}),
            **(headers or {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Feishu request failed with HTTP {exc.code}: {details}") from exc


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    return _request_json(url, method="POST", payload=payload, headers=headers)


def _tenant_token(config: dict[str, Any]) -> str:
    app_id = get_secret(config, "app_id_env", "app_id")
    app_secret = get_secret(config, "app_secret_env", "app_secret")
    if not app_id or not app_secret:
        raise ValueError("Set FEISHU_APP_ID and FEISHU_APP_SECRET first.")
    response = _post_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if response.get("code") != 0 or not response.get("tenant_access_token"):
        raise RuntimeError(f"Feishu token failed: {response}")
    return str(response["tenant_access_token"])


def list_chats(config: dict[str, Any]) -> list[dict[str, str]]:
    token = _tenant_token(config)
    chats: list[dict[str, str]] = []
    page_token = ""
    while True:
        query = {"page_size": "100"}
        if page_token:
            query["page_token"] = page_token
        response = _request_json(
            "https://open.feishu.cn/open-apis/im/v1/chats?"
            + urllib.parse.urlencode(query),
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.get("code") != 0:
            raise RuntimeError(f"Feishu chat list failed: {response}")
        data = response.get("data") or {}
        for chat in data.get("items") or []:
            chats.append(
                {
                    "chat_id": str(chat.get("chat_id", "")),
                    "name": str(chat.get("name", "")),
                    "description": str(chat.get("description", "")),
                }
            )
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token", ""))
        if not page_token:
            break
    return chats


class FeishuSender:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def send(self, text: str) -> str:
        webhook = get_secret(self.config, "webhook_url_env", "webhook_url")
        if webhook:
            response = _post_json(webhook, {"msg_type": "text", "content": {"text": text}})
            if response.get("code", response.get("StatusCode", 0)) not in (0, None):
                raise RuntimeError(f"Feishu webhook failed: {response}")
            return "webhook"

        receive_id = get_secret(self.config, "receive_id_env", "receive_id")
        receive_id_type = str(self.config.get("receive_id_type", "chat_id"))
        if not receive_id:
            raise ValueError(
                "Feishu delivery is not configured. Set FEISHU_WEBHOOK_URL, or set "
                "FEISHU_APP_ID, FEISHU_APP_SECRET and FEISHU_RECEIVE_ID."
            )

        token = _tenant_token(self.config)
        response = _post_json(
            "https://open.feishu.cn/open-apis/im/v1/messages"
            f"?receive_id_type={urllib.parse.quote(receive_id_type)}",
            {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            {"Authorization": f"Bearer {token}"},
        )
        if response.get("code") != 0:
            raise RuntimeError(f"Feishu message failed: {response}")
        return "app"
