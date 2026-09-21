from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import get_secret


class OpenAICompatibleLLM:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.base_url = str(config.get("base_url", "")).rstrip("/")
        self.model = str(config.get("model", "")).strip()
        self.api_style = str(config.get("api_style", "chat_completions")).strip()
        self.api_key = str(config.get("api_key", "")).strip() or get_secret(
            config,
            "api_key_env",
            "api_key",
        )
        self.timeout = int(config.get("timeout_seconds", 120))
        self.max_tokens = int(config.get("max_tokens", 4096))
        if not self.base_url or not self.model:
            raise ValueError("LLM base_url and model must be configured.")
        if not self.api_key:
            raise ValueError(
                "Missing LLM API key. Set llm.api_key in config.json or environment variable "
                f"{config.get('api_key_env', 'AI_JOB_INTEL_LLM_API_KEY')}."
            )

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if self.api_style == "responses":
            return self._responses(system_prompt, user_prompt)
        return self._chat_completions(system_prompt, user_prompt)

    def _chat_completions(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        response = self._post("/chat/completions", payload)
        try:
            message = response["choices"][0]["message"]
            content = str(message.get("content") or "").strip()
            if not content and message.get("reasoning_content"):
                raise RuntimeError(
                    "LLM used the entire completion budget for reasoning. "
                    "Increase llm.max_tokens in config.json."
                )
            return content
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response: {response}") from exc

    def _responses(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "max_output_tokens": self.max_tokens,
        }
        response = self._post("/responses", payload)
        output_text = response.get("output_text")
        if output_text:
            return str(output_text).strip()
        fragments: list[str] = []
        for output in response.get("output", []):
            for content in output.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    fragments.append(str(content["text"]))
        if fragments:
            return "".join(fragments).strip()
        raise RuntimeError(f"Unexpected LLM response: {response}")

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {details}") from exc
