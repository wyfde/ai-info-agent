from __future__ import annotations

import unittest
from datetime import date

from ai_job_intel.digest import DigestGenerator, count_digest_chars, validate_digest
from ai_job_intel.models import SourceItem


VALID_DIGEST = """【今日必读】
1.《OpenAI发布新模型》 [原文](https://example.com/openai)
新模型强化了工具调用和企业部署能力。求职者应在作品集中展示真实业务流程的集成能力。

【值得留意】
《AI客服落地观察》 [原文](https://example.com/customer-service)

【可忽略】
论文解读、纯技术原理、焦虑文共3篇。"""


class FakeLLM:
    def __init__(self, output: str):
        self.output = output

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.output


class DigestTests(unittest.TestCase):
    def test_count_excludes_urls_and_whitespace(self) -> None:
        self.assertEqual(count_digest_chars("标题 https://example.com/a 内容"), 4)

    def test_validate_accepts_expected_format(self) -> None:
        self.assertEqual(validate_digest(VALID_DIGEST), [])

    def test_validate_rejects_missing_headers(self) -> None:
        errors = validate_digest("只有正文")
        self.assertTrue(any("分类标题" in error for error in errors))

    def test_validate_requires_links_for_items(self) -> None:
        digest = VALID_DIGEST.replace("[原文](https://example.com/openai)", "")
        errors = validate_digest(digest, require_links=True)
        self.assertTrue(any("链接" in error for error in errors))

    def test_generator_returns_empty_digest(self) -> None:
        generator = DigestGenerator(FakeLLM("unused"))
        result = generator.generate([], date(2026, 9, 21))
        self.assertIn("【今日必读】", result)
        self.assertIn("【可忽略】", result)

    def test_generator_uses_llm_output(self) -> None:
        item = SourceItem(id="1", title="测试", source="inbox", content="内容")
        generator = DigestGenerator(FakeLLM(VALID_DIGEST))
        result = generator.generate([item], date(2026, 9, 21))
        self.assertEqual(result, VALID_DIGEST)


if __name__ == "__main__":
    unittest.main()
