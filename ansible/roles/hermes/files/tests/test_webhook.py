from __future__ import annotations

import json
from unittest.mock import Mock

from hermes_triage.engine import Engine
from hermes_triage.webhook import authorize, handle_webhook


class FakeModel:
    def complete(self, prompt, history, complex_case=False):
        return "Observed: test\nInference: none\nConfidence: low\nProposed action: none\nNot verified: none"


def test_authorize_requires_bearer_secret(config):
    assert authorize("Bearer supersecret-token", config.webhook_secret)
    assert not authorize("Bearer nope", config.webhook_secret)
    assert not authorize(None, config.webhook_secret)


def test_webhook_rejects_bad_secret_without_model(config, tmp_path):
    from hermes_triage.state import ConversationStore

    engine = Engine(config, ConversationStore(config), FakeModel())
    status, body = handle_webhook(engine, "Bearer nope", b"{}")
    assert status == 401
    assert body == b"unauthorized\n"


def test_webhook_accepts_and_does_not_retry(config):
    from hermes_triage.state import ConversationStore

    engine = Engine(config, ConversationStore(config), FakeModel())
    payload = {
        "status": "firing",
        "alerts": [{"fingerprint": "abc", "labels": {"alertname": "AlloyDown"}}],
    }
    status, body = handle_webhook(
        engine,
        "Bearer supersecret-token",
        json.dumps(payload).encode(),
    )
    assert status == 200
    assert body == b"accepted\n"


def test_telegram_rejects_other_chat_ids(config):
    from hermes_triage.state import ConversationStore
    from hermes_triage.telegram import TelegramBot

    model = Mock()
    engine = Engine(config, ConversationStore(config), model)
    bot = TelegramBot(config, engine, http=Mock())
    bot.handle_update({"update_id": 1, "message": {"chat": {"id": 99}, "text": "hi"}})
    model.complete.assert_not_called()
