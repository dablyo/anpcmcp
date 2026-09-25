"""多控制器连接注册表：按名懒加载连接，每连接独立登录态。"""
from __future__ import annotations

from .client import AnpClient
from .config import ControllerProfile


class UnknownControllerError(KeyError):
    """请求了未配置的控制器名。available 供 LLM/用户选择正确名称。"""

    def __init__(self, name: str, available: list[str]):
        self.name = name
        self.available = available
        super().__init__(f"unknown controller '{name}'; available controllers: "
                         f"{', '.join(available)}")


class ControllerRegistry:
    """持有全部 ControllerProfile；连接按需创建、按名复用。"""

    def __init__(self, profiles: list[ControllerProfile], default_name: str):
        self._profiles = {p.name: p for p in profiles}
        if default_name not in self._profiles:
            raise ValueError(f"default controller '{default_name}' not in profiles")
        self._default_name = default_name
        self._clients: dict[str, AnpClient] = {}

    @property
    def default_name(self) -> str:
        return self._default_name

    def names(self) -> list[str]:
        return sorted(self._profiles)

    def get(self, name: str | None = None) -> AnpClient:
        """取连接。name 为空用 default；未知名抛 UnknownControllerError。"""
        key = name or self._default_name
        if key not in self._profiles:
            raise UnknownControllerError(key, self.names())
        if key not in self._clients:
            self._clients[key] = AnpClient(self._profiles[key])
        return self._clients[key]

    def info(self) -> list[dict]:
        """全部控制器的非敏感元数据（无凭据）。"""
        return [{"name": p.name,
                 "base_url": p.base_url,
                 "username": p.username,
                 "is_default": p.name == self._default_name,
                 "verify_ssl": p.verify_ssl,
                 "timeout": p.timeout}
                for p in (self._profiles[n] for n in self.names())]

    async def aclose_all(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
