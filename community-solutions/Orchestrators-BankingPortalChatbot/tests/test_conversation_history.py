"""Unit tests for services/conversation_history.py."""
import pytest
from services.conversation_history import ConversationHistory


class TestConversationHistory:
    def test_init_with_system_prompt(self):
        h = ConversationHistory(system_prompt="You are helpful.")
        msgs = h.get_messages()
        assert len(msgs) >= 1
        assert msgs[0]["role"] == "system"

    def test_add_user_and_assistant(self):
        h = ConversationHistory(system_prompt="sys")
        h.add_user_message("hi")
        h.add_assistant_message("hello!")
        msgs = h.get_messages()
        assert msgs[-2]["content"] == "hi"
        assert msgs[-1]["content"] == "hello!"

    def test_save_and_load(self, tmp_path):
        fp = tmp_path / "hist.json"
        h = ConversationHistory(system_prompt="sys")
        h.add_user_message("q")
        h.add_assistant_message("a")
        h.save_to_file(fp)
        loaded = ConversationHistory.load_from_file(fp)
        assert loaded is not None
        assert len(loaded.messages) == 3

    def test_load_nonexistent_returns_none(self, tmp_path):
        assert ConversationHistory.load_from_file(tmp_path / "nope.json") is None
