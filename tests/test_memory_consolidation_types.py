"""Test MemoryStore.consolidate() handles non-string tool call arguments.

Regression test for upstream issue #1042
When memory consolidation receives dict values instead of strings from the LLM
tool call response, it should serialize them to JSON instead of raising TypeError.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crabclaw.agent.memory import MemoryStore
from crabclaw.providers.base import LLMResponse, ToolCallRequest


def _make_session(message_count: int = 30, memory_window: int = 50):
    """Create a mock session with messages."""
    session = MagicMock()
    session.messages = [
        {"role": "user", "content": f"msg{i}", "timestamp": "2026-01-01 00:00"}
        for i in range(message_count)
    ]
    session.last_consolidated = 0
    return session


def _make_tool_response(global_sem=None, user_sem=None, user_epi=None):
    """Create an LLMResponse with a save_memory tool call."""
    return LLMResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id="call_1",
                name="save_memory",
                arguments={
                    "global_semantic_updates": global_sem or {},
                    "user_semantic_updates": user_sem or {},
                    "user_episodic_entry": user_epi,
                },
            )
        ],
    )


class TestMemoryConsolidationTypeHandling:
    """Test that consolidation handles various argument types correctly."""

    @pytest.fixture(autouse=True)
    def patch_config(self):
        with patch("crabclaw.config.loader.load_config", side_effect=Exception("mocked")):
            yield

    @pytest.mark.asyncio
    async def test_string_arguments_work(self, tmp_path: Path) -> None:
        """Normal case: LLM returns string arguments."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=_make_tool_response(
                global_sem={"rule": "Test"},
                user_sem={"likes": "testing"},
                user_epi="[2026-01-01] User discussed testing.",
            )
        )
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50, user_scope="test_user")

        assert result is True
        
        _, episodic_file = store._get_user_memory_paths("test_user")
        assert episodic_file.exists()
        assert "[2026-01-01] User discussed testing." in episodic_file.read_text()
        assert "testing" in store.read_user_semantic("test_user").get("likes", "")
        assert "Test" in store.read_global_semantic().get("rule", "")

    @pytest.mark.asyncio
    async def test_dict_arguments_serialized_to_json(self, tmp_path: Path) -> None:
        """Issue #1042: LLM returns dict instead of string - must not raise TypeError."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=_make_tool_response(
                user_epi={"timestamp": "2026-01-01", "summary": "User discussed testing."},
                user_sem={"facts": ["User likes testing"], "topics": ["testing"]},
            )
        )
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50, user_scope="test_user")

        assert result is True
        _, episodic_file = store._get_user_memory_paths("test_user")
        assert episodic_file.exists()
        history_content = episodic_file.read_text()
        assert "User discussed testing." in history_content

        user_sem = store.read_user_semantic("test_user")
        assert "User likes testing" in user_sem.get("facts", [])

    @pytest.mark.asyncio
    async def test_string_arguments_as_raw_json(self, tmp_path: Path) -> None:
        """Some providers return arguments as a JSON string instead of parsed dict."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()

        # Simulate arguments being a JSON string (not yet parsed)
        response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="save_memory",
                    arguments=json.dumps({
                        "user_episodic_entry": "[2026-01-01] User discussed testing.",
                        "user_semantic_updates": {"likes": "testing"},
                    }),
                )
            ],
        )
        provider.chat = AsyncMock(return_value=response)
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50, user_scope="test_user")

        assert result is True
        _, episodic_file = store._get_user_memory_paths("test_user")
        assert "User discussed testing." in episodic_file.read_text()

    @pytest.mark.asyncio
    async def test_no_tool_call_returns_false(self, tmp_path: Path) -> None:
        """When LLM doesn't use the save_memory tool, returns true after fallback."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=LLMResponse(content="I summarized the conversation.", tool_calls=[])
        )
        session = _make_session(message_count=60)

        # Trigger failure loop
        for _ in range(3):
            result = await store.consolidate(session, provider, "test-model", memory_window=50, user_scope="test_user")
            
        assert result is True
        _, episodic_file = store._get_user_memory_paths("test_user")
        assert episodic_file.exists()
        assert "[RAW]" in episodic_file.read_text()

    @pytest.mark.asyncio
    async def test_skips_when_few_messages(self, tmp_path: Path) -> None:
        """Consolidation should be a no-op when messages < keep_count."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        session = _make_session(message_count=10)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is True
        provider.chat.assert_not_called()
