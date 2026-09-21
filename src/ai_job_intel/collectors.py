from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

from .config import get_secret
from .models import SourceItem


USER_AGENT = "AI-Job-Intel-Agent/0.1"
URL_PATTERN = re.compile(r"https?://[^\s<>\"')]+")


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Feishu request failed with HTTP {exc.code}: {details}") from exc


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.isdigit():
        numeric = int(cleaned)
        if numeric > 10_000_000_000:
            numeric //= 1000
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(cleaned)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _in_window(item: SourceItem, since: datetime, now: datetime) -> bool:
    parsed = _parse_datetime(item.published_at)
    return parsed is None or since <= parsed <= now


def _clean_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _first_url(value: str) -> str:
    match = URL_PATTERN.search(value)
    return match.group(0).rstrip(".,;，。；") if match else ""


def _json_items(value: Any, fallback_source: str) -> list[SourceItem]:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        value = value["items"]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []

    items: list[SourceItem] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("name") or "").strip()
        content = str(
            raw.get("content") or raw.get("text") or raw.get("summary") or raw.get("description") or ""
        ).strip()
        if not title and content:
            title = content.splitlines()[0][:80]
        if not title and not content:
            continue
        items.append(
            SourceItem(
                id=str(raw.get("id") or f"{fallback_source}:{index}"),
                title=title,
                source=str(raw.get("source") or fallback_source),
                url=str(raw.get("url") or raw.get("link") or "").strip(),
                published_at=str(
                    raw.get("published_at") or raw.get("published") or raw.get("date") or ""
                ).strip(),
                content=content,
            )
        )
    return items


class LocalInboxCollector:
    def __init__(self, inbox_dir: str):
        self.inbox_dir = Path(inbox_dir)

    def collect(self, since: datetime, now: datetime) -> list[SourceItem]:
        if not self.inbox_dir.exists():
            return []

        items: list[SourceItem] = []
        for path in sorted(self.inbox_dir.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified < since:
                continue

            if path.suffix.lower() == ".json":
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                items.extend(_json_items(value, f"inbox:{path.name}"))
                continue

            if path.suffix.lower() not in {".txt", ".md"}:
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            title = re.sub(r"^#+\s*", "", lines[0])[:120]
            items.append(
                SourceItem(
                    id=f"inbox:{path.name}",
                    title=title,
                    source=f"inbox:{path.name}",
                    published_at=modified.isoformat(),
                    content=text,
                )
            )
        return items


class RssCollector:
    def __init__(self, feeds: Iterable[str], timeout: int = 60):
        self.feeds = [feed.strip() for feed in feeds if feed.strip()]
        self.timeout = timeout

    def collect(self, since: datetime, now: datetime) -> list[SourceItem]:
        items: list[SourceItem] = []
        for feed_url in self.feeds:
            try:
                request = urllib.request.Request(
                    feed_url,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml"},
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    root = ET.fromstring(response.read())
            except (OSError, ET.ParseError):
                continue
            items.extend(self._parse_feed(root, feed_url, since, now))
        return items

    @staticmethod
    def _parse_feed(
        root: ET.Element, feed_url: str, since: datetime, now: datetime
    ) -> list[SourceItem]:
        entries = root.findall(".//item")
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        items: list[SourceItem] = []
        for index, entry in enumerate(entries):
            title = _first_text(entry, ["title", "{http://www.w3.org/2005/Atom}title"])
            link = _first_text(entry, ["link", "{http://www.w3.org/2005/Atom}link"])
            if not link:
                atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
                if atom_link is not None:
                    link = atom_link.attrib.get("href", "")
            published = _first_text(
                entry,
                [
                    "pubDate",
                    "published",
                    "updated",
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                ],
            )
            content = _first_text(
                entry,
                [
                    "description",
                    "summary",
                    "content",
                    "{http://www.w3.org/2005/Atom}summary",
                    "{http://www.w3.org/2005/Atom}content",
                ],
            )
            title = _clean_text(title)
            content = _clean_text(content)
            if not title and content:
                title = content[:80]
            if not title:
                continue
            identifier = link or f"{feed_url}#{index}"
            item = SourceItem(
                id=f"rss:{identifier}",
                title=title,
                source=feed_url,
                url=link,
                published_at=published,
                content=content,
            )
            if _in_window(item, since, now):
                items.append(item)
        return items


def _first_text(element: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _render_feishu_content(message_type: str, raw_content: str) -> str:
    try:
        content = json.loads(raw_content)
    except json.JSONDecodeError:
        return _clean_text(raw_content)
    if message_type == "text":
        return str(content.get("text", "")).strip()
    if message_type == "system":
        return ""
    if message_type == "video_chat":
        return str(content.get("topic", "")).strip()

    fragments: list[str] = []

    def walk(value: Any, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"text", "content", "title", "summary", "description"} and isinstance(child, str):
                    fragments.append(child)
                elif key in {"url", "href"} and isinstance(child, str) and child.startswith("http"):
                    fragments.append(child)
                else:
                    walk(child, key)
        elif isinstance(value, list):
            for child in value:
                walk(child, parent_key)
        elif isinstance(value, str) and parent_key in {"title", "text", "content"}:
            fragments.append(value)

    walk(content)
    unique_fragments = list(dict.fromkeys(fragment.strip() for fragment in fragments if fragment.strip()))
    return " ".join(unique_fragments).strip()


class FeishuGroupCollector:
    def __init__(self, config: dict[str, Any], timeout: int = 60):
        self.config = config
        self.timeout = timeout

    def collect(self, since: datetime, now: datetime) -> list[SourceItem]:
        chats = self.config.get("group_chats") or []
        app_id = get_secret(self.config, "app_id_env", "app_id")
        app_secret = get_secret(self.config, "app_secret_env", "app_secret")
        if not chats or not app_id or not app_secret:
            return []

        token = self._tenant_token(app_id, app_secret)
        items: list[SourceItem] = []
        for chat in chats:
            chat_id = str(chat.get("chat_id", "")).strip()
            chat_name = str(chat.get("name") or chat_id).strip()
            if not chat_id:
                continue
            items.extend(self._chat_messages(chat_id, chat_name, token, since, now))
        return items

    def _tenant_token(self, app_id: str, app_secret: str) -> str:
        response = _request_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            payload={"app_id": app_id, "app_secret": app_secret},
            timeout=self.timeout,
        )
        if response.get("code") != 0 or not response.get("tenant_access_token"):
            raise RuntimeError(f"Failed to obtain Feishu tenant token: {response.get('msg', 'unknown error')}")
        return str(response["tenant_access_token"])

    def _chat_messages(
        self,
        chat_id: str,
        chat_name: str,
        token: str,
        since: datetime,
        now: datetime,
    ) -> list[SourceItem]:
        query = urllib.parse.urlencode(
            {
                "container_id_type": "chat",
                "container_id": chat_id,
                "start_time": int(since.timestamp()),
                "end_time": int(now.timestamp()),
                "sort_type": "ByCreateTimeAsc",
                "page_size": 50,
            }
        )
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?{query}"
        response = _request_json(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if response.get("code") != 0:
            raise RuntimeError(f"Failed to read Feishu group {chat_name}: {response.get('msg', 'unknown error')}")

        items: list[SourceItem] = []
        for message in response.get("data", {}).get("items", []):
            message_type = str(message.get("msg_type", ""))
            body = message.get("body") or {}
            text = _render_feishu_content(message_type, str(body.get("content", "")))
            if not text:
                continue
            first_line = next((line.strip() for line in text.splitlines() if line.strip()), text)
            items.append(
                SourceItem(
                    id=f"feishu:{message.get('message_id', '')}",
                    title=first_line[:120],
                    source=f"feishu:{chat_name}",
                    url=_first_url(text),
                    published_at=str(message.get("create_time", "")),
                    content=text,
                )
            )
        return items


def collect_sources(config: dict[str, Any], now: datetime) -> list[SourceItem]:
    window_hours = int(config.get("window_hours", 24))
    since = now - timedelta(hours=window_hours)
    items: list[SourceItem] = []
    items.extend(LocalInboxCollector(config["inbox_dir"]).collect(since, now))
    items.extend(
        RssCollector(
            config.get("wechat", {}).get("rss_feeds", []),
            timeout=int(config.get("llm", {}).get("timeout_seconds", 60)),
        ).collect(since, now)
    )
    items.extend(FeishuGroupCollector(config.get("feishu", {})).collect(since, now))
    return deduplicate(items)


def deduplicate(items: Iterable[SourceItem]) -> list[SourceItem]:
    result: list[SourceItem] = []
    seen: set[str] = set()
    for item in items:
        key = item.url.strip().lower() or f"{item.title.strip().lower()}|{item.source.strip().lower()}"
        if not item.title or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
