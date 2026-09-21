from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from .digest import REQUIRED_HEADERS
from .feishu import _request_json, _tenant_token


MUST_READ_PATTERN = re.compile(
    r"^(?:\d+\.\s*)?《(?P<title>.+?)》\s*\[原文\]\((?P<url>https?://[^)]+)\)\s*(?P<body>.*)$"
)
WORTH_PATTERN = re.compile(
    r"^《(?P<title>.+?)》\s*\[原文\]\((?P<url>https?://[^)]+)\)\s*$"
)


@dataclass(slots=True)
class DigestEntry:
    category: str
    title: str
    url: str = ""
    summary: str = ""
    implication: str = ""


def parse_bitable_url(value: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(value.strip())
    match = re.search(r"/(?:base|bitable|wiki)/([^/?#]+)", parsed.path)
    query = urllib.parse.parse_qs(parsed.query)
    app_token = match.group(1) if match else ""
    table_id = (query.get("table") or query.get("table_id") or [""])[0]
    return app_token, table_id


def _section(text: str, start: str, end: str | None = None) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    start_index += len(start)
    end_index = text.find(end, start_index) if end else -1
    return text[start_index:end_index if end_index >= 0 else None]


def parse_digest(text: str) -> list[DigestEntry]:
    entries: list[DigestEntry] = []
    must_read = _section(text, REQUIRED_HEADERS[0], REQUIRED_HEADERS[1])
    worth_watching = _section(text, REQUIRED_HEADERS[1], REQUIRED_HEADERS[2])
    ignored = _section(text, REQUIRED_HEADERS[2])

    for raw_line in must_read.splitlines():
        line = raw_line.strip()
        match = MUST_READ_PATTERN.match(line)
        if not match:
            continue
        sentences = [
            sentence.strip()
            for sentence in re.findall(r"[^。！？]+[。！？]", match.group("body"))
        ]
        entries.append(
            DigestEntry(
                category="今日必读",
                title=match.group("title").strip(),
                url=match.group("url").strip(),
                summary=sentences[0] if sentences else match.group("body").strip(),
                implication="".join(sentences[1:]).strip(),
            )
        )

    for raw_line in worth_watching.splitlines():
        line = raw_line.strip()
        match = WORTH_PATTERN.match(line)
        if not match:
            continue
        entries.append(
            DigestEntry(
                category="值得留意",
                title=match.group("title").strip(),
                url=match.group("url").strip(),
            )
        )

    ignored_text = " ".join(
        line.strip()
        for line in ignored.splitlines()
        if line.strip() and line.strip() != "无"
    )
    if ignored_text:
        entries.append(
            DigestEntry(
                category="可忽略",
                title="可忽略汇总",
                summary=ignored_text,
            )
        )
    return entries


class FeishuBitableSender:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.app_token = str(config.get("app_token", "")).strip()
        self.table_id = str(config.get("table_id", "")).strip()
        url_app_token, url_table_id = parse_bitable_url(str(config.get("url", "")))
        self.app_token = self.app_token or url_app_token
        self.table_id = self.table_id or url_table_id
        self.fields = {
            "date": "日期",
            "category": "分类",
            "title": "标题",
            "link": "链接",
            "summary": "摘要",
            "implication": "求职启示",
            **(config.get("fields") or {}),
        }
        self.date_field_type = str(config.get("date_field_type", "text"))
        self.link_field_type = str(config.get("link_field_type", "url"))

    def _base_url(self) -> str:
        if not self.app_token or not self.table_id:
            raise ValueError(
                "Bitable is not configured. Set feishu.bitable.url, "
                "or set app_token and table_id."
            )
        return (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{urllib.parse.quote(self.app_token)}/tables/"
            f"{urllib.parse.quote(self.table_id)}"
        )

    def list_fields(self) -> list[dict[str, Any]]:
        token = _tenant_token(self.config)
        response = _request_json(
            self._base_url() + "/fields?page_size=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.get("code") != 0:
            raise RuntimeError(f"Failed to read Bitable fields: {response}")
        return list((response.get("data") or {}).get("items") or [])

    def list_records(self) -> list[dict[str, Any]]:
        token = _tenant_token(self.config)
        records: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query = {"page_size": "100"}
            if page_token:
                query["page_token"] = page_token
            response = _request_json(
                self._base_url()
                + "/records?"
                + urllib.parse.urlencode(query),
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.get("code") != 0:
                raise RuntimeError(f"Failed to read Bitable records: {response}")
            data = response.get("data") or {}
            records.extend(data.get("items") or [])
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token", ""))
            if not page_token:
                break
        return records

    def send_digest(self, text: str, coverage_date: date) -> int:
        entries = parse_digest(text)
        if not entries:
            raise ValueError("No digest entries could be parsed for Bitable delivery.")
        existing_keys = self._existing_keys(self.list_records(), coverage_date)
        entries = [
            entry
            for entry in entries
            if self._entry_key(entry, coverage_date) not in existing_keys
        ]
        if not entries:
            return 0
        token = _tenant_token(self.config)
        records = [
            {"fields": self._record_fields(entry, coverage_date)}
            for entry in entries
        ]
        response = _request_json(
            self._base_url() + "/records/batch_create",
            method="POST",
            payload={"records": records},
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.get("code") != 0:
            raise RuntimeError(f"Failed to create Bitable records: {response}")
        return len((response.get("data") or {}).get("records") or records)

    def _entry_key(self, entry: DigestEntry, coverage_date: date) -> tuple[str, str, str]:
        identifier = entry.url.strip() or entry.title.strip().lower()
        return coverage_date.isoformat(), entry.category, identifier

    def _existing_keys(
        self,
        records: list[dict[str, Any]],
        coverage_date: date,
    ) -> set[tuple[str, str, str]]:
        keys: set[tuple[str, str, str]] = set()
        for record in records:
            fields = record.get("fields") or {}
            date_value = fields.get(self.fields["date"])
            if isinstance(date_value, (int, float)):
                date_text = datetime.fromtimestamp(
                    date_value / 1000,
                    tz=timezone.utc,
                ).date().isoformat()
            else:
                date_text = str(date_value or "").strip()
            if date_text != coverage_date.isoformat():
                continue
            link_value = fields.get(self.fields["link"])
            if isinstance(link_value, dict):
                link_value = link_value.get("link", "")
            title = str(fields.get(self.fields["title"]) or "").strip().lower()
            identifier = str(link_value or "").strip() or title
            keys.add(
                (
                    date_text,
                    str(fields.get(self.fields["category"]) or "").strip(),
                    identifier,
                )
            )
        return keys

    def _record_fields(self, entry: DigestEntry, coverage_date: date) -> dict[str, Any]:
        fields: dict[str, Any] = {
            self.fields["category"]: entry.category,
            self.fields["title"]: entry.title,
        }
        if self.date_field_type == "date":
            date_value = datetime.combine(
                coverage_date,
                time.min,
                tzinfo=timezone.utc,
            )
            fields[self.fields["date"]] = int(date_value.timestamp() * 1000)
        else:
            fields[self.fields["date"]] = coverage_date.isoformat()
        if entry.url:
            fields[self.fields["link"]] = (
                {"link": entry.url, "text": "原文"}
                if self.link_field_type == "url"
                else entry.url
            )
        if entry.summary:
            fields[self.fields["summary"]] = entry.summary
        if entry.implication:
            fields[self.fields["implication"]] = entry.implication
        return fields
