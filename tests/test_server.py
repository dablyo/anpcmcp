"""server 组装 TDD：15 工具全注册、DESTRUCTIVE 进 schema、系统工具行为。"""
import json

import httpx
import pytest
import respx

from anp_mcp.auth import AUTH_PATH
from anp_mcp.registry import ControllerRegistry
from anp_mcp.server import create_server
from anp_mcp.tools.system import make_anp_controllers, make_anp_ping
from conftest import SH, BJ

ENV = {"ANP_BASE_URL": "https://sh.test", "ANP_USERNAME": "admin", "ANP_PASSWORD": "pw"}

EXPECTED_TOOLS = {
    "anp_alarm_active", "anp_alarm_cleared", "anp_alarm_notification",
    "anp_operlog_query", "anp_pm_query", "anp_controller_kpi",
    "anp_device_list", "anp_device_get", "anp_device_write",
    "anp_asset_ops", "anp_site_ops", "anp_tenant_ops", "anp_staticroute_ops",
    "anp_controllers", "anp_ping"}


async def test_all_15_tools_registered(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    mcp = create_server()
    tools = {t.name for t in await mcp.list_tools()}
    assert tools == EXPECTED_TOOLS


async def test_destructive_marked_in_schema(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    mcp = create_server()
    desc = next(t.description for t in await mcp.list_tools()
                if t.name == "anp_device_write")
    assert "DESTRUCTIVE" in desc


async def test_tool_has_controller_param(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    mcp = create_server()
    tool = next(t for t in await mcp.list_tools() if t.name == "anp_alarm_active")
    assert "controller" in tool.inputSchema.get("properties", {})


@respx.mock
async def test_anp_controllers_probe(registry_with_mocks):
    out = json.loads(await make_anp_controllers(registry_with_mocks[0])(probe=True))
    auth = {c["name"]: c["auth"] for c in out["controllers"]}
    assert auth["sh"] == "ok" and auth["bj"].startswith("failed")


@respx.mock
async def test_anp_controllers_no_probe_lists_config(registry_with_mocks):
    out = json.loads(await make_anp_controllers(registry_with_mocks[0])())
    assert {c["name"] for c in out["controllers"]} == {"sh", "bj"}
    assert all("auth" not in c for c in out["controllers"])


@respx.mock
async def test_anp_ping_ok_and_fail(registry_with_mocks):
    registry = registry_with_mocks[0]
    out = json.loads(await make_anp_ping(registry)())
    assert out == {"controller": "sh", "status": "ok", "authenticated_as": "admin"}
    # 密码错误场景：重置 mock 为业务错误码
    respx.get("https://sh.test" + AUTH_PATH).mock(
        return_value=httpx.Response(200, json={"code": 604}))
    out = json.loads(await make_anp_ping(registry)())
    assert "error" in out and "wrong password" in out["error"]


@pytest.fixture
def registry_with_mocks(two_profiles, respx_mock):
    respx_mock.get("https://sh.test" + AUTH_PATH).mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "t1"}))
    respx_mock.get("https://bj.test" + AUTH_PATH).mock(
        return_value=httpx.Response(401))
    return ControllerRegistry(*two_profiles), respx_mock
