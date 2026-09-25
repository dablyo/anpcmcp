"""设备工具 TDD：list/get/write 三件套与 DESTRUCTIVE 标注。"""
import json

import httpx
import pytest
import respx

from anp_mcp.auth import AUTH_PATH
from anp_mcp.registry import ControllerRegistry
from anp_mcp.tools.devices import (
    make_anp_device_list, make_anp_device_get, make_anp_device_write)


@pytest.fixture
def registry(two_profiles):
    return ControllerRegistry(*two_profiles)


@pytest.fixture
def mock_controller(respx_mock):
    respx_mock.get(f"https://sh.test{AUTH_PATH}").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "tok"}))
    return respx_mock


async def test_device_list_filters(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/device/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {"deviceCount": 0, "devices": []}}))
    await make_anp_device_list(registry)(pageNo=0, pageSize=10,
                                         tenantId="00000000-0000-0000-0000-000000000000")
    q = route.calls.last.request.url.params
    assert q["pageNo"] == "0" and q["tenantId"].startswith("0000")


async def test_device_get_info(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/device/v1/d1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {"deviceId": "d1"}}))
    out = json.loads(await make_anp_device_get(registry)(device_id="d1"))
    assert out["value"]["deviceId"] == "d1" and route.called


async def test_device_get_status(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/device/v1/status/d1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {"state": 0}}))
    out = json.loads(await make_anp_device_get(registry)(device_id="d1", detail="status"))
    assert out["value"]["state"] == 0


async def test_device_get_all_merges(registry, mock_controller):
    mock_controller.get("https://sh.test/rest/device/v1/d1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {"deviceId": "d1"}}))
    mock_controller.get("https://sh.test/rest/device/v1/status/d1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {"state": 1}}))
    out = json.loads(await make_anp_device_get(registry)(device_id="d1", detail="all"))
    assert out["value"] == {"info": {"deviceId": "d1"}, "status": {"state": 1}}


async def test_device_get_bad_detail(registry, mock_controller):
    out = json.loads(await make_anp_device_get(registry)(device_id="d1", detail="bogus"))
    assert "error" in out


@pytest.mark.parametrize("action,method,url", [
    ("create", "POST", "https://sh.test/rest/device/v1"),
    ("update", "PUT", "https://sh.test/rest/device/v1"),
    ("set_bandwidth", "PUT", "https://sh.test/rest/device/v1/bandwidth"),
    ("set_admin", "PUT", "https://sh.test/rest/device/v1/admin"),
    ("restart", "PUT", "https://sh.test/rest/device/v1/restart/d1"),
    ("delete", "DELETE", "https://sh.test/rest/device/v1/d1")])
async def test_device_write_actions(registry, mock_controller, action, method, url):
    route = mock_controller.request(method.upper(), url).mock(
        return_value=httpx.Response(200, json={"code": 0, "value": None}))
    kwargs = {"device_id": "d1"} if action in ("restart", "delete") else {"body": {"x": 1}}
    out = json.loads(await make_anp_device_write(registry)(action=action, **kwargs))
    assert out["code"] == 0 and route.called


async def test_device_write_requires_args(registry, mock_controller):
    out = json.loads(await make_anp_device_write(registry)(action="delete"))
    assert "error" in out and "device_id" in out["error"]
    out = json.loads(await make_anp_device_write(registry)(action="create"))
    assert "error" in out and "body" in out["error"]


async def test_device_write_unknown_action(registry, mock_controller):
    out = json.loads(await make_anp_device_write(registry)(action="bogus"))
    assert "error" in out


def test_destructive_marked_in_docstring(registry):
    assert "DESTRUCTIVE" in make_anp_device_write(registry).__doc__
