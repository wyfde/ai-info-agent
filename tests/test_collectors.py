from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_job_intel.collectors import LocalInboxCollector, deduplicate
from ai_job_intel.models import SourceItem


class CollectorTests(unittest.TestCase):
    def test_local_inbox_reads_text_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "article.md").write_text("# 标题\n正文", encoding="utf-8")
            (root / "items.json").write_text(
                json.dumps([{"title": "JSON标题", "content": "JSON正文", "url": "https://example.com"}]),
                encoding="utf-8",
            )
            now = datetime.now(timezone.utc)
            items = LocalInboxCollector(str(root)).collect(
                now.replace(hour=0, minute=0, second=0, microsecond=0),
                now,
            )
            self.assertEqual(len(items), 2)
            self.assertIn("标题", {item.title for item in items})
            self.assertIn("JSON标题", {item.title for item in items})

    def test_deduplicate_prefers_first_url(self) -> None:
        items = [
            SourceItem(id="1", title="A", source="one", url="https://example.com/a"),
            SourceItem(id="2", title="A2", source="two", url="https://example.com/a"),
            SourceItem(id="3", title="B", source="one"),
        ]
        result = deduplicate(items)
        self.assertEqual([item.id for item in result], ["1", "3"])


if __name__ == "__main__":
    unittest.main()
