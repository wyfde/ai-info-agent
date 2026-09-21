from __future__ import annotations

import unittest
from datetime import date

from ai_job_intel.bitable import FeishuBitableSender, parse_bitable_url, parse_digest


DIGEST = """【今日必读】
1.《OpenAI发布新模型》[原文](https://example.com/openai) 新模型强化了企业部署能力。求职者应学习企业级AI集成。

【值得留意】
《AI客服案例》[原文](https://example.com/case)

【可忽略】
论文解读、纯技术原理共2篇。"""


class BitableTests(unittest.TestCase):
    def test_parse_bitable_url(self) -> None:
        app_token, table_id = parse_bitable_url(
            "https://example.feishu.cn/base/bascn123?table=tbl456&view=vew789"
        )
        self.assertEqual(app_token, "bascn123")
        self.assertEqual(table_id, "tbl456")

    def test_parse_wiki_bitable_url(self) -> None:
        app_token, table_id = parse_bitable_url(
            "https://example.feishu.cn/wiki/wikcn123?table=tbl456&view=vew789"
        )
        self.assertEqual(app_token, "wikcn123")
        self.assertEqual(table_id, "tbl456")

    def test_parse_digest(self) -> None:
        entries = parse_digest(DIGEST)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].category, "今日必读")
        self.assertEqual(entries[0].url, "https://example.com/openai")
        self.assertEqual(entries[0].summary, "新模型强化了企业部署能力。")
        self.assertEqual(entries[0].implication, "求职者应学习企业级AI集成。")

    def test_record_fields_use_configured_names(self) -> None:
        sender = FeishuBitableSender(
            {
                "app_token": "app",
                "table_id": "table",
                "fields": {"title": "文章标题"},
            }
        )
        entry = parse_digest(DIGEST)[0]
        fields = sender._record_fields(entry, date(2026, 9, 21))
        self.assertEqual(fields["文章标题"], "OpenAI发布新模型")
        self.assertEqual(fields["日期"], "2026-09-21")
        self.assertEqual(fields["链接"]["link"], "https://example.com/openai")

    def test_existing_keys_detect_duplicate(self) -> None:
        sender = FeishuBitableSender(
            {
                "app_token": "app",
                "table_id": "table",
            }
        )
        entry = parse_digest(DIGEST)[0]
        keys = sender._existing_keys(
            [
                {
                    "fields": {
                        "日期": "2026-09-21",
                        "分类": "今日必读",
                        "标题": "OpenAI发布新模型",
                        "链接": {"link": "https://example.com/openai"},
                    }
                }
            ],
            date(2026, 9, 21),
        )
        self.assertIn(sender._entry_key(entry, date(2026, 9, 21)), keys)

    def test_duplicate_detection_uses_link_before_title(self) -> None:
        sender = FeishuBitableSender(
            {
                "app_token": "app",
                "table_id": "table",
            }
        )
        entry = parse_digest(DIGEST)[0]
        changed_title = type(entry)(
            category=entry.category,
            title="OpenAI新模型正式发布",
            url=entry.url,
            summary=entry.summary,
            implication=entry.implication,
        )
        keys = sender._existing_keys(
            [
                {
                    "fields": {
                        "日期": "2026-09-21",
                        "分类": "今日必读",
                        "标题": "OpenAI发布新模型",
                        "链接": {"link": "https://example.com/openai"},
                    }
                }
            ],
            date(2026, 9, 21),
        )
        self.assertIn(sender._entry_key(changed_title, date(2026, 9, 21)), keys)


if __name__ == "__main__":
    unittest.main()
