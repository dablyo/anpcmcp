"""单控制器连接：httpx 封装 + Bearer 注入 + 401 重登一次 + 统一错误映射。

错误信息只含控制器地址/名称，绝不含凭据。
"""
from __future__ import annotations

import logging

import httpx

from .auth import AuthClient, AuthError
from .config import ControllerProfile

logger = logging.getLogger("anp_mcp.client")


class ApiError(Exception):
    """对 LLM 可读的接口错误。"""

    def __init__(self, message: str, *, controller: str,
                 http_status: int | None = None, code: int | None = None):
        super().__init__(message)
        self.controller = controller
        self.http_status = http_status
        self.code = code


class AnpClient:
    """一个控制器 profile = 一条 httpx 连接 + 独立登录态。"""

    def __init__(self, profile: ControllerProfile):
        self.profile = profile
        self._http = httpx.AsyncClient(base_url=profile.base_url,
                                       verify=profile.verify_ssl,
                                       timeout=profile.timeout)
        self.auth = AuthClient(profile, self._http)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def request(self, method: str, path: str, *,
                      params: dict | None = None,
                      json_body: object | None = None) -> dict:
        """带认证请求，返回控制器原始 {code, value}。

        401 → 重登一次并重试；仍 401 → ApiError(401)。
        """
        try:
            await self.auth.ensure_token()
        except AuthError as exc:
            raise ApiError(str(exc), controller=self.profile.name) from exc
        resp: httpx.Response | None = None
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {self.auth.token}"}
            try:
                resp = await self._http.request(method, path, params=params,
                                                json=json_body, headers=headers)
            except httpx.HTTPError as exc:
                raise ApiError(f"request to {self.profile.base_url}{path} failed: "
                               f"{exc.__class__.__name__}",
                               controller=self.profile.name) from exc
            if resp.status_code == 401 and attempt == 1:
                logger.debug("401 on %s%s; re-authenticating once",
                             self.profile.base_url, path)
                self.auth.invalidate()
                try:
                    await self.auth.login()
                except AuthError as exc:
                    raise ApiError(str(exc), http_status=401,
                                   controller=self.profile.name) from exc
                continue
            break
        return self._parse(resp, path)

    def _parse(self, resp: httpx.Response, path: str) -> dict:
        name = self.profile.name
        if resp.status_code == 401:
            raise ApiError(f"authentication failed for controller '{name}' "
                           f"after re-login (401)", http_status=401, controller=name)
        if resp.status_code != 200:
            detail = (resp.text or "")[:200]
            raise ApiError(f"{path} returned HTTP {resp.status_code}"
                           + (f": {detail}" if detail else ""),
                           http_status=resp.status_code, controller=name)
        try:
            body = resp.json()
        except ValueError as exc:
            raise ApiError(f"{path} returned non-JSON body", controller=name) from exc
        if not isinstance(body, dict):
            raise ApiError(f"{path} returned unexpected JSON structure",
                           controller=name)
        return body
