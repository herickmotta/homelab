from __future__ import annotations

import time
from typing import Any

import httpx

from hermes_triage.audit import audit
from hermes_triage.config import Config
from hermes_triage.engine import Engine


class TelegramBot:
    def __init__(
        self,
        config: Config,
        engine: Engine,
        http: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.engine = engine
        self.http = http or httpx.Client(timeout=httpx.Timeout(45.0))
        self._offset = 0
        self._base = f"https://api.telegram.org/bot{config.telegram_bot_token}"

    def poll_once(self) -> None:
        response = self.http.get(
            f"{self._base}/getUpdates",
            params={"timeout": 30, "offset": self._offset, "allowed_updates": ["message"]},
        )
        response.raise_for_status()
        for update in response.json().get("result", []):
            self._offset = int(update["update_id"]) + 1
            self.handle_update(update)

    def run_forever(self) -> None:
        while True:
            try:
                self.poll_once()
            except httpx.HTTPError as exc:
                audit("telegram_poll_error", error=str(exc))
                time.sleep(5)

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = str(message.get("text") or "").strip()
        if chat_id != self.config.telegram_chat_id:
            audit("telegram_rejected", chat_id=chat_id)
            return
        if not text:
            return
        self.engine.diagnose_telegram(text)

    def send(self, text: str) -> None:
        self.http.post(
            f"{self._base}/sendMessage",
            json={
                "chat_id": self.config.telegram_chat_id,
                "text": text[:3900],
            },
        )
