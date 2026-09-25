"""监控类工具：告警/操作日志/性能指标/控制器 KPI（故障性能分册全部只读接口）。

所有工具均带可选 controller 参数选择目标控制器（省略用 default）。
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from ..registry import ControllerRegistry
from .common import fmt_result, mcp_tool_wrapper, tool_error

# metric_type → 后端路径（host_hybrid 路径为两段）
PM_METRIC_PATHS = {
    "port": "/rest/pm/port/v1",
    "tunnel": "/rest/pm/tunnel/v1",
    "appcat": "/rest/pm/appcat/v1",
    "pathquality": "/rest/pm/pathquality/v1",
    "sys": "/rest/pm/sys/v1",
    "syscpu": "/rest/pm/syscpu/v1",
    "sysvol": "/rest/pm/sysvol/v1",
    "hybrid": "/rest/pm/hybrid/v1",
    "host_hybrid": "/rest/pm/host/hybrid/v1",
}


def make_anp_alarm_active(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_alarm_active(deviceid: str | None = None,
                               pageSize: int | None = None,
                               controller: str | None = None) -> str:
        """读取 ANP 控制器当前激活告警列表。可选 deviceid 过滤指定设备、pageSize 页大小。"""
        client = registry.get(controller)
        params = {"pageSize": pageSize} if pageSize is not None else None
        path = f"/rest/fm/active/v1/{deviceid}" if deviceid else "/rest/fm/active/v1"
        return fmt_result(client.profile.name,
                          await client.request("GET", path, params=params))
    return anp_alarm_active


def make_anp_alarm_cleared(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_alarm_cleared(pageSize: int | None = None,
                                controller: str | None = None) -> str:
        """读取 ANP 控制器已恢复（清除）告警列表。"""
        client = registry.get(controller)
        params = {"pageSize": pageSize} if pageSize is not None else None
        return fmt_result(client.profile.name,
                          await client.request("GET", "/rest/fm/cleared/v1", params=params))
    return anp_alarm_cleared


def make_anp_alarm_notification(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_alarm_notification(pageSize: int | None = None,
                                     controller: str | None = None) -> str:
        """读取 ANP 控制器通知消息列表。"""
        client = registry.get(controller)
        params = {"pageSize": pageSize} if pageSize is not None else None
        return fmt_result(client.profile.name,
                          await client.request("GET", "/rest/fm/notification/v1",
                                               params=params))
    return anp_alarm_notification


def make_anp_operlog_query(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_operlog_query(pageSize: int | None = None, pageIndex: int | None = None,
                                filterType: str | None = None,
                                filterValue: str | None = None,
                                actions: list[str] | None = None,
                                controller: str | None = None) -> str:
        """条件查询 ANP 控制器操作日志。filterType 取值 username/ip/position/action；
        filterType=action 时配合 actions 列表过滤；pageSize/pageIndex 分页。"""
        client = registry.get(controller)
        param: dict = {}
        if pageSize is not None:
            param["pageSize"] = pageSize
        if pageIndex is not None:
            param["pageIndex"] = pageIndex
        if filterType is not None:
            param["filterType"] = filterType
        if filterValue is not None:
            param["filterValue"] = filterValue
        if actions:
            param["actions"] = actions
        return fmt_result(client.profile.name, await client.request(
            "GET", "/api/maintain/log/queryoperlog",
            params={"param": json.dumps(param)}))
    return anp_operlog_query


def make_anp_pm_query(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_pm_query(metric_type: str, since: str, before: str,
                           tenantid: str | None = None, pageSize: int | None = None,
                           controller: str | None = None) -> str:
        """读取 ANP 控制器性能指标。metric_type 必填，取值：
        port(端口)/tunnel(隧道)/appcat(应用分类)/pathquality(隧道质量)/sys(系统)/
        syscpu(系统CPU)/sysvol(系统文件系统)/hybrid(转发面设备混合)/host_hybrid(主机混合)。
        since/before 必填，格式 YYYY-MM-DD HH:MM:SS；tenantid/pageSize 可选。"""
        if metric_type not in PM_METRIC_PATHS:
            return tool_error(controller or registry.default_name,
                              f"unknown metric_type '{metric_type}'; valid: "
                              f"{', '.join(PM_METRIC_PATHS)}")
        client = registry.get(controller)
        params: dict = {"since": since, "before": before}
        if tenantid is not None:
            params["tenantid"] = tenantid
        if pageSize is not None:
            params["pageSize"] = pageSize
        return fmt_result(client.profile.name,
                          await client.request("GET", PM_METRIC_PATHS[metric_type],
                                               params=params))
    return anp_pm_query


def make_anp_controller_kpi(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_controller_kpi(controller: str | None = None) -> str:
        """读取 ANP 控制器关键 KPI：Controller/Tenant/vCPE/CPE 的离线、故障、正常、总数。"""
        client = registry.get(controller)
        return fmt_result(client.profile.name,
                          await client.request("GET", "/rest/kpi/v1"))
    return anp_controller_kpi


def register(mcp: FastMCP, registry: ControllerRegistry) -> None:
    for factory in (make_anp_alarm_active, make_anp_alarm_cleared,
                    make_anp_alarm_notification, make_anp_operlog_query,
                    make_anp_pm_query, make_anp_controller_kpi):
        mcp.tool()(factory(registry))
