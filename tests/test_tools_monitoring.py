"""监控工具 TDD：告警/操作日志/性能指标/KPI + controller 参数路由。"""
import json

import httpx
import pytest
import respx

from anp_mcp.auth import AUTH_PATH
from anp_mcp.registry import ControllerRegistry
from anp_mcp.tools.monitoring import (
    make_anp_alarm_active, make_anp_alarm_cleared, make_anp_alarm_notification,
    make_anp_operlog_query, make_anp_pm_query, make_anp_controller_kpi)
from conftest import SH, BJ


@pytest.fixture
def registry(two_profiles):
    return ControllerRegistry(*two_profiles)


@pytest.fixture
def mock_controller(respx_mock):
    respx_mock.get(f"https://sh.test{AUTH_PATH}").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "tok-sh"}))
    respx_mock.get(f"https://bj.test{AUTH_PATH}").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": "tok-bj"}))
    return respx_mock


async def test_alarm_active_default(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/fm/active/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    out = json.loads(await make_anp_alarm_active(registry)(pageSize=100))
    assert out == {"controller": "sh", "code": 0, "value": []}
    assert route.calls.last.request.url.params["pageSize"] == "100"


async def test_alarm_active_by_deviceid(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/fm/active/v1/dev-1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    await make_anp_alarm_active(registry)(deviceid="dev-1")
    assert route.called


async def test_alarm_cleared(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/fm/cleared/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    await make_anp_alarm_cleared(registry)()
    assert route.called


async def test_alarm_notification(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/fm/notification/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    await make_anp_alarm_notification(registry)()
    assert route.called


async def test_operlog_param_json(registry, mock_controller):
    route = mock_controller.get("https://sh.test/api/maintain/log/queryoperlog").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": {}}))
    await make_anp_operlog_query(registry)(pageSize=50, pageIndex=0, filterType="action",
                                           filterValue="x", actions=["ADD_APP_RULE"])
    param = json.loads(route.calls.last.request.url.params["param"])
    assert param == {"pageSize": 50, "pageIndex": 0, "filterType": "action",
                     "filterValue": "x", "actions": ["ADD_APP_RULE"]}


@pytest.mark.parametrize("metric_type,path", [
    ("port", "/rest/pm/port/v1"),
    ("tunnel", "/rest/pm/tunnel/v1"),
    ("appcat", "/rest/pm/appcat/v1"),
    ("pathquality", "/rest/pm/pathquality/v1"),
    ("sys", "/rest/pm/sys/v1"),
    ("syscpu", "/rest/pm/syscpu/v1"),
    ("sysvol", "/rest/pm/sysvol/v1"),
    ("hybrid", "/rest/pm/hybrid/v1"),
    ("host_hybrid", "/rest/pm/host/hybrid/v1")])
async def test_pm_metric_all_9_types(registry, mock_controller, metric_type, path):
    route = mock_controller.get(f"https://sh.test{path}").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    await make_anp_pm_query(registry)(metric_type=metric_type,
                                      since="2026-09-25 10:00:00",
                                      before="2026-09-25 11:00:00")
    assert route.called


async def test_pm_forwards_tenantid(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/pm/port/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    await make_anp_pm_query(registry)(metric_type="port",
                                      since="2026-09-25 10:00:00",
                                      before="2026-09-25 11:00:00",
                                      tenantid="00000000-0000-0000-0000-000000000000",
                                      pageSize=500)
    q = route.calls.last.request.url.params
    assert q["tenantid"].startswith("0000") and q["pageSize"] == "500"


async def test_pm_unknown_metric_type_error(registry, mock_controller):
    out = json.loads(await make_anp_pm_query(registry)(
        metric_type="bogus", since="s", before="b"))
    assert "error" in out and "port" in out["error"]


async def test_controller_param_routes_to_bj(registry, mock_controller):
    route = mock_controller.get("https://bj.test/rest/kpi/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": [1]}))
    out = json.loads(await make_anp_controller_kpi(registry)(controller="bj"))
    assert out["controller"] == "bj" and route.called


async def test_unknown_controller_error_lists_available(registry, mock_controller):
    out = json.loads(await make_anp_controller_kpi(registry)(controller="nope"))
    assert out["available"] == ["bj", "sh"] and "error" in out


async def test_kpi_default_controller(registry, mock_controller):
    route = mock_controller.get("https://sh.test/rest/kpi/v1").mock(
        return_value=httpx.Response(200, json={"code": 0, "value": []}))
    out = json.loads(await make_anp_controller_kpi(registry)())
    assert out["controller"] == "sh" and route.called
