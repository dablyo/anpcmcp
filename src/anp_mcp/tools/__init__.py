"""工具注册入口。"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..registry import ControllerRegistry


def register_all_tools(mcp: FastMCP, registry: ControllerRegistry) -> None:
    from . import devices, monitoring, resources, system
    monitoring.register(mcp, registry)
    devices.register(mcp, registry)
    resources.register(mcp, registry)
    system.register(mcp, registry)
