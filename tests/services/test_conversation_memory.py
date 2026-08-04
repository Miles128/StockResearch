import pytest

from stockresearch.services.chat.conversation_memory import (
    MEMORY_CHAR_LIMIT,
    _message_chars,
    compress_messages_if_needed,
)
from stockresearch.services.mock_llm import MockLLMClient


@pytest.mark.asyncio
async def test_compress_messages_when_over_limit() -> None:
    messages = [
        {"role": "user", "content": "x" * 6000},
        {"role": "assistant", "content": "y" * 6000},
        {"role": "user", "content": "recent question"},
        {"role": "assistant", "content": "recent answer"},
    ]
    assert _message_chars(messages) > MEMORY_CHAR_LIMIT
    compressed = await compress_messages_if_needed(MockLLMClient(), messages)
    assert compressed[0]["content"].startswith("【会话摘要】")
    assert _message_chars(compressed) < _message_chars(messages)
    assert compressed[-1]["content"] == "recent answer"
