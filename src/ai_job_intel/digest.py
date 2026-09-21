from __future__ import annotations

import json
import re
from datetime import date
from typing import Protocol

from .models import SourceItem


MAX_CHINESE_CHARS = 500
REQUIRED_HEADERS = ("【今日必读】", "【值得留意】", "【可忽略】")
EMPTY_DIGEST = "【今日必读】\n无\n\n【值得留意】\n无\n\n【可忽略】\n无"


SYSTEM_PROMPT = """你是AI行业信息筛选助手。求职目标：AI产品经理、入门级AI解决方案顾问、AI应用开发。

输入是当天收集的飞书群和微信公众号文章。严格完成：
1. 【今日必读】收录大厂AI产品发布或重大更新、有数字和场景的行业落地、AI岗位市场/薪资/招聘趋势、AI应用开发内容。每篇使用“《标题》 [原文](来源URL)”后接恰好两句话：第一句主要内容，第二句对上述求职方向的启示。
2. 【值得留意】只列其他有信息量但不紧急的文章标题，并附“[原文](来源URL)”。
3. 【可忽略】将论文解读、纯技术原理、贩卖焦虑文章合并为一行。

只能使用输入JSON中提供的URL，不得猜测或拼接链接。无URL的条目不放入【今日必读】或【值得留意】。输出必须以这三个标题开头，按顺序排列。空分类写“无”。全文不超过500个汉字，不含URL。不要寒暄、不写方法说明、不编造数字或事实。只输出最终日报。"""


class TextLLM(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        ...


def count_digest_chars(text: str) -> int:
    without_urls = re.sub(r"https?://\S+", "", text)
    return len(re.sub(r"\s+", "", without_urls))


def clean_digest_output(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:markdown|md|text)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    first_header = cleaned.find(REQUIRED_HEADERS[0])
    return cleaned[first_header:] if first_header >= 0 else cleaned


def validate_digest(
    text: str,
    max_chars: int = MAX_CHINESE_CHARS,
    require_links: bool = False,
) -> list[str]:
    errors: list[str] = []
    positions = [text.find(header) for header in REQUIRED_HEADERS]
    if any(position < 0 for position in positions):
        errors.append("缺少规定的分类标题。")
    elif positions != sorted(positions):
        errors.append("分类标题顺序错误。")

    length = count_digest_chars(text)
    if length > max_chars:
        errors.append(f"当前约{length}字，超过{max_chars}字。")
    if require_links:
        must_read = _section_text(text, REQUIRED_HEADERS[0], REQUIRED_HEADERS[1])
        worth_watching = _section_text(text, REQUIRED_HEADERS[1], REQUIRED_HEADERS[2])
        item_lines = [
            line.strip()
            for line in must_read.splitlines() + worth_watching.splitlines()
            if line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "《"))
        ]
        if item_lines and any("](http" not in line for line in item_lines):
            errors.append("每个今日必读和值得留意条目都必须附Markdown原文链接。")
    return errors


def _section_text(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end)
    if start_index < 0 or end_index < 0 or end_index <= start_index:
        return ""
    return text[start_index + len(start) : end_index]


class DigestGenerator:
    def __init__(self, llm: TextLLM, max_chars: int = MAX_CHINESE_CHARS, attempts: int = 3):
        self.llm = llm
        self.max_chars = max_chars
        self.attempts = attempts

    def generate(self, items: list[SourceItem], coverage_date: date) -> str:
        if not items:
            return EMPTY_DIGEST

        source_payload = json.dumps(
            [item.to_dict() for item in items],
            ensure_ascii=False,
            indent=2,
        )
        base_prompt = (
            f"整理 {coverage_date.isoformat()} 的AI行业信息。\n"
            "请从以下JSON中筛选、去重并压缩，只输出最终日报。\n\n"
            f"{source_payload}"
        )
        last_errors: list[str] = []
        last_output = ""
        for attempt in range(1, self.attempts + 1):
            extra = ""
            if last_errors:
                extra = (
                    "\n上一版不合格，请修正以下问题后重新输出："
                    + " ".join(last_errors)
                    + " 删除低价值条目并进一步压缩，不能删掉今日必读中的求职启示句。"
                )
            output = clean_digest_output(self.llm.complete(SYSTEM_PROMPT, base_prompt + extra))
            errors = validate_digest(
                output,
                self.max_chars,
                require_links=any(item.url for item in items),
            )
            if not errors:
                return output
            last_errors = errors
            last_output = output
        raise ValueError("LLM两次以上未满足日报格式或长度要求：" + " ".join(last_errors) + f"\n{last_output}")
