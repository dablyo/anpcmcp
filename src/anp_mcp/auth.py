"""ANP 控制器认证：GET /public/authenticate/v1?username=&password=<MD5>（业务分册 3.3）。

- 认证成功：HTTP 200 + {code: 0, value: <token>}，token 存内存。
- 失败：HTTP 401，或业务 code 非 0（3=用户不存在，604=密码错误）。
"""
from __future__ import annotations

import logging

import httpx

from .config import ControllerProfile

logger = logging.getLogger("anp_mcp.auth")

AUTH_PATH = "/public/authenticate/v1"

_CODE_HINTS = {3: "user not found", 604: "wrong password"}


class AuthError(Exception):
    """认证失败。错误信息不含凭据。"""


class AuthClient:
    """单个控制器连接的登录态（token 仅存内存，进程退出即失效）。"""

    def __init__(self, profile: ControllerProfile, http: httpx.AsyncClient):
        self._profile = profile
        self._http = http
        self._token: str | None = None

    @property
    def token(self) -> str | None:
        return self._token

    def invalidate(self) -> None:
        self._token = None

    async def login(self) -> str:
        """全新登录，成功后缓存并返回 JWT；失败抛 AuthError。"""
        params = {"username": self._profile.username,
                  "password": self._profile.password_md5}
        try:
            resp = await self._http.get(AUTH_PATH, params=params)
        except httpx.HTTPError as exc:
            raise AuthError(f"cannot reach controller {self._profile.base_url}: "
                            f"{exc.__class__.__name__}") from exc
        if resp.status_code == 401:
            raise AuthError(f"authentication failed for user "
                            f"'{self._profile.username}' (401)")
        if resp.status_code != 200:
            raise AuthError(f"authentication endpoint returned HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError as exc:
            raise AuthError("authentication endpoint returned non-JSON body") from exc
        code = body.get("code")
        if code != 0:
            detail = _CODE_HINTS.get(code, f"code={code}")
            raise AuthError(f"authentication rejected for user "
                            f"'{self._profile.username}': {detail}")
        token = body.get("value")
        if not token or not isinstance(token, str):
            raise AuthError("authentication response missing token in 'value'")
        self._token = token
        logger.debug("logged in to %s as %s", self._profile.base_url, self._profile.username)
        return token

    async def ensure_token(self) -> str:
        if self._token:
            return self._token
        return await self.login()
