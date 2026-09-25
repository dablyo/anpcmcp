"""ANP-MCP 配置加载。三级来源（高→低）：

1. ANP_CONTROLLERS（内联 JSON）
2. ANP_CONTROLLERS_FILE（JSON 文件）
3. 单控制器环境变量（ANP_BASE_URL/ANP_USERNAME/ANP_PASSWORD[_MD5]/...，隐式 default）

单控制器 env 仅在命名来源未定义 default profile 时补位。
错误信息永不回显凭据值。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

DEFAULT_CONTROLLER_NAME = "default"


class ConfigError(Exception):
    """配置缺失或非法。不携带任何凭据值。"""


@dataclass(frozen=True)
class ControllerProfile:
    name: str
    base_url: str
    username: str
    password_md5: str
    verify_ssl: bool = False
    timeout: float = 30.0


def md5_password(plain: str) -> str:
    """认证接口要求密码以 MD5 Hash 传输（业务分册 3.3.1）。"""
    return hashlib.md5(plain.encode("utf-8")).hexdigest()


def _coerce_bool(value: object, default: bool, where: str) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    raise ConfigError(f"{where}: 'verify_ssl' must be boolean-like")


def _build_profile(name: str, data: Mapping[str, object]) -> ControllerProfile:
    if not isinstance(data, Mapping):
        raise ConfigError(f"controller '{name}': config must be a JSON object")
    base_url = data.get("base_url")
    username = data.get("username")
    if not base_url or not isinstance(base_url, str):
        raise ConfigError(f"controller '{name}': missing required field 'base_url'")
    if not base_url.startswith(("http://", "https://")):
        raise ConfigError(f"controller '{name}': 'base_url' must start with http:// or https://")
    if not username or not isinstance(username, str):
        raise ConfigError(f"controller '{name}': missing required field 'username'")
    password, password_md5 = data.get("password"), data.get("password_md5")
    if password_md5:
        if not isinstance(password_md5, str):
            raise ConfigError(f"controller '{name}': 'password_md5' must be a string")
        md5 = password_md5
    elif password:
        if not isinstance(password, str):
            raise ConfigError(f"controller '{name}': 'password' must be a string")
        md5 = md5_password(password)
    else:
        raise ConfigError(f"controller '{name}': missing credential: "
                          f"set 'password' or 'password_md5'")
    try:
        timeout = float(data.get("timeout", 30.0))
    except (TypeError, ValueError):
        raise ConfigError(f"controller '{name}': 'timeout' must be a number")
    return ControllerProfile(
        name=name,
        base_url=base_url.rstrip("/"),
        username=username,
        password_md5=md5,
        verify_ssl=_coerce_bool(data.get("verify_ssl"), False, f"controller '{name}'"),
        timeout=timeout,
    )


def _parse_named_config(raw: str, source_desc: str) -> tuple[dict[str, ControllerProfile], str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{source_desc}: invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ConfigError(f"{source_desc}: top level must be a JSON object")
    controllers = parsed.get("controllers")
    if not isinstance(controllers, dict) or not controllers:
        raise ConfigError(f"{source_desc}: missing non-empty 'controllers' object")
    profiles = {name: _build_profile(name, data) for name, data in controllers.items()}
    if "default" not in parsed:
        # 未显式指定 default：返回 None，由 load_config 决定回退策略
        # （单控制器 env 可补位，否则取排序首名）。
        return profiles, None
    default_name = parsed["default"]
    if default_name not in profiles:
        raise ConfigError(f"{source_desc}: 'default' points to unknown controller "
                          f"'{default_name}'; available: {', '.join(sorted(profiles))}")
    return profiles, default_name


def load_config(env: Mapping[str, str] | None = None) -> tuple[list[ControllerProfile], str]:
    """返回 (profiles, default_name)。env 传入时用于测试，不读进程环境与 .env。"""
    environ = dict(os.environ) if env is None else dict(env)
    if env is None:
        load_dotenv()  # 进程真实环境变量优先于 .env 文件

    profiles: dict[str, ControllerProfile] = {}
    default_name: str | None = None

    inline, file_path = environ.get("ANP_CONTROLLERS"), environ.get("ANP_CONTROLLERS_FILE")
    if inline:
        profiles, default_name = _parse_named_config(inline, "ANP_CONTROLLERS")
    elif file_path:
        path = Path(file_path)
        if not path.is_file():
            raise ConfigError(f"ANP_CONTROLLERS_FILE: file not found: {path}")
        profiles, default_name = _parse_named_config(path.read_text(encoding="utf-8"),
                                                     f"ANP_CONTROLLERS_FILE ({path})")

    if environ.get("ANP_BASE_URL"):
        single = _build_profile(DEFAULT_CONTROLLER_NAME, {
            "base_url": environ["ANP_BASE_URL"],
            "username": environ.get("ANP_USERNAME"),
            "password": environ.get("ANP_PASSWORD"),
            "password_md5": environ.get("ANP_PASSWORD_MD5"),
            "verify_ssl": environ.get("ANP_VERIFY_SSL", "false"),
            "timeout": environ.get("ANP_TIMEOUT", "30"),
        })
        if DEFAULT_CONTROLLER_NAME not in profiles and default_name is None:
            profiles[DEFAULT_CONTROLLER_NAME] = single
            default_name = DEFAULT_CONTROLLER_NAME

    if not profiles:
        raise ConfigError("no controller configured: set ANP_CONTROLLERS / ANP_CONTROLLERS_FILE "
                          "or ANP_BASE_URL+ANP_USERNAME+ANP_PASSWORD[_MD5]")
    if default_name is None:
        default_name = sorted(profiles)[0]
    return list(profiles.values()), default_name
