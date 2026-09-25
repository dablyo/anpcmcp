# anp-mcp

ANP SDN 控制器北向 REST API 的 MCP（Model Context Protocol）Server。让 WorkBuddy、Claude Code、OpenClaw 等任意 stdio MCP 客户端直接查告警、看性能、管设备、配路由。

支持**单控制器**与**多控制器**两种部署形态；凭据经环境变量注入，token 仅存内存，日志不泄敏。

> 📖 完整部署手册（WorkBuddy 桌面 / Claude Code CLI / OpenClaw+Telegram 多 bot、单/多实例、切换控制器）见 **[GUIDE.md](GUIDE.md)**。

## 工具清单（15 个）

| 工具 | 说明 | 备注 |
|------|------|------|
| `anp_alarm_active` | 激活告警列表（可按设备过滤） | 只读 |
| `anp_alarm_cleared` | 已恢复告警列表 | 只读 |
| `anp_alarm_notification` | 通知消息列表 | 只读 |
| `anp_operlog_query` | 操作日志条件查询 | 只读 |
| `anp_pm_query` | 性能指标（port/tunnel/appcat/pathquality/sys/syscpu/sysvol/hybrid/host_hybrid 九类） | 只读 |
| `anp_controller_kpi` | 控制器/租户/CPE/vCPE 在线与故障统计 | 只读 |
| `anp_device_list` | 设备列表（分页/租户/站点过滤） | 只读 |
| `anp_device_get` | 设备详情 / 运行状态 / 合并 | 只读 |
| `anp_device_write` | 设备 create/update/set_bandwidth/set_admin/**restart**/**delete** | restart、delete 为 DESTRUCTIVE |
| `anp_site_ops` | 站点 CRUD | delete 为 DESTRUCTIVE |
| `anp_tenant_ops` | 租户 CRUD + set_quota | delete 为 DESTRUCTIVE |
| `anp_asset_ops` | 设备资产 CRUD + get_cert | delete 为 DESTRUCTIVE |
| `anp_staticroute_ops` | 静态路由 CRUD + 子网查询 | delete 为 DESTRUCTIVE |
| `anp_controllers` | 列出已配置控制器（probe=true 可验证凭据） | 本地/认证 |
| `anp_ping` | 指定控制器连通性自检（全新登录验证） | 认证 |

所有工具均带可选 `controller` 参数（多控制器模式下选择目标，省略用 default）。返回值为 JSON 字符串：控制器原始 `{code, value}` + `controller` 字段；错误时含 `error`/`httpStatus`/`available` 等字段。

DESTRUCTIVE 操作在工具描述中显式标注，交由客户端权限系统（Claude Code 权限确认、WorkBuddy 操作确认等）拦截。

## 安装

```bash
pip install anp-mcp          # 或源码目录 pip install -e .
```

要求 Python ≥ 3.10；依赖 `mcp`（v1，FastMCP）、`httpx`、`python-dotenv`。

## 配置：三种凭据来源（可共存，优先级从高到低）

### 1. `ANP_CONTROLLERS` 内联 JSON（免文件）

适合客户端只能注入环境变量的场景。内容同下方 controllers.json。

### 2. `ANP_CONTROLLERS_FILE` 指向 JSON 文件（推荐）

文件放用户目录（如 `~/.anp-mcp/controllers.json`），勿放项目目录；POSIX 下 `chmod 600`。

```json
{
  "default": "shanghai",
  "controllers": {
    "shanghai": {
      "base_url": "https://10.1.203.3:8443",
      "username": "admin",
      "password": "yourpass"
    },
    "beijing": {
      "base_url": "https://10.1.204.125:8443",
      "username": "ops",
      "password_md5": "21232f297a57a5a743894a0e4a801fc3"
    }
  }
}
```

字段：`base_url`、`username` 必填；`password`（明文，运行时自动 MD5）或 `password_md5` 二选一；`verify_ssl`（默认 false，自签证书场景）、`timeout`（默认 30 秒）可选。

### 3. 单控制器环境变量（隐式 default）

| 变量 | 说明 |
|------|------|
| `ANP_BASE_URL` | 控制器地址（含端口，不含路径） |
| `ANP_USERNAME` | 用户名 |
| `ANP_PASSWORD` | 明文密码（自动 MD5） |
| `ANP_PASSWORD_MD5` | 已 MD5 密码（与上面二选一，优先） |
| `ANP_VERIFY_SSL` | 默认 false |
| `ANP_TIMEOUT` | 默认 30 |
| `ANP_LOG_LEVEL` | 默认 WARNING（日志永不输出凭据/token） |

加载顺序：进程环境变量 > 项目目录 `.env` 文件（模板见 `.env.example`）。缺必填项启动即报错，不回显任何凭据值。

## 接入示例

### 模式 A：每控制器一个 server 实例（多 bot 场景首选，隔离最干净）

**Claude Code**：

```bash
claude mcp add anp-sh \
  -e ANP_BASE_URL=https://10.1.203.3:8443 \
  -e ANP_USERNAME=admin -e ANP_PASSWORD=yourpass \
  -- python -m anp_mcp

claude mcp add anp-bj \
  -e ANP_BASE_URL=https://10.1.204.125:8443 \
  -e ANP_USERNAME=ops -e ANP_PASSWORD=otherpass \
  -- python -m anp_mcp
```

**OpenClaw + Telegram 多 bot**：每个 bot 的 MCP 配置各自注入一套 `ANP_BASE_URL / ANP_USERNAME / ANP_PASSWORD`——bot A 连控制器 A，bot B 连控制器 B。同一份代码不同 env，连接与登录态互不可见。

**WorkBuddy（mcp.json）**：

```json
{
  "mcpServers": {
    "anp": {
      "command": "python",
      "args": ["-m", "anp_mcp"],
      "env": {
        "ANP_BASE_URL": "https://10.1.203.3:8443",
        "ANP_USERNAME": "admin",
        "ANP_PASSWORD": "yourpass"
      }
    }
  }
}
```

### 模式 B：单实例多控制器（工具内 `controller` 参数路由）

```json
{
  "mcpServers": {
    "anp-multi": {
      "command": "python",
      "args": ["-m", "anp_mcp"],
      "env": { "ANP_CONTROLLERS_FILE": "C:/Users/me/.anp-mcp/controllers.json" }
    }
  }
}
```

调用流程：先 `anp_controllers` 看可用目标，再在任意工具里传 `"controller": "beijing"`。客户端不方便给文件时，把同一份 JSON 压成一行放进 `ANP_CONTROLLERS` 环境变量即可。

### 认证行为（自动，无需工具）

首次请求自动 `GET /public/authenticate/v1` 登录，token 缓存在内存；任何请求遇 401 自动重登一次并重试。`anp_ping` / `anp_controllers(probe=true)` 可主动验证凭据。

## 安全要点

- 密码可只配 MD5（`ANP_PASSWORD_MD5` / `password_md5`），避免明文出现在配置中；明文配置时传输前也只发送 MD5。
- token 仅存进程内存，不落盘、不进日志。
- 错误信息不含凭据；`ANP_LOG_LEVEL` 默认 WARNING。
- 自签证书默认跳过校验（`verify_ssl=false`），生产环境建议导入受信证书后开启。
- `.env`、`controllers.json` 已被 `.gitignore` 排除，请勿提交真实凭据。
- DESTRUCTIVE 操作（重启/删除）依赖客户端权限确认拦截，请谨慎授权。

## 开发

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q     # 90 用例，全离线（respx mock）
```

设计文档见 `DESIGN.md`，实施计划见 `PLAN.md`。API 依据：《ANP控制器北向接口API说明书—业务管理分册-1 2025》《故障性能 2025》。
