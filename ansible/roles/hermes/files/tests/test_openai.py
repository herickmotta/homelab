from __future__ import annotations

import json

from hermes_triage.openai_client import OpenAITriage


class FakeHTTP:
    def __init__(self, bodies):
        self.bodies = bodies
        self.calls = []

    def post(self, url, headers=None, json=None):
        self.calls.append(json)
        import httpx

        body = self.bodies.pop(0)
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=body, request=request)


def test_responses_request_disables_store_and_parallel_tools(config):
    from hermes_triage.tools import ToolExecutor
    import httpx

    http = FakeHTTP(
        [
            {
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "ok"}]}
                ],
                "usage": {"total_tokens": 12},
            }
        ]
    )
    client = OpenAITriage(config, ToolExecutor(config, http=httpx.Client()), http=http)
    client.complete("hello", [])
    payload = http.calls[0]
    assert payload["store"] is False
    assert payload["parallel_tool_calls"] is False
    assert payload["model"] == "gpt-5.6-luna"
    names = [tool["name"] for tool in payload["tools"]]
    assert "run_shell" not in names


def test_unknown_function_call_returns_tool_error_to_model(config):
    from hermes_triage.tools import ToolExecutor
    import httpx

    http = FakeHTTP(
        [
            {
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "run_shell",
                        "arguments": json.dumps({"command": "id"}),
                    }
                ]
            },
            {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "refused"}],
                    }
                ]
            },
        ]
    )
    client = OpenAITriage(config, ToolExecutor(config, http=httpx.Client()), http=http)
    text = client.complete("hack", [])
    assert text == "refused"
    output_item = http.calls[1]["input"][-1]
    assert output_item["type"] == "function_call_output"
    assert "not allowlisted" in output_item["output"]
