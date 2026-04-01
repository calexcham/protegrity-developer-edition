"""Simple conversation history manager for the banking chatbot."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


class ConversationHistory:
    def __init__(self, system_prompt: str = "", max_turns: int = 20):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.messages: list[dict] = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})
        self._trim()

    def get_messages(self) -> list[dict]:
        return list(self.messages)

    def _trim(self):
        # Keep system message + last max_turns*2 messages (user+assistant pairs)
        if len(self.messages) <= 1:
            return
        non_system = [m for m in self.messages if m["role"] != "system"]
        if len(non_system) > self.max_turns * 2:
            system_msgs = [m for m in self.messages if m["role"] == "system"]
            self.messages = system_msgs + non_system[-(self.max_turns * 2):]

    def clear(self):
        sys_msg = self.messages[0] if self.messages and self.messages[0]["role"] == "system" else None
        self.messages = []
        if sys_msg:
            self.messages.append(sys_msg)

    def save_to_file(self, filepath: Path):
        try:
            filepath.write_text(json.dumps(self.messages, indent=2))
        except Exception:
            pass

    @classmethod
    def load_from_file(cls, filepath: Path) -> Optional["ConversationHistory"]:
        if not filepath.exists():
            return None
        try:
            data = json.loads(filepath.read_text())
            if not isinstance(data, list):
                return None
            hist = cls()
            hist.messages = data
            return hist
        except Exception:
            return None
