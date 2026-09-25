"""资源域工具：site/tenant/asset 走 CRUD 工厂；staticroute 手写（接口形态特殊：
deviceId 在 path、delete 需设备+路由双 ID、另有 /api/biz/staticroute 子网查询）。"""
from __future__ import annotations

from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from ..client import AnpClient
from ..registry import ControllerRegistry
from .common import fmt_result, mcp_tool_wrapper, tool_error


@dataclass(frozen=True)
class CrudSpec:
    tool_name: str
    base_path: str
    noun: str                                   # 中文资源名，进 docstring
    actions: tuple[str, ...] = ("list", "get", "create", "update", "delete")


def _apply_standard_action(client: AnpClient, spec: CrudSpec, action: str,
                           resource_id: str | None, body: dict | None,
                           list_params: dict | None):
    """list/get/create/update/delete 五个标准 action 的 method/path/payload 分发。"""
    if action in ("get", "delete") and not resource_id:
        return tool_error(client.profile.name, f"action '{action}' requires resource_id")
    if action in ("create", "update") and body is None:
        return tool_error(client.profile.name, f"action '{action}' requires body object")
    method, url, payload = {
        "list": ("GET", spec.base_path, None),
        "get": ("GET", f"{spec.base_path}/{resource_id}", None),
        "create": ("POST", spec.base_path, body),
        "update": ("PUT", spec.base_path, body),
        "delete": ("DELETE", f"{spec.base_path}/{resource_id}", None),
    }[action]
    return client.request(method, url, params=list_params if action == "list" else None,
                          json_body=payload)


def make_crud_tool(registry: ControllerRegistry, spec: CrudSpec):
    destructive = ("DESTRUCTIVE: delete 不可逆，慎用。" if "delete" in spec.actions else "")
    extras = [a for a in spec.actions if a not in ("list", "get", "create", "update", "delete")]
    extras_note = "；扩展 action：" + "、".join(
        f"{a}" + ("（body=对象）" if a == "set_quota" else "（extra={'ip': ...}）" if a == "get_cert" else "")
        for a in extras) if extras else ""

    @mcp_tool_wrapper
    async def tool(action: str, resource_id: str | None = None, body: dict | None = None,
                   pageNo: int | None = None, pageSize: int | None = None,
                   tenantId: str | None = None, extra: dict | None = None,
                   controller: str | None = None) -> str:
        """{spec.noun}管理。action 取值：{action_list}。{destructive}{extras_note}
        list 支持 pageNo/pageSize/tenantId 过滤；get/delete 需 resource_id；
        create/update 需 body 对象（字段结构见 API 说明书对应章节）。"""
        client = registry.get(controller)
        action = action.strip().lower()
        if action not in spec.actions:
            return tool_error(client.profile.name,
                              f"unknown action '{action}'; valid: {', '.join(spec.actions)}")
        if action == "set_quota":
            if body is None:
                return tool_error(client.profile.name,
                                  "action 'set_quota' requires body object")
            return fmt_result(client.profile.name, await client.request(
                "PUT", f"{spec.base_path}/quota", json_body=body))
        if action == "get_cert":
            ip = (extra or {}).get("ip")
            if not ip:
                return tool_error(client.profile.name,
                                  "action 'get_cert' requires extra={'ip': ...}")
            return fmt_result(client.profile.name, await client.request(
                "GET", f"{spec.base_path}/cert", params={"ip": ip}))
        list_params = {k: v for k, v in {"pageNo": pageNo, "pageSize": pageSize,
                                         "tenantId": tenantId}.items() if v is not None}
        result = _apply_standard_action(client, spec, action, resource_id,
                                        body, list_params or None)
        if isinstance(result, str):  # 参数校验失败的 tool_error，非协程
            return result
        return fmt_result(client.profile.name, await result)

    action_list = ", ".join(spec.actions)
    tool.__name__ = spec.tool_name
    tool.__doc__ = tool.__doc__.format(spec=spec, action_list=action_list,
                                       destructive=destructive, extras_note=extras_note)
    return tool


def make_anp_staticroute_ops(registry: ControllerRegistry):
    @mcp_tool_wrapper
    async def anp_staticroute_ops(action: str, device_id: str | None = None,
                                  route_id: str | None = None, body: dict | None = None,
                                  subnet: str | None = None, limit: int | None = None,
                                  controller: str | None = None) -> str:
        """静态路由管理。DESTRUCTIVE: delete 不可逆，慎用。
        action：list（需 device_id）/ create（body）/ update（body）/
        delete（需 device_id + route_id，DESTRUCTIVE）/ query_by_subnet
        （需 device_id + subnet，走 /api/biz/staticroute，limit 默认 100）。
        body 字段结构见 API 说明书静态路由管理章节。"""
        client = registry.get(controller)
        action = action.strip().lower()
        if action == "list":
            if not device_id:
                return tool_error(client.profile.name, "action 'list' requires device_id")
            return fmt_result(client.profile.name,
                              await client.request("GET", f"/rest/routeentry/v1/{device_id}"))
        if action == "create":
            if body is None:
                return tool_error(client.profile.name, "action 'create' requires body object")
            return fmt_result(client.profile.name,
                              await client.request("POST", "/rest/routeentry/v1",
                                                   json_body=body))
        if action == "update":
            if body is None:
                return tool_error(client.profile.name, "action 'update' requires body object")
            return fmt_result(client.profile.name,
                              await client.request("PUT", "/rest/routeentry/v1",
                                                   json_body=body))
        if action == "delete":
            if not (device_id and route_id):
                return tool_error(client.profile.name,
                                  "action 'delete' requires device_id and route_id")
            return fmt_result(client.profile.name, await client.request(
                "DELETE", f"/rest/routeentry/v1/{device_id}/{route_id}"))
        if action == "query_by_subnet":
            if not (device_id and subnet):
                return tool_error(client.profile.name,
                                  "action 'query_by_subnet' requires device_id and subnet")
            return fmt_result(client.profile.name, await client.request(
                "GET", "/api/biz/staticroute",
                params={"deviceId": device_id, "subnet": subnet, "limit": limit or 100}))
        return tool_error(client.profile.name,
                          f"unknown action '{action}'; valid: list, create, update, "
                          f"delete, query_by_subnet")
    return anp_staticroute_ops


def register(mcp: FastMCP, registry: ControllerRegistry) -> None:
    for spec in (
        CrudSpec("anp_site_ops", "/rest/site/v1", "站点"),
        CrudSpec("anp_tenant_ops", "/rest/tenant/v1", "租户",
                 actions=("list", "get", "create", "update", "set_quota", "delete")),
        CrudSpec("anp_asset_ops", "/rest/assets/v1", "设备资产",
                 actions=("list", "get", "create", "update", "get_cert", "delete")),
    ):
        mcp.tool()(make_crud_tool(registry, spec))
    mcp.tool()(make_anp_staticroute_ops(registry))
