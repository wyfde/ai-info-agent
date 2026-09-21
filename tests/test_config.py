from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ai_job_intel.config import get_secret


class ConfigTests(unittest.TestCase):
    def test_secret_uses_environment_first(self) -> None:
        with patch.dict(os.environ, {"TEST_SECRET": "from-env"}):
            value = get_secret(
                {"env": "TEST_SECRET", "value": "from-config"},
                "env",
            )
        self.assertEqual(value, "from-env")

    def test_secret_falls_back_to_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            value = get_secret(
                {"env": "TEST_SECRET", "value": "from-config"},
                "env",
            )
        self.assertEqual(value, "from-config")


if __name__ == "__main__":
    unittest.main()
