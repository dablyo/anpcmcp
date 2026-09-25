"""client.py TDD：Bearer 注入、401 重登一次、错误映射。"""
import httpx
import pytest
import respx

from anp_mcp.auth import AUTH_PATH
from anp_mcp.client import AnpClient, ApiError
from conftest import SH

KPI = "/rest/kpi/v1"


def _mock_auth(respx_mock, token="tok", status=200):
    return respx_mock.get(f"https://sh.test{AUTH_PATH}").mock(
        return_value=httpx.Response(status, json={"code": 0, "value": token}))


@respx.mock
async def test_bearer_header_injected():
    _mock_auth(respx, "tok")
    route = respx.get(f"https://sh.test{KPI}").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    client = AnpClient(SH)
    try:
        body = await client.request("GET", KPI)
        assert body == {"code": 0, "value": []}
        assert route.calls.last.request.headers["Authorization"] == "Bearer tok"
    finally:
        await client.aclose()


@respx.mock
async def test_401_relogins_once_then_succeeds():
    auth_route = _mock_auth(respx, "tok2")
    kpi_route = respx.get(f"https://sh.test{KPI}")
    kpi_route.side_effect = [httpx.Response(401),
                             httpx.Response(200, json={"code": 0, "value": [1]})]
    client = AnpClient(SH)
    try:
        assert (await client.request("GET", KPI))["value"] == [1]
        # kpi 恰好 2 次（原请求+重试）证明只重登了一次；auth 共 2 次（初始+重登）
        assert kpi_route.call_count == 2 and auth_route.call_count == 2
    finally:
        await client.aclose()


@respx.mock
async def test_401_after_relogin_raises():
    _mock_auth(respx, "tok")
    respx.get(f"https://sh.test{KPI}").mock(return_value=httpx.Response(401))
    client = AnpClient(SH)
    try:
        with pytest.raises(ApiError, match="401"):
            await client.request("GET", KPI)
    finally:
        await client.aclose()


@respx.mock
async def test_http_500_mapped():
    _mock_auth(respx, "tok")
    respx.get(f"https://sh.test{KPI}").mock(return_value=httpx.Response(500, text="boom"))
    client = AnpClient(SH)
    try:
        with pytest.raises(ApiError) as ei:
            await client.request("GET", KPI)
        assert ei.value.http_status == 500 and ei.value.controller == "sh"
    finally:
        await client.aclose()


@respx.mock
async def test_network_error_no_secrets_in_message():
    respx.get(f"https://sh.test{AUTH_PATH}").mock(side_effect=httpx.ConnectError("refused"))
    client = AnpClient(SH)
    try:
        with pytest.raises(ApiError, match="https://sh.test") as ei:
            await client.request("GET", KPI)
        assert SH.password_md5 not in str(ei.value)
        assert SH.username not in str(ei.value)
    finally:
        await client.aclose()
