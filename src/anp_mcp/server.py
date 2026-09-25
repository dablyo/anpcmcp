"""FastMCP 组装入口。"""
from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .registry import ControllerRegistry
from .tools import register_all_tools


def create_server() -> FastMCP:
    """读配置 → 建注册表 → 注册 15 个工具。配置非法直接抛异常（fail-fast）。"""
    level = os.environ.get("ANP_LOG_LEVEL", "WARNING").upper()
    logging.basicConfig(level=getattr(logging, level, logging.WARNING),
                        format="%(levelname)s %(name)s: %(message)s")
    profiles, default_name = load_config()
    registry = ControllerRegistry(profiles, default_name)
    mcp = FastMCP("anp-controller")
    register_all_tools(mcp, registry)
    return mcp


def main() -> None:
    create_server().run()  # 默认 stdio 传输


if __name__ == "__main__":
    main()
