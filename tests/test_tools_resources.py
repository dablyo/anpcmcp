"""资源工具 TDD：site/tenant/asset CRUD 工厂 + staticroute 手写工具。"""
import json

import httpx
import pytest
import respx

from anp_mcp.auth import AUTH_PATH
from anp_mcp.registry import ControllerRegistry
from anp_mcp.tools.resources import make_crud_tool, CrudSpec, make_anp_staticroute_ops

SITE = CrudSpec("anp_site_ops", "/rest/site/v1", "站点")
TENANT = CrudSpec("anp_tenant_ops", "/rest/tenant/v1", "租户",
                  actions=("list", "get", "create", "update", "set_quota", "delete"))
ASSET = CrudSpec("anp_asset_ops", "/rest/assets/v1", "设备资产",
                 actions=("list", "get", "create", "update", "get_cert", "delete"))


@pytest.fixture
def registry(two_profiles):
    return ControllerRegistry(*two_profiles)


@pytest.fixture
def mock_controller(respx_mock):
    respx_mock.get(f"https://sh.test{AUTH_PATH}").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "tok"}))
    return respx_mock


async def test_site_list(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/site/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {"siteCount": 0, "sites": []}}))
    await make_crud_tool(registry, SITE)(action="list", pageSize=10)
    assert route.calls.last.request.url.params["pageSize"] == "10"


async def test_site_get(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/site/v1/s1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {"uid": "s1"}}))
    out = json.loads(await make_crud_tool(registry, SITE)(action="get", resource_id="s1"))
    assert out["value"]["uid"] == "s1"


async def test_site_get_requires_id(registry, mock_controller):
    out = json.loads(await make_crud_tool(registry, SITE)(action="get"))
    assert "error" in out and "resource_id" in out["error"]


async def test_site_create_and_update(registry, mock_controller):
    post_route = mock_controller.post("https://sh.test/rest/site/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "new-id"}))
    put_route = mock_controller.put("https://sh.test/rest/site/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": None}))
    await make_crud_tool(registry, SITE)(action="create", body={"name": "a"})
    await make_crud_tool(registry, SITE)(action="update", body={"uid": "x"})
    assert post_route.called and put_route.called


async def test_site_delete(registry, mock_controller):
    route = mock_controller.delete("https://sh.test/rest/site/v1/s1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": None}))
    await make_crud_tool(registry, SITE)(action="delete", resource_id="s1")
    assert route.called


async def test_site_unknown_action(registry, mock_controller):
    out = json.loads(await make_crud_tool(registry, SITE)(action="bogus"))
    assert "error" in out


def test_site_destructive_docstring(registry):
    assert "DESTRUCTIVE" in make_crud_tool(registry, SITE).__doc__


async def test_tenant_set_quota(registry, mock_controller):
    route = mock_controller.put("https://sh.test/rest/tenant/v1/quota").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": None}))
    await make_crud_tool(registry, TENANT)(action="set_quota", body={"maxDevice": 5})
    assert route.called


async def test_asset_get_cert(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/assets/v1/cert").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "CERT"}))
    await make_crud_tool(registry, ASSET)(action="get_cert", extra={"ip": "10.1.203.71"})
    assert route.calls.last.request.url.params["ip"] == "10.1.203.71"


async def test_asset_get_cert_requires_ip(registry, mock_controller):
    out = json.loads(await make_crud_tool(registry, ASSET)(action="get_cert"))
    assert "error" in out and "ip" in out["error"]


async def test_staticroute_list_by_device(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/routeentry/v1/d1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    await make_anp_staticroute_ops(registry)(action="list", device_id="d1")
    assert route.called


async def test_staticroute_create_update(registry, mock_controller):
    post_route = mock_controller.post("https://sh.test/rest/routeentry/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "r1"}))
    put_route = mock_controller.put("https://sh.test/rest/routeentry/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": None}))
    await make_anp_staticroute_ops(registry)(action="create", body={"deviceId": "d1"})
    await make_anp_staticroute_ops(registry)(action="update", body={"uid": "r1"})
    assert post_route.called and put_route.called


async def test_staticroute_delete_double_id(registry, mock_controller):
    route = mock_controller.delete("https://sh.test/rest/routeentry/v1/d1/r1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": None}))
    await make_anp_staticroute_ops(registry)(action="delete", device_id="d1", route_id="r1")
    assert route.called


async def test_staticroute_query_by_subnet(registry, mock_controller):
    route = mock_controller.get("https://sh.test/api/biz/staticroute").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    await make_anp_staticroute_ops(registry)(action="query_by_subnet",
                                             device_id="d1", subnet="172.16.201.0/24")
    q = route.calls.last.request.url.params
    assert q["subnet"] == "172.16.201.0/24" and q["limit"] == "100"


async def test_staticroute_delete_requires_both_ids(registry, mock_controller):
    out = json.loads(await make_anp_staticroute_ops(registry)(action="delete", device_id="d1"))
    assert "error" in out and "route_id" in out["error"]


async def test_staticroute_unknown_action(registry, mock_controller):
    out = json.loads(await make_anp_staticroute_ops(registry)(action="bogus"))
    assert "error" in out


def test_staticroute_destructive_docstring(registry):
    assert "DESTRUCTIVE" in make_anp_staticroute_ops(registry).__doc__
