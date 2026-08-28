from __future__ import annotations

from hermes_triage.engine import Engine
from hermes_triage.openai_client import ModelError
from hermes_triage.state import ConversationStore


class BoomModel:
    def complete(self, prompt, history, complex_case=False):
        raise ModelError("openai down")


class CountingModel:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, history, complex_case=False):
        self.calls += 1
        return "Observed: ok\nInference: none\nConfidence: high\nProposed action: none\nNot verified: none"


def test_conversation_expires(config, tmp_path):
    import json

    store = ConversationStore(config)
    path = tmp_path / f"chat-{config.telegram_chat_id}.json"
    path.write_text(json.dumps({"turns": [{"role": "user", "text": "old"}], "updated_at": 0}))
    loaded = store.load(config.telegram_chat_id)
    assert loaded["turns"] == []


def test_alert_fingerprint_dedup(config):
    model = CountingModel()
    engine = Engine(config, ConversationStore(config), model)
    payload = {"alerts": [{"fingerprint": "fp-1", "labels": {"alertname": "AlloyDown"}}]}
    assert engine.diagnose_alert(payload)
    assert engine.diagnose_alert(payload) is None
    assert model.calls == 1


def test_model_failure_does_not_raise(config):
    notified: list[str] = []
    engine = Engine(config, ConversationStore(config), BoomModel(), notify=notified.append)
    reply = engine.diagnose_telegram("what is down?")
    assert "model request failed" in reply
    assert notified == [reply]


def test_sol_prefix_selects_complex_model(config):
    seen: list[bool] = []

    class Capture:
        def complete(self, prompt, history, complex_case=False):
            seen.append(complex_case)
            return "Observed: x\nInference: x\nConfidence: low\nProposed action: x\nNot verified: x"

    engine = Engine(config, ConversationStore(config), Capture())
    engine.diagnose_telegram("/sol why is nas quiet")
    assert seen == [True]
