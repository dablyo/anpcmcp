"""系统类工具：控制器清单与连通性自检。"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..auth import AuthError
from ..registry import ControllerRegistry
from .common import dump_json, mcp_tool_wrapper, tool_error


def make_anp_controllers(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_controllers(probe: bool = False) -> str:
        """列出所有已配置的 ANP 控制器（名称/地址/账号/是否默认）。
        probe=true 时逐个执行真实登录验证凭据可用性（会产生认证请求）。"""
        infos = registry.info()
        if probe:
            for item in infos:
                try:
                    client = registry.get(item["name"])
                    client.auth.invalidate()
                    await client.auth.login()
                    item["auth"] = "ok"
                except AuthError as exc:
                    item["auth"] = f"failed: {exc}"
                except Exception as exc:  # noqa: BLE001 - 逐项探测不中断整体
                    item["auth"] = f"failed: {exc.__class__.__name__}: {exc}"
        return dump_json({"controllers": infos})
    return anp_controllers


def make_anp_ping(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_ping(controller: str | None = None) -> str:
        """对指定（或默认）ANP 控制器执行一次全新认证，验证地址与凭据是否可用。"""
        client = registry.get(controller)
        client.auth.invalidate()
        try:
            await client.auth.login()
        except AuthError as exc:
            return tool_error(client.profile.name, str(exc))
        return dump_json({"controller": client.profile.name, "status": "ok",
                          "authenticated_as": client.profile.username})
    return anp_ping


def register(mcp: FastMCP, registry: ControllerRegistry) -> None:
    mcp.tool()(make_anp_controllers(registry))
    mcp.tool()(make_anp_ping(registry))
