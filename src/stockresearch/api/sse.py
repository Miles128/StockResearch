"""FastAPI SSE 流式响应公共封装。"""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse


def sse_response(
    event_generator: AsyncIterator[dict[str, object]],
    *,
    keep_alive_seconds: float = 15.0,
) -> StreamingResponse:
    """把异步事件生成器包装为 SSE StreamingResponse。

    调用方只需 yield dict 事件；序列化、keep-alive 心跳由本函数统一处理。
    """

    async def _wrapped() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        next_deadline = loop.time() + keep_alive_seconds
        async for event in event_generator:
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            now = loop.time()
            if now >= next_deadline:
                yield ": keep-alive\n\n"
                next_deadline = now + keep_alive_seconds

    return StreamingResponse(_wrapped(), media_type="text/event-stream")
