"""设备管理工具（业务分册 3.7）：列表/详情/写操作分发。"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..registry import ControllerRegistry
from .common import fmt_result, mcp_tool_wrapper, tool_error

WRITE_ACTIONS = ("create", "update", "set_bandwidth", "set_admin", "restart", "delete")


def make_anp_device_list(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_device_list(pageNo: int | None = None, pageSize: int | None = None,
                              tenantId: str | None = None, siteId: str | None = None,
                              controller: str | None = None) -> str:
        """读取 ANP 控制器设备列表。可选分页 pageNo/pageSize 与 tenantId/siteId 过滤
        （tenantId 传全零 UUID 表示查询运营方设备，不传查全部）。"""
        client = registry.get(controller)
        params = {k: v for k, v in {"pageNo": pageNo, "pageSize": pageSize,
                                    "tenantId": tenantId, "siteId": siteId}.items()
                  if v is not None}
        return fmt_result(client.profile.name,
                          await client.request("GET", "/rest/device/v1",
                                               params=params or None))
    return anp_device_list


def make_anp_device_get(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_device_get(device_id: str, detail: str = "info",
                             controller: str | None = None) -> str:
        """读取设备详情（detail=info）、运行状态（detail=status）或两者合并（detail=all）。"""
        client = registry.get(controller)
        if detail not in ("info", "status", "all"):
            return tool_error(client.profile.name, "detail must be one of: info, status, all")
        if detail == "status":
            return fmt_result(client.profile.name,
                              await client.request("GET", f"/rest/device/v1/status/{device_id}"))
        info = await client.request("GET", f"/rest/device/v1/{device_id}")
        if detail == "info":
            return fmt_result(client.profile.name, info)
        status = await client.request("GET", f"/rest/device/v1/status/{device_id}")
        return fmt_result(client.profile.name, {
            "code": info.get("code", 0),
            "value": {"info": info.get("value"), "status": status.get("value")}})
    return anp_device_get


def make_anp_device_write(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_device_write(action: str, device_id: str | None = None,
                               body: dict | None = None,
                               controller: str | None = None) -> str:
        """设备写操作分发。DESTRUCTIVE：restart（重启设备）、delete（删除设备）不可逆，慎用。
        action 取值：create（body=设备对象）/ update（body）/ set_bandwidth（body）/
        set_admin（body）/ restart（需 device_id，DESTRUCTIVE）/ delete（需 device_id，
        DESTRUCTIVE）。body 字段结构见 API 说明书设备管理章节。"""
        client = registry.get(controller)
        action = action.strip().lower()
        if action not in WRITE_ACTIONS:
            return tool_error(client.profile.name,
                              f"unknown action '{action}'; valid: {', '.join(WRITE_ACTIONS)}")
        if action in ("restart", "delete") and not device_id:
            return tool_error(client.profile.name, f"action '{action}' requires device_id")
        if action in ("create", "update", "set_bandwidth", "set_admin") and body is None:
            return tool_error(client.profile.name, f"action '{action}' requires body object")
        method, url = {
            "create": ("POST", "/rest/device/v1"),
            "update": ("PUT", "/rest/device/v1"),
            "set_bandwidth": ("PUT", "/rest/device/v1/bandwidth"),
            "set_admin": ("PUT", "/rest/device/v1/admin"),
            "restart": ("PUT", f"/rest/device/v1/restart/{device_id}"),
            "delete": ("DELETE", f"/rest/device/v1/{device_id}"),
        }[action]
        return fmt_result(client.profile.name,
                          await client.request(method, url, json_body=body))
    return anp_device_write


def register(mcp: FastMCP, registry: ControllerRegistry) -> None:
    for factory in (make_anp_device_list, make_anp_device_get, make_anp_device_write):
        mcp.tool()(factory(registry))
