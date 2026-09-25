# anp-mcp 部署与使用手册

面向三种客户端的完整接入指南：**WorkBuddy 桌面应用**、**Claude Code 命令行**、**OpenClaw + Telegram 多 bot**。覆盖单控制器 / 多控制器、单 MCP 实例 / 多 MCP 实例的全部组合，以及切换目标控制器的操作方法。

> 前提：仓库已发布到 GitHub（下文以 `https://github.com/<你的用户名>/anpcmcp` 为例，请替换为实际地址）。

---

## 目录

1. [部署形态决策：先选对模式](#1-部署形态决策先选对模式)
2. [安装：从 GitHub 获取](#2-安装从-github-获取)
3. [配置模型速览](#3-配置模型速览)
4. [WorkBuddy 桌面应用接入](#4-workbuddy-桌面应用接入)
5. [Claude Code 命令行接入](#5-claude-code-命令行接入)
6. [OpenClaw + Telegram 多 bot 接入](#6-openclaw--telegram-多-bot-接入)
7. [切换目标控制器的三种方法](#7-切换目标控制器的三种方法)
8. [验证与排障](#8-验证与排障)
9. [安全清单](#9-安全清单)

---

## 1. 部署形态决策：先选对模式

| 你的场景 | 推荐形态 | 理由 |
|---|---|---|
| 只有一台控制器，单客户端 | **单控制器 env** | 配置最少，三个变量搞定 |
| 一台控制器，多个客户端/bot 复用 | **单控制器 env × N 实例** | 同配置多实例，互不干扰 |
| 多台控制器，单用户手动切换 | **单实例 + 多控制器配置** | 工具内 `controller` 参数路由，资源最省 |
| 多 bot，每个 bot 管不同控制器 | **多实例（模式 A），每 bot 绑一套 env** | bot 间零耦合，权限/凭据完全隔离 |
| 多 bot 管多控制器但实例太多 | **单实例（模式 B）+ bot 提示词指定 controller** | 省资源，但依赖 bot 遵守提示词约束 |

一句话原则：**隔离要求高 → 多实例（模式 A）；资源/管理成本优先 → 单实例（模式 B）**。两种模式可以混合使用。

---

## 2. 安装：从 GitHub 获取

要求：Python ≥ 3.10，pip 可用。

### 方式一：pip 直接安装（推荐，仓库根目录即 pyproject 所在）

```bash
pip install git+https://github.com/<你的用户名>/anpcmcp.git
```

### 方式二：仓库根目录下还有 anp-mcp 子目录时

```bash
pip install "git+https://github.com/<你的用户名>/anpcmcp.git#subdirectory=anp-mcp"
```

### 方式三：克隆后可编辑安装（需要改代码时）

```bash
git clone https://github.com/<你的用户名>/anpcmcp.git
cd anpcmcp/anp-mcp        # 视仓库结构调整
pip install -e .
```

### 验证安装

```bash
python -c "import anp_mcp; print('ok')"
# 完整冒烟：应能列出 15 个工具（见第 8 节）
```

### 固定版本

生产环境建议锁定 commit，避免上游变更直接影响：

```bash
pip install "git+https://github.com/<你的用户名>/anpcmcp.git@<commit-sha>#subdirectory=anp-mcp"
```

> 注意：依赖钉在 `mcp<2`（mcp 2.x 将 FastMCP 改名为 MCPServer，不兼容）。pip 会自动解析，不要手动升级 mcp 到 2.x。

---

## 3. 配置模型速览

anp-mcp 从三个来源读取控制器配置，**可共存，优先级从高到低**：

| 优先级 | 来源 | 适用场景 |
|---|---|---|
| 1 | `ANP_CONTROLLERS`（内联 JSON 字符串） | 客户端只能注入 env、不方便给文件 |
| 2 | `ANP_CONTROLLERS_FILE`（JSON 文件路径） | 多控制器，推荐放 `~/.anp-mcp/controllers.json` |
| 3 | `ANP_BASE_URL` / `ANP_USERNAME` / `ANP_PASSWORD[_MD5]` | 单控制器，隐式成为 default |

### 单控制器（3 个变量）

```bash
ANP_BASE_URL=https://10.1.203.3:8443   # 控制器地址:端口，不含路径
ANP_USERNAME=admin
ANP_PASSWORD=yourpass                   # 或 ANP_PASSWORD_MD5=<md5>，避免明文
```

### 多控制器（controllers.json）

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

- `default` 指定省略 `controller` 参数时的目标；省略 default 键则取第一个控制器。
- 每个控制器可选 `verify_ssl`（默认 false，自签证书场景）和 `timeout`（默认 30 秒）。
- 文件存放位置建议：`~/.anp-mcp/controllers.json`（用户目录，**不要**放项目目录）；POSIX 下 `chmod 600`。
- 环境变量注入同样的 JSON 时压成一行：`ANP_CONTROLLERS={"default":"shanghai","controllers":{...}}`。

---

## 4. WorkBuddy 桌面应用接入

配置文件：`~/.workbuddy/mcp.json`（Windows 即 `C:\Users\<你>\.workbuddy\mcp.json`）。编辑前先备份；新 server 写入后**不会自动激活**——需打开 WorkBuddy 的连接器管理页面，在自定义连接器入口对新 server 点击「信任」。

### 4.1 单控制器

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

> Windows 上若 `python` 不在 PATH，用绝对路径，如 `"command": "C:/Users/<你>/AppData/Local/Programs/Python/Python313/python.exe"`。

### 4.2 多控制器（单实例，推荐）

```json
{
  "mcpServers": {
    "anp-multi": {
      "command": "python",
      "args": ["-m", "anp_mcp"],
      "env": {
        "ANP_CONTROLLERS_FILE": "C:/Users/<你>/.anp-mcp/controllers.json"
      }
    }
  }
}
```

对话中切换目标：先让助手调用 `anp_controllers` 查看可用控制器，之后任何工具调用带上 `controller` 参数即可，例如「查一下 beijing 控制器的激活告警」。

### 4.3 多实例（每控制器一个 server）

```json
{
  "mcpServers": {
    "anp-sh": {
      "command": "python",
      "args": ["-m", "anp_mcp"],
      "env": { "ANP_BASE_URL": "https://10.1.203.3:8443", "ANP_USERNAME": "admin", "ANP_PASSWORD": "pass1" }
    },
    "anp-bj": {
      "command": "python",
      "args": ["-m", "anp_mcp"],
      "env": { "ANP_BASE_URL": "https://10.1.204.125:8443", "ANP_USERNAME": "ops", "ANP_PASSWORD": "pass2" }
    }
  }
}
```

对话中切换目标：直接点名 server，如「用 anp-bj 查设备列表」。两套工具名相同（前缀 `mcp__anp-sh__` / `mcp__anp-bj__`），由你指定用哪套。

### 4.4 使用示例（对话直接说）

- 「查上海控制器的激活告警」
- 「列出 beijing 的所有设备，按站点分组」
- 「用 anp_ping 验证 beijing 的凭据是否有效」
- ⚠️ 「重启设备 DEV-001」→ 会触发 WorkBuddy 的操作确认（DESTRUCTIVE）

---

## 5. Claude Code 命令行接入

### 5.1 单控制器

```bash
claude mcp add anp \
  -e ANP_BASE_URL=https://10.1.203.3:8443 \
  -e ANP_USERNAME=admin -e ANP_PASSWORD=yourpass \
  -- python -m anp_mcp
```

### 5.2 多控制器（单实例）

```bash
claude mcp add anp-multi \
  -e ANP_CONTROLLERS_FILE="$HOME/.anp-mcp/controllers.json" \
  -- python -m anp_mcp
```

会话内切换：让 Claude 先调 `anp_controllers`，之后说「查 beijing 的恢复告警」即可（Claude 会在工具调用中带上 `"controller": "beijing"`）。

### 5.3 多实例

```bash
claude mcp add anp-sh \
  -e ANP_BASE_URL=https://10.1.203.3:8443 \
  -e ANP_USERNAME=admin -e ANP_PASSWORD=pass1 \
  -- python -m anp_mcp

claude mcp add anp-bj \
  -e ANP_BASE_URL=https://10.1.204.125:8443 \
  -e ANP_USERNAME=ops -e ANP_PASSWORD=pass2 \
  -- python -m anp_mcp
```

### 5.4 作用域与日常管理

```bash
claude mcp list                 # 查看已注册 server
claude mcp get anp-multi        # 查看某 server 详情
claude mcp remove anp-bj        # 移除
# 默认 local 作用域（仅当前项目）；全局可用：
claude mcp add --scope user anp ... 
```

会话中输入 `/mcp` 可查看连接状态。首次使用带 DESTRUCTIVE 标注的工具（restart/delete）时，Claude Code 会弹权限确认，按需放行。

> 凭据写进了 `~/.claude.json`，注意该文件的文件权限；更敏感的环境可改用 `-e ANP_PASSWORD_MD5=<md5>`。

---

## 6. OpenClaw + Telegram 多 bot 接入

目标：**每个 Telegram bot 绑定一个 ANP 控制器**，不同 bot 的运维范围、凭据、登录态完全隔离。

### 6.1 规划 bot ↔ 控制器映射

先画一张表（示例）：

| Telegram bot | Token 来源 | 目标控制器 | 凭据 |
|---|---|---|---|
| `@sh_noc_bot` | BotFather token A | shanghai | admin / pass1 |
| `@bj_noc_bot` | BotFather token B | beijing | ops / pass2 |
| `@gz_noc_bot` | BotFather token C | guangzhou | ops_gz / pass3 |

### 6.2 模式 A（推荐）：每 bot 一个 MCP 实例

在 OpenClaw 中为**每个 bot 的 agent** 分别注册 MCP server，env 各自指向自己的控制器。以 OpenClaw 的 agent/MCP 配置为例（字段名以你所用 OpenClaw 版本为准，核心是 `command` + `env`）：

```yaml
# bot: sh_noc_bot 的 agent 配置
mcp_servers:
  - name: anp
    command: python
    args: ["-m", "anp_mcp"]
    env:
      ANP_BASE_URL: https://10.1.203.3:8443
      ANP_USERNAME: admin
      ANP_PASSWORD: pass1

# bot: bj_noc_bot 的 agent 配置（另一个独立 agent）
mcp_servers:
  - name: anp
    command: python
    args: ["-m", "anp_mcp"]
    env:
      ANP_BASE_URL: https://10.1.204.125:8443
      ANP_USERNAME: ops
      ANP_PASSWORD: pass2
```

要点：

- 每个 bot 是**独立 agent + 独立 MCP 进程**，token 缓存与 401 重登互不可见——`@sh_noc_bot` 永远摸不到 beijing。
- bot 的系统提示词无需提及控制器选择，工具里没有歧义。
- bot 数量多时进程数线性增长；每个实例空闲时几乎零开销（连接懒加载，首次调用才登录）。

### 6.3 模式 B（备选）：所有 bot 共享一个多控制器实例

所有 bot 的 agent 挂同一个 MCP server：

```yaml
mcp_servers:
  - name: anp-multi
    command: python
    args: ["-m", "anp_mcp"]
    env:
      ANP_CONTROLLERS_FILE: /home/openclaw/.anp-mcp/controllers.json
```

然后**在每个 bot 的系统提示词中锁定它的控制器**：

```
你是上海站点运维助手。所有 anp 工具调用必须带 "controller": "shanghai" 参数，
禁止调用其他控制器。用户问及别的站点时回复"此 bot 仅管辖上海站点"。
```

⚠️ 模式 B 的隔离靠提示词约束，是软隔离——bot 理论上仍可传其他 controller 值。对安全边界有要求（如不同租户的运维 bot）务必用模式 A。

### 6.4 Telegram 侧验证清单

每个 bot 上线后，在对应聊天里依次发：

1. 「列出你可用的控制器」→ 应只看到（或被约束到）自己的控制器
2. 「ping 一下控制器」→ `anp_ping` 返回 ok，确认凭据有效
3. 「查看激活告警」→ 正常返回数据
4. 尝试让它查别的控制器（模式 B 下应被提示词拒绝）

---

## 7. 切换目标控制器的三种方法

| 方法 | 适用形态 | 操作 |
|---|---|---|
| **① 工具参数路由** | 单实例多控制器 | 任意工具传 `"controller": "<名字>"`；先调 `anp_controllers` 可列出全部目标及其 probe 状态 |
| **② 点名 server** | 多实例 | 对话中指定用哪个 server（WorkBuddy/Claude Code 按工具前缀区分，如 `mcp__anp-bj__*`） |
| **③ 改配置重启** | 任何形态 | 修改 `controllers.json` 的 `default` 键或 env 变量，重启客户端/MCP 进程后生效（对话说「重载 anp 的 MCP 配置」或重开会话） |

日常推荐：单实例用户固定用 ①（说「查 beijing 的…」即可）；多实例用户固定用 ②；换账号/加控制器等结构性变更走 ③。

注意：`default` 只影响**省略 controller 参数时**的落点，不阻止显式指定其他控制器；需要硬隔离时请用多实例。

---

## 8. 验证与排障

### 冒烟测试（不经任何客户端，直接验证 server）

```bash
# 应输出 tools: 15
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n' \
  | ANP_BASE_URL=https://10.1.203.3:8443 ANP_USERNAME=admin ANP_PASSWORD=yourpass \
    python -m anp_mcp 2>/dev/null | tail -1
```

### 常见问题

| 现象 | 原因与处理 |
|---|---|
| 启动即报 `no controller configured` | 三个配置来源都没配齐；检查 env 拼写（必须 `ANP_` 前缀） |
| 报 `unknown controller 'xxx'` | 名字不在 controllers.json 里；先调 `anp_controllers` 看可用列表 |
| `code: 3` / `code: 604` | 控制器返回：3=用户不存在，604=密码错误；核对凭据（注意 MD5 是否算对） |
| 一直超时 | 确认 `base_url` 含端口、网络可达（控制器多为内网/专线）；可临时调大 `ANP_TIMEOUT` |
| SSL 报错 | 自签证书保持 `verify_ssl=false`；生产开启后需导入受信证书 |
| WorkBuddy 里看不到工具 | 配置后未「信任」新 server；到连接器管理页确认 |
| Claude Code 连不上 | `claude mcp list` 看状态；确认 `python` 在 PATH 或改用绝对路径 |
| 升级后工具行为异常 | 确认没有把 mcp 升到 2.x：`pip show mcp`，需要时 `pip install "mcp<2"` |

---

## 9. 安全清单

- [ ] 密码优先用 `password_md5` / `ANP_PASSWORD_MD5`，避免明文落盘
- [ ] controllers.json 放用户目录（`~/.anp-mcp/`），POSIX 下 `chmod 600`；绝不提交进 git
- [ ] `.env` 已被 `.gitignore` 排除，含真实凭据的文件不要拷进仓库目录
- [ ] token 仅存进程内存，不落盘；日志默认 WARNING 且不含凭据
- [ ] `restart` / `delete` 类 DESTRUCTIVE 操作依赖客户端权限确认——Telegram bot 场景建议在 OpenClaw 侧限制可触发写操作的 chat/user 白名单
- [ ] 多租户/多管理者场景一律用模式 A（进程级隔离），不要依赖提示词做安全边界
- [ ] pip 安装锁定 commit，防止上游变更静默改变行为

---

配置字段、认证流程与全部 15 个工具的详细说明见 `README.md`；架构设计见 `DESIGN.md`。
