"""auth.py TDD：登录成功/失败路径与 token 缓存。"""
import httpx
import pytest
import respx

from anp_mcp.auth import AuthClient, AuthError
from conftest import SH

AUTH_URL = "https://sh.test/public/authenticate/v1"


def _client(http: httpx.AsyncClient) -> AuthClient:
    return AuthClient(SH, http)


@respx.mock
async def test_login_success_and_cache():
    route = respx.get(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "tok123"}))
    async with httpx.AsyncClient(base_url=SH.base_url) as http:
        auth = _client(http)
        assert await auth.login() == "tok123"
        assert await auth.ensure_token() == "tok123"
    assert route.call_count == 1


@respx.mock
async def test_login_sends_md5_password():
    route = respx.get(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "t"}))
    async with httpx.AsyncClient(base_url=SH.base_url) as http:
        await _client(http).login()
    assert route.calls.last.request.url.params["username"] == SH.username
    assert route.calls.last.request.url.params["password"] == SH.password_md5


@respx.mock
async def test_login_wrong_password():
    respx.get(AUTH_URL).mock(return_value=httpx.Response(200, json={"code": 604}))
    async with httpx.AsyncClient(base_url=SH.base_url) as http:
        with pytest.raises(AuthError, match="wrong password"):
            await _client(http).login()


@respx.mock
async def test_login_user_not_found():
    respx.get(AUTH_URL).mock(return_value=httpx.Response(200, json={"code": 3}))
    async with httpx.AsyncClient(base_url=SH.base_url) as http:
        with pytest.raises(AuthError, match="user not found"):
            await _client(http).login()


@respx.mock
async def test_login_http_401():
    respx.get(AUTH_URL).mock(return_value=httpx.Response(401))
    async with httpx.AsyncClient(base_url=SH.base_url) as http:
        with pytest.raises(AuthError, match="401"):
            await _client(http).login()


@respx.mock
async def test_login_network_error():
    respx.get(AUTH_URL).mock(side_effect=httpx.ConnectError("refused"))
    async with httpx.AsyncClient(base_url=SH.base_url) as http:
        with pytest.raises(AuthError, match="cannot reach controller"):
            await _client(http).login()


@respx.mock
async def test_invalidate_forces_relogin():
    route = respx.get(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "t"}))
    async with httpx.AsyncClient(base_url=SH.base_url) as http:
        auth = _client(http)
        await auth.ensure_token()
        auth.invalidate()
        await auth.ensure_token()
    assert route.call_count == 2
