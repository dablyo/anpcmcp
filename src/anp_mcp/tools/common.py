"""工具共享：JSON 输出格式化 + 统一异常→错误 JSON 包装。"""
from __future__ import annotations

import functools
import json
from typing import Any, Awaitable, Callable

from ..client import ApiError
from ..registry import UnknownControllerError


def dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def tool_error(controller: str, message: str, **extra: Any) -> str:
    payload: dict[str, Any] = {"controller": controller, "error": message, **extra}
    return dump_json(payload)


def fmt_result(controller_name: str, body: dict) -> str:
    """控制器原始 {code, value} + 来源控制器名。"""
    return dump_json({"controller": controller_name, **body})


def mcp_tool_wrapper(fn: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """捕获已知异常并格式化为 JSON 错误串。

    functools.wraps 保留函数名/签名/docstring，FastMCP 依此生成 schema。
    """
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return await fn(*args, **kwargs)
        except UnknownControllerError as exc:
            return tool_error(exc.name, str(exc), available=exc.available)
        except ApiError as exc:
            extra: dict[str, Any] = {}
            if exc.http_status is not None:
                extra["httpStatus"] = exc.http_status
            return tool_error(exc.controller, str(exc), **extra)
    return wrapper
