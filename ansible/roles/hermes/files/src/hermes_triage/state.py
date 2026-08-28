from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hermes_triage.config import Config


class ConversationStore:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._root = Path(config.state_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, chat_id: int) -> Path:
        return self._root / f"chat-{chat_id}.json"

    def load(self, chat_id: int) -> dict[str, Any]:
        path = self._path(chat_id)
        if not path.is_file():
            return {"chat_id": chat_id, "turns": [], "fingerprints": {}}
        data = json.loads(path.read_text())
        updated = float(data.get("updated_at", 0))
        if time.time() - updated > self._config.conversation_ttl_seconds:
            return {"chat_id": chat_id, "turns": [], "fingerprints": {}}
        data.setdefault("turns", [])
        data.setdefault("fingerprints", {})
        return data

    def save(self, chat_id: int, data: dict[str, Any]) -> None:
        data["chat_id"] = chat_id
        data["updated_at"] = time.time()
        turns = data.get("turns", [])[-self._config.conversation_max_turns :]
        data["turns"] = turns
        path = self._path(chat_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)

    def remember_turn(self, chat_id: int, role: str, text: str) -> None:
        data = self.load(chat_id)
        data["turns"].append({"role": role, "text": text[:1000]})
        self.save(chat_id, data)

    def recent_fingerprint(self, fingerprint: str) -> bool:
        data = self.load(self._config.telegram_chat_id)
        seen = float(data.get("fingerprints", {}).get(fingerprint, 0))
        return bool(seen) and (time.time() - seen) < self._config.diagnosis_cooldown_seconds

    def mark_fingerprint(self, fingerprint: str) -> None:
        data = self.load(self._config.telegram_chat_id)
        fingerprints = {
            key: ts
            for key, ts in data.get("fingerprints", {}).items()
            if time.time() - float(ts) < self._config.diagnosis_cooldown_seconds * 4
        }
        fingerprints[fingerprint] = time.time()
        data["fingerprints"] = fingerprints
        self.save(self._config.telegram_chat_id, data)
