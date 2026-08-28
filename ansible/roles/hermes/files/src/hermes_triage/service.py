from __future__ import annotations

import threading

from hermes_triage.audit import configure_logging
from hermes_triage.config import Config
from hermes_triage.engine import Engine
from hermes_triage.openai_client import OpenAITriage
from hermes_triage.state import ConversationStore
from hermes_triage.telegram import TelegramBot
from hermes_triage.tools import ToolExecutor
from hermes_triage.webhook import make_server


def main() -> int:
    configure_logging()
    config = Config.from_env()
    tools = ToolExecutor(config)
    model = OpenAITriage(config, tools)
    store = ConversationStore(config)
    engine = Engine(config, store, model)
    bot = TelegramBot(config, engine)
    engine.notify = bot.send
    server = make_server(config, engine)
    thread = threading.Thread(target=server.serve_forever, name="hermes-webhook", daemon=True)
    thread.start()
    bot.run_forever()
    return 0
