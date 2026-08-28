from __future__ import annotations

import json
from typing import Any

import httpx

from hermes_triage.audit import audit
from hermes_triage.config import Config
from hermes_triage.tools import INSTRUCTIONS, ToolError, ToolExecutor, tool_schemas


class ModelError(RuntimeError):
    """Raised when the model API fails after the allowed retry."""


class OpenAITriage:
    def __init__(
        self,
        config: Config,
        tools: ToolExecutor,
        http: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.tools = tools
        timeout = httpx.Timeout(config.openai_timeout_seconds)
        self.http = http or httpx.Client(timeout=timeout)
        self._owns_http = http is None

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def complete(
        self,
        user_text: str,
        history: list[dict[str, str]],
        *,
        complex_case: bool = False,
    ) -> str:
        model = (
            self.config.openai_model_complex
            if complex_case
            else self.config.openai_model_default
        )
        messages: list[dict[str, Any]] = []
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["text"]})
        messages.append({"role": "user", "content": user_text})
        payload: dict[str, Any] = {
            "model": model,
            "store": False,
            "parallel_tool_calls": False,
            "instructions": INSTRUCTIONS,
            "input": messages,
            "tools": tool_schemas(self.config),
        }
        tool_trace: list[str] = []
        for _ in range(8):
            data = self._post(payload)
            output = data.get("output") or []
            calls = [item for item in output if item.get("type") == "function_call"]
            if not calls:
                audit(
                    "model_complete",
                    model=model,
                    tools=tool_trace,
                    usage=data.get("usage", {}),
                    latency_ms=data.get("metadata", {}).get("latency_ms"),
                )
                return _message_text(output) or data.get("output_text") or ""
            payload["input"] = list(payload["input"]) + output
            for call in calls:
                name = str(call.get("name", ""))
                raw_args = call.get("arguments", "{}")
                try:
                    result = self.tools.execute(name, raw_args)
                except ToolError as exc:
                    result = json.dumps({"error": str(exc)})
                tool_trace.append(name)
                payload["input"].append(
                    {
                        "type": "function_call_output",
                        "call_id": call.get("call_id"),
                        "output": result,
                    }
                )
        raise ModelError("model exceeded tool-call budget")

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.http.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {self.config.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code >= 500 or response.status_code == 429:
                    last_error = ModelError(f"openai status {response.status_code}")
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 0:
                    continue
                break
        audit("model_failure", error=str(last_error))
        raise ModelError(str(last_error))


def _message_text(output: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for item in output:
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") in {"output_text", "text"} and part.get("text"):
                chunks.append(part["text"])
    return "\n".join(chunks)
